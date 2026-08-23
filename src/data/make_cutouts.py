"""src/data/make_cutouts.py

Genera una biblioteca de "cutouts" RGBA (producto recortado, fondo
transparente) exclusivamente a partir de las imagenes de split=train del
dataset canonico AMARKET, para uso posterior en composicion sintetica de
Phase 2 (docs/governance/03_PHASE2/06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md).

Reutiliza la logica de mascara de foreground de src/data/make_boxes.py
(load_and_validate_image, make_mask_from_alpha, make_mask_from_rgb) -- no la
reimplementa.

Regla critica: NUNCA procesa una fila cuyo split no sea "train". val=98 y
test=98 estan absolutamente prohibidos como fuente de cutouts.

Correccion P2-005 (cierre de CHANGES_REQUESTED sobre HEAD 7b28554d...): el
contrato (Seccion 2, punto 6) exige registrar "category metadata" por cutout.
Por eso el manifiesto enriquecido (data/manifests/source_assets_enriched.csv)
es ahora una entrada OBLIGATORIA y explicita (--enriched-manifest): no existe
modo de produccion que genere el manifiesto de cutouts sin el gate de
metadata. El join contra splits.csv es determinista por source_asset_id y
valida sku_id/sha256/split; cualquier discrepancia detiene la ejecucion
(nunca se degrada a un rechazo silencioso ni se inventa un valor). category
se copia literalmente y puede ser vacia; metadata_status se copia
literalmente y nunca puede ser vacio -- pero un metadata_status=FAILED no
afecta la aceptacion del cutout, que sigue dependiendo solo de imagen/mascara.

Ejemplo:
    python src/data/make_cutouts.py \
        --dataset-root /ruta/AMARKET_YOLO_DATASET_655_SEED42 \
        --splits data/manifests/splits.csv \
        --enriched-manifest data/manifests/source_assets_enriched.csv \
        --output-root /ruta/privada/externa/P2_TRAIN_CUTOUTS_459 \
        --manifest data/manifests/p2_cutout_library.csv
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import sys
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from src.data.make_boxes import (  # noqa: E402
    load_and_validate_image,
    make_mask_from_alpha,
    make_mask_from_rgb,
)

MANIFEST_FIELDS = [
    "source_asset_id",
    "sku_id",
    "split",
    "source_sha256",
    "source_image_relative_path",
    "mask_method",
    "x0",
    "y0",
    "x1",
    "y1",
    "cutout_width",
    "cutout_height",
    "foreground_pixels",
    "cutout_sha256",
    "cutout_relative_path",
    "category",
    "metadata_status",
    "status",
    "rejection_reason",
]


class NotTrainSplitError(ValueError):
    """Se intento procesar una fila cuyo split no es 'train'."""


class EnrichedManifestError(ValueError):
    """Error de integridad en el join contra source_assets_enriched.csv.

    Cubre: source_asset_id duplicado en el manifiesto enriquecido, fuentes
    faltantes/adicionales respecto a splits.csv, o desacuerdo de
    sku_id/sha256/split entre ambos manifiestos para el mismo
    source_asset_id. Siempre detiene la ejecucion -- nunca se resuelve
    inventando o adivinando el valor correcto.
    """


class MissingMetadataStatusError(ValueError):
    """metadata_status vacio para un source_asset_id -- viola el contrato P2-005.

    category puede ser vacia (dato no disponible del catalogo), pero
    metadata_status debe declarar explicitamente el resultado del scraping
    de metadata (p.ej. OK/FAILED); nunca puede quedar vacio.
    """


def ensure_train_only(row: dict) -> None:
    """Guarda de defensa: nunca procesar una fila que no sea split=train.

    Esta funcion existe para que el rechazo de val/test sea explicito y
    verificable por test, no un efecto secundario incidental del filtro
    de lectura del CSV.
    """
    split = row.get("split")
    if split != "train":
        raise NotTrainSplitError(
            f"split '{split}' no permitido para biblioteca de cutouts "
            f"(solo 'train'); source_asset_id={row.get('source_asset_id')}"
        )


def ensure_metadata_status_present(enriched_row: dict, source_asset_id: str) -> None:
    """Guarda de defensa: metadata_status nunca puede llegar vacio a un cutout."""
    if not enriched_row.get("metadata_status"):
        raise MissingMetadataStatusError(
            f"metadata_status vacio para source_asset_id={source_asset_id}; "
            "el manifiesto enriquecido debe declarar un estado explicito "
            "(p.ej. OK/FAILED), nunca vacio"
        )


def load_enriched_manifest(path: Path) -> dict[str, dict]:
    """Carga source_assets_enriched.csv indexado por source_asset_id.

    Lanza EnrichedManifestError si hay source_asset_id duplicados -- un
    manifiesto enriquecido con duplicados no puede unirse deterministicamente
    contra splits.csv.
    """
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))

    by_id: dict[str, dict] = {}
    duplicates: list[str] = []
    for row in rows:
        asset_id = row["source_asset_id"]
        if asset_id in by_id:
            duplicates.append(asset_id)
            continue
        by_id[asset_id] = row

    if duplicates:
        raise EnrichedManifestError(
            f"source_asset_id duplicado en manifiesto enriquecido: {sorted(set(duplicates))}"
        )

    return by_id


def validate_enriched_join(splits_rows: list[dict], enriched_by_id: dict[str, dict]) -> dict:
    """Valida el join determinista splits.csv <-> source_assets_enriched.csv.

    Se valida contra TODAS las filas de splits.csv (train/val/test), no solo
    train, porque el manifiesto enriquecido debe cubrir el dataset completo
    de 655 fuentes. Cualquier discrepancia (fuente faltante, fuente extra, o
    desacuerdo de sku_id/sha256/split para el mismo source_asset_id) lanza
    EnrichedManifestError y detiene la ejecucion -- nunca un rechazo
    silencioso ni un valor inventado.
    """
    split_ids = {row["source_asset_id"] for row in splits_rows}
    enriched_ids = set(enriched_by_id.keys())

    missing = sorted(split_ids - enriched_ids)
    extra = sorted(enriched_ids - split_ids)

    if missing:
        raise EnrichedManifestError(
            f"source_asset_id en splits.csv sin entrada en manifiesto enriquecido: {missing}"
        )
    if extra:
        raise EnrichedManifestError(
            f"source_asset_id en manifiesto enriquecido sin entrada en splits.csv: {extra}"
        )

    sku_mismatches: list[str] = []
    hash_mismatches: list[str] = []
    split_mismatches: list[str] = []

    for row in splits_rows:
        asset_id = row["source_asset_id"]
        enriched_row = enriched_by_id[asset_id]
        if enriched_row["sku_id"] != row["sku_id"]:
            sku_mismatches.append(asset_id)
        if enriched_row["sha256"] != row["source_sha256"]:
            hash_mismatches.append(asset_id)
        if enriched_row["split"] != row["split"]:
            split_mismatches.append(asset_id)

    if sku_mismatches:
        raise EnrichedManifestError(f"sku_id discordante para source_asset_id: {sku_mismatches}")
    if hash_mismatches:
        raise EnrichedManifestError(f"sha256 discordante para source_asset_id: {hash_mismatches}")
    if split_mismatches:
        raise EnrichedManifestError(f"split discordante para source_asset_id: {split_mismatches}")

    return {
        "enriched_rows": len(enriched_by_id),
        "splits_rows": len(splits_rows),
        "join_matched": len(splits_rows),
        "join_missing": 0,
        "join_extra": 0,
        "sku_mismatches": 0,
        "hash_mismatches": 0,
        "split_mismatches": 0,
    }


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def build_foreground_mask(
    arr: np.ndarray,
    *,
    alpha_threshold: float,
    background_uniformity_tolerance: float,
    foreground_delta: float,
    min_foreground_pixels: int,
) -> tuple[np.ndarray, str]:
    """Misma politica alpha->RGB que audit_image en make_boxes.py.

    Intenta primero canal alfa real; si no demuestra transparencia real,
    cae a deteccion de fondo uniforme en RGB.
    """
    mask_method = "alpha"
    try:
        mask = make_mask_from_alpha(arr, alpha_threshold)
    except ValueError:
        rgb = arr[:, :, :3]
        mask = make_mask_from_rgb(
            rgb,
            background_uniformity_tolerance=background_uniformity_tolerance,
            foreground_delta=foreground_delta,
            min_foreground_pixels=min_foreground_pixels,
        )
        mask_method = "rgb"
    return mask, mask_method


def make_cutout(
    image_path: Path,
    *,
    alpha_threshold: float,
    background_uniformity_tolerance: float,
    foreground_delta: float,
    min_foreground_pixels: int,
) -> dict:
    """Genera un cutout RGBA a partir de una imagen fuente ya validada.

    No escribe nada a disco. Devuelve los datos crudos (incluida la imagen
    PIL en memoria) para que el llamador decida donde persistirlos.

    Lanza ValueError si la mascara de foreground no puede calcularse o
    resulta vacia (rechazo trazable, nunca silencioso).
    """
    arr = load_and_validate_image(str(image_path))

    mask, mask_method = build_foreground_mask(
        arr,
        alpha_threshold=alpha_threshold,
        background_uniformity_tolerance=background_uniformity_tolerance,
        foreground_delta=foreground_delta,
        min_foreground_pixels=min_foreground_pixels,
    )

    if not mask.any():
        raise ValueError("mascara de foreground vacia: no hay pixeles de producto")

    ys, xs = mask.nonzero()
    x0, x1 = int(xs.min()), int(xs.max()) + 1
    y0, y1 = int(ys.min()), int(ys.max()) + 1

    rgb = arr[:, :, :3]
    cropped_rgb = rgb[y0:y1, x0:x1]
    cropped_mask = mask[y0:y1, x0:x1]

    # No se inventa fondo: fuera de la mascara, alpha=0 (transparente).
    # Los pixeles RGB originales se conservan tal cual dentro del recorte,
    # incluso donde alpha=0 -- no se rellenan ni se generan con IA.
    alpha_channel = np.where(cropped_mask, 255, 0).astype(np.uint8)
    cutout_rgba = np.dstack([cropped_rgb, alpha_channel]).astype(np.uint8)

    cutout_image = Image.fromarray(cutout_rgba, mode="RGBA")

    return {
        "mask_method": mask_method,
        "x0": x0,
        "y0": y0,
        "x1": x1,
        "y1": y1,
        "cutout_width": x1 - x0,
        "cutout_height": y1 - y0,
        "foreground_pixels": int(mask.sum()),
        "cutout_image": cutout_image,
    }


def _png_bytes(image: Image.Image) -> bytes:
    from io import BytesIO

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def process_row(
    row: dict,
    *,
    dataset_root: Path,
    output_root: Path,
    enriched_row: dict,
    alpha_threshold: float,
    background_uniformity_tolerance: float,
    foreground_delta: float,
    min_foreground_pixels: int,
) -> dict:
    """Procesa una unica fila train y devuelve el registro de manifest.

    Nunca lanza por un rechazo de calidad de imagen: los rechazos se
    devuelven como filas con status=rejected y rejection_reason poblada.
    Si lanza, es por violacion de contrato (split != train, o
    metadata_status vacio en el manifiesto enriquecido), que debe frenar la
    ejecucion, no degradarse a un rechazo silencioso.

    category y metadata_status se copian literalmente de enriched_row y no
    dependen del resultado de imagen/mascara: metadata_status=FAILED no
    excluye el cutout de ser aceptado (la aceptacion depende solo de si se
    pudo generar la mascara/recorte).
    """
    ensure_train_only(row)

    source_asset_id = row["source_asset_id"]
    ensure_metadata_status_present(enriched_row, source_asset_id)

    sku_id = row["sku_id"]
    source_image_relative_path = row["image_path"]
    expected_sha = row["source_sha256"]

    # category se copia literalmente; vacia es valida (no se infiere desde
    # marca/presentacion/descripcion/tags/nombre ni ningun otro campo).
    category = enriched_row.get("category", "")
    metadata_status = enriched_row["metadata_status"]

    record = {
        "source_asset_id": source_asset_id,
        "sku_id": sku_id,
        "split": row["split"],
        "source_sha256": expected_sha,
        "source_image_relative_path": source_image_relative_path,
        "mask_method": "",
        "x0": "",
        "y0": "",
        "x1": "",
        "y1": "",
        "cutout_width": "",
        "cutout_height": "",
        "foreground_pixels": "",
        "cutout_sha256": "",
        "cutout_relative_path": "",
        "category": category,
        "metadata_status": metadata_status,
        "status": "rejected",
        "rejection_reason": "",
    }

    image_path = dataset_root / source_image_relative_path

    try:
        if not image_path.is_file():
            raise ValueError(f"imagen fuente no encontrada: {image_path}")

        actual_sha = sha256_file(image_path)
        if actual_sha != expected_sha:
            raise ValueError(
                f"source_sha256 no coincide: esperado={expected_sha} "
                f"actual={actual_sha}"
            )

        result = make_cutout(
            image_path,
            alpha_threshold=alpha_threshold,
            background_uniformity_tolerance=background_uniformity_tolerance,
            foreground_delta=foreground_delta,
            min_foreground_pixels=min_foreground_pixels,
        )

        cutout_bytes = _png_bytes(result["cutout_image"])
        cutout_sha256 = sha256_bytes(cutout_bytes)

        cutouts_dir = output_root / "cutouts"
        cutouts_dir.mkdir(parents=True, exist_ok=True)

        cutout_relative_path = f"cutouts/{source_asset_id}.png"
        cutout_path = output_root / cutout_relative_path

        tmp_path = cutout_path.with_suffix(cutout_path.suffix + ".tmp")
        tmp_path.write_bytes(cutout_bytes)
        tmp_path.replace(cutout_path)

        record.update(
            {
                "mask_method": result["mask_method"],
                "x0": result["x0"],
                "y0": result["y0"],
                "x1": result["x1"],
                "y1": result["y1"],
                "cutout_width": result["cutout_width"],
                "cutout_height": result["cutout_height"],
                "foreground_pixels": result["foreground_pixels"],
                "cutout_sha256": cutout_sha256,
                "cutout_relative_path": cutout_relative_path,
                "status": "accepted",
                "rejection_reason": "",
            }
        )
    except ValueError as exc:
        record["status"] = "rejected"
        record["rejection_reason"] = str(exc)

    return record


def build_cutout_library(
    *,
    dataset_root: Path,
    splits_path: Path,
    enriched_manifest_path: Path,
    output_root: Path,
    manifest_path: Path,
    alpha_threshold: float = 127,
    background_uniformity_tolerance: float = 5.0,
    foreground_delta: float = 30.0,
    min_foreground_pixels: int = 10,
) -> dict:
    """Orquesta la generacion completa de la biblioteca de cutouts TRAIN-only.

    El manifiesto enriquecido (enriched_manifest_path) es una entrada
    obligatoria: se valida su join determinista contra splits.csv (por
    source_asset_id, con sku_id/sha256/split concordantes) ANTES de procesar
    ningun cutout. No existe forma de generar el manifiesto de cutouts sin
    pasar por este gate de metadata.

    Devuelve un resumen con los conteos gobernantes requeridos por
    docs/evidence/P2_CUTOUT_LIBRARY.md.
    """
    with splits_path.open("r", encoding="utf-8-sig", newline="") as handle:
        all_rows = list(csv.DictReader(handle))

    enriched_by_id = load_enriched_manifest(enriched_manifest_path)
    join_summary = validate_enriched_join(all_rows, enriched_by_id)

    train_rows = [row for row in all_rows if row["split"] == "train"]

    seen_asset_ids: set[str] = set()
    duplicate_source_ids = 0
    manifest_rows = []

    for row in train_rows:
        asset_id = row["source_asset_id"]
        if asset_id in seen_asset_ids:
            duplicate_source_ids += 1
            continue
        seen_asset_ids.add(asset_id)

        manifest_rows.append(
            process_row(
                row,
                dataset_root=dataset_root,
                output_root=output_root,
                enriched_row=enriched_by_id[asset_id],
                alpha_threshold=alpha_threshold,
                background_uniformity_tolerance=background_uniformity_tolerance,
                foreground_delta=foreground_delta,
                min_foreground_pixels=min_foreground_pixels,
            )
        )

    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=MANIFEST_FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(manifest_rows)

    accepted = [r for r in manifest_rows if r["status"] == "accepted"]
    rejected = [r for r in manifest_rows if r["status"] == "rejected"]
    category_nonempty = [r for r in manifest_rows if r["category"]]
    metadata_status_nonempty = [r for r in manifest_rows if r["metadata_status"]]
    metadata_ok = [r for r in manifest_rows if r["metadata_status"] == "OK"]
    metadata_failed = [r for r in manifest_rows if r["metadata_status"] == "FAILED"]

    return {
        "train_expected": 459,
        "train_attempted": len(train_rows),
        "cutout_accepted": len(accepted),
        "cutout_rejected": len(rejected),
        "val_used": 0,
        "test_used": 0,
        "duplicate_source_ids": duplicate_source_ids,
        "manifest_sha256": sha256_file(manifest_path),
        "rejections": [
            (r["source_asset_id"], r["rejection_reason"]) for r in rejected
        ],
        "enriched_rows": join_summary["enriched_rows"],
        "splits_rows": join_summary["splits_rows"],
        "join_matched": join_summary["join_matched"],
        "join_missing": join_summary["join_missing"],
        "join_extra": join_summary["join_extra"],
        "sku_mismatches": join_summary["sku_mismatches"],
        "hash_mismatches": join_summary["hash_mismatches"],
        "split_mismatches": join_summary["split_mismatches"],
        "category_nonempty": len(category_nonempty),
        "metadata_status_nonempty": len(metadata_status_nonempty),
        "metadata_ok": len(metadata_ok),
        "metadata_failed": len(metadata_failed),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--dataset-root", required=True, type=Path)
    parser.add_argument("--splits", required=True, type=Path)
    parser.add_argument(
        "--enriched-manifest",
        required=True,
        type=Path,
        help="data/manifests/source_assets_enriched.csv -- obligatorio, gate de metadata (category/metadata_status)",
    )
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--alpha-threshold", type=float, default=127)
    parser.add_argument("--background-uniformity-tolerance", type=float, default=5.0)
    parser.add_argument("--foreground-delta", type=float, default=30.0)
    parser.add_argument("--min-foreground-pixels", type=int, default=10)
    args = parser.parse_args()

    summary = build_cutout_library(
        dataset_root=args.dataset_root,
        splits_path=args.splits,
        enriched_manifest_path=args.enriched_manifest,
        output_root=args.output_root,
        manifest_path=args.manifest,
        alpha_threshold=args.alpha_threshold,
        background_uniformity_tolerance=args.background_uniformity_tolerance,
        foreground_delta=args.foreground_delta,
        min_foreground_pixels=args.min_foreground_pixels,
    )

    print("=== P2-005 TRAIN CUTOUT LIBRARY ===")
    print(f"ENRICHED_ROWS={summary['enriched_rows']}")
    print(f"SPLITS_ROWS={summary['splits_rows']}")
    print(f"JOIN_MATCHED={summary['join_matched']}")
    print(f"JOIN_MISSING={summary['join_missing']}")
    print(f"JOIN_EXTRA={summary['join_extra']}")
    print(f"SKU_MISMATCHES={summary['sku_mismatches']}")
    print(f"HASH_MISMATCHES={summary['hash_mismatches']}")
    print(f"SPLIT_MISMATCHES={summary['split_mismatches']}")
    print(f"TRAIN_EXPECTED={summary['train_expected']}")
    print(f"TRAIN_ATTEMPTED={summary['train_attempted']}")
    print(f"CUTOUT_ACCEPTED={summary['cutout_accepted']}")
    print(f"CUTOUT_REJECTED={summary['cutout_rejected']}")
    print(f"CATEGORY_NONEMPTY={summary['category_nonempty']}")
    print(f"METADATA_STATUS_NONEMPTY={summary['metadata_status_nonempty']}")
    print(f"METADATA_OK={summary['metadata_ok']}")
    print(f"METADATA_FAILED={summary['metadata_failed']}")
    print(f"VAL_USED={summary['val_used']}")
    print(f"TEST_USED={summary['test_used']}")
    print(f"DUPLICATE_SOURCE_IDS={summary['duplicate_source_ids']}")
    print(f"MANIFEST_SHA256={summary['manifest_sha256']}")

    if summary["cutout_rejected"] > 0:
        print("--- rechazos (source_asset_id: motivo) ---")
        for asset_id, reason in summary["rejections"]:
            print(f"  {asset_id}: {reason}")

    if summary["train_attempted"] != summary["train_expected"]:
        raise SystemExit(
            f"STOP=TRAIN_ATTEMPTED_MISMATCH:"
            f"{summary['train_attempted']}!={summary['train_expected']}"
        )


if __name__ == "__main__":
    main()
