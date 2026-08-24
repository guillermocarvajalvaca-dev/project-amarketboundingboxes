"""src/recognition.py

Segunda etapa (ADR-006, docs/governance/03_PHASE2/14_ADR-006...): identificación
de producto por retrieval visual contra un catálogo de referencia, desacoplada
del detector YOLO monoclase (`class_id=0`). YOLO sigue localizando; este módulo
solo responde "qué producto es" para un crop ya localizado, comparando sus
descriptores SIFT contra los de cada imagen de referencia del catálogo
(`catalog_identity.csv`) y devolviendo el mejor candidato por conteo de buenos
emparejamientos (ratio test de Lowe, 0.75).

No hay clasificación supervisada por SKU: con ~1 muestra por SKU (ver ADR-006)
es estadísticamente inviable. Este es un método de instancia (retrieval), no de
aprendizaje de una frontera de decisión por clase.

Requiere cv2 (opencv), disponible solo en el entorno WSL ComputerVision en este
proyecto -- se importa de forma perezosa para no romper el modo de predict.py
que no usa --catalog (detección pura, sin identificación).
"""
from __future__ import annotations

import csv
import hashlib
import json
import os
from pathlib import Path

import numpy as np

RATIO_TEST_THRESHOLD = 0.75
DEFAULT_UNKNOWN_MIN_GOOD_MATCHES = 8


def _to_local_path(path: str) -> str:
    """Convierte una ruta 'G:\\...' de Windows a '/mnt/g/...' si hace falta.

    catalog_identity.csv se genera con rutas Windows (artefacto de
    documentación general); este backend corre en WSL, donde esas rutas no
    resuelven directamente.
    """
    if len(path) > 1 and path[1] == ":":
        drive = path[0].lower()
        rest = path[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return path


def load_catalog(catalog_csv_path: str) -> list[dict]:
    with open(catalog_csv_path, newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def _catalog_cache_key(catalog_csv_path: str) -> str:
    with open(catalog_csv_path, "rb") as handle:
        digest = hashlib.sha256(handle.read()).hexdigest()
    return digest[:16]


def build_sift_index(catalog: list[dict], cache_dir: str | None = None, catalog_csv_path: str | None = None):
    """Extrae descriptores SIFT de cada imagen de referencia del catálogo.

    Cachea en disco (pickle) por hash del CSV de catálogo: reconstruir el
    índice sobre 459+ imágenes toma ~1 minuto; predict.py no debe pagar ese
    costo en cada invocación.
    """
    import cv2

    cache_meta_path = cache_npz_path = None
    if cache_dir and catalog_csv_path:
        os.makedirs(cache_dir, exist_ok=True)
        key = _catalog_cache_key(catalog_csv_path)
        cache_meta_path = os.path.join(cache_dir, f"sift_index_{key}_meta.json")
        cache_npz_path = os.path.join(cache_dir, f"sift_index_{key}_descriptors.npz")
        if os.path.isfile(cache_meta_path) and os.path.isfile(cache_npz_path):
            # numpy .npz + JSON: no ejecución de código arbitrario al cargar
            # (a diferencia de pickle), seguro aunque el caché quedara en un
            # directorio compartido.
            with open(cache_meta_path, encoding="utf-8") as handle:
                meta = json.load(handle)
            npz = np.load(cache_npz_path)
            return [
                {
                    "sku_id": m["sku_id"],
                    "product_name": m["product_name"],
                    "source_asset_id": m["source_asset_id"],
                    "descriptors": npz[f"d{i}"],
                }
                for i, m in enumerate(meta)
            ]

    detector = cv2.SIFT_create()
    index = []
    for row in catalog:
        img_path = _to_local_path(row["reference_image_path"])
        raw = cv2.imread(img_path, cv2.IMREAD_UNCHANGED)
        if raw is None:
            continue
        gray = _to_gray(raw)
        _, des = detector.detectAndCompute(gray, None)
        if des is None:
            continue
        index.append({
            "sku_id": row["sku_id"],
            "product_name": row["product_name"],
            "source_asset_id": row["source_asset_id"],
            "descriptors": des,
        })

    if cache_dir and catalog_csv_path:
        meta = [
            {"sku_id": e["sku_id"], "product_name": e["product_name"], "source_asset_id": e["source_asset_id"]}
            for e in index
        ]
        with open(cache_meta_path, "w", encoding="utf-8") as handle:
            json.dump(meta, handle, ensure_ascii=False)
        np.savez(cache_npz_path, **{f"d{i}": e["descriptors"] for i, e in enumerate(index)})

    return index


def _to_gray(img):
    import cv2

    if img.ndim == 3 and img.shape[2] == 4:
        alpha = img[:, :, 3]
        bgr = img[:, :, :3]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        gray[alpha < 10] = 0
    elif img.ndim == 3:
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    else:
        gray = img
    return gray


def identify_crop(
    crop_bgr,
    index: list[dict],
    unknown_min_good_matches: int = DEFAULT_UNKNOWN_MIN_GOOD_MATCHES,
) -> dict:
    """Identifica un crop ya localizado por YOLO contra el catálogo.

    Determinista: mismo crop + mismo índice => mismo resultado (SIFT y
    BFMatcher con NORM_L2 no usan aleatoriedad). Devuelve top-5 ordenado por
    conteo de buenos matches (ratio test), y marca UNKNOWN si el mejor
    candidato no alcanza `unknown_min_good_matches` -- no hay evidencia
    suficiente para afirmar una identidad.
    """
    import cv2

    detector = cv2.SIFT_create()
    matcher = cv2.BFMatcher(cv2.NORM_L2)

    if crop_bgr is None or crop_bgr.size == 0:
        return {"sku_id": "UNKNOWN", "product_name": "UNKNOWN", "similarity": 0, "top5": []}

    gray = _to_gray(crop_bgr) if crop_bgr.ndim == 3 else crop_bgr
    _, des = detector.detectAndCompute(gray, None)
    if des is None or len(des) == 0:
        return {"sku_id": "UNKNOWN", "product_name": "UNKNOWN", "similarity": 0, "top5": []}

    scored = []
    for entry in index:
        try:
            matches = matcher.knnMatch(des, entry["descriptors"], k=2)
        except cv2.error:
            continue
        good = sum(
            1
            for pair in matches
            if len(pair) == 2 and pair[0].distance < RATIO_TEST_THRESHOLD * pair[1].distance
        )
        scored.append((good, entry["sku_id"], entry["product_name"], entry["source_asset_id"]))

    scored.sort(key=lambda x: -x[0])
    top5 = [
        {"sku_id": s[1], "product_name": s[2], "source_asset_id": s[3], "good_matches": s[0]}
        for s in scored[:5]
    ]

    if not scored or scored[0][0] < unknown_min_good_matches:
        return {"sku_id": "UNKNOWN", "product_name": "UNKNOWN", "similarity": scored[0][0] if scored else 0, "top5": top5}

    best = scored[0]
    return {"sku_id": best[1], "product_name": best[2], "similarity": best[0], "top5": top5}
