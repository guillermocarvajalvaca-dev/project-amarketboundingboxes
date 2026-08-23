"""
src/data/make_synthetic_scenes.py

P2-007 — Compositor sintético determinista de escenas multiproducto (Fase 2).

Contratos aplicables:
- docs/governance/03_PHASE2/01_CONTRACT_SDD_PHASE2_v2_0_0_FROZEN.md §7, §8
- docs/governance/03_PHASE2/06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md §5-§11
- docs/governance/02_CONTRACTS/BOUNDING_BOX_ALGORITHM_CONTRACT.md (geometría YOLO)

Principios:
- toda la aleatoriedad de una escena deriva EXCLUSIVAMENTE de su scene_seed;
  cada reintento deriva su sub-seed determinísticamente de (scene_seed, attempt);
- la caja YOLO se calcula sobre la máscara VISIBLE final tras el z-order, nunca
  sobre el rectángulo del objeto transformado (§7 del contrato de generación);
- el número de objetos por escena nunca se reduce en silencio: si la escena no
  cumple las restricciones, se regenera; si se agotan los intentos, falla fuerte;
- ninguna ruta absoluta ni con traversal se acepta ni se escribe en el manifiesto;
- no hay filtros generativos: solo escalado, rotación y alpha compositing;
- el gate anti-fuga (allowlist train/accepted) y la procedencia del generador
  (generator_commit) son OBLIGATORIOS: ninguna corrida FULL, PILOT o SELECTED
  puede completar sin ambos;
- antes de usar un cutout se verifica su sha256 físico contra el declarado;
- category y metadata_status se propagan literales desde P2-006, nunca se
  inventan aquí.

Uso:
    python -m src.data.make_synthetic_scenes \
        --assignments <ruta>/scene_source_assignments.csv \
        --cutout-root <ruta privada>/cutouts \
        --output-root <ruta privada>/synthetic \
        --manifest <ruta privada>/scene_manifest.csv \
        --cutout-manifest <ruta>/p2_cutout_library.csv \
        --generator-commit <sha git> \
        [--pilot | --scene-id SYN_0001 ...] \
        [--background-rgb 255,255,255]
"""
import argparse
import csv
import hashlib
import io
import os
import random
import re
import sys

import numpy as np
from PIL import Image

from src.data.assign_synthetic_sources import (
    ACCEPTED_STATUS,
    TRAIN_SPLIT,
    AssignmentError,
    _read_csv_rows,
    read_assignments,
    validate_relative_path,
)
from src.data.make_boxes import compute_yolo_box

GENERATOR_VERSION = "p2-synthetic-compositor/1.0.0"

# Lienzo gobernante (06_SYNTHETIC §5)
CANVAS_WIDTH = 1280
CANVAS_HEIGHT = 1280

# Reglas de dificultad gobernantes (06_SYNTHETIC §5, 01_CONTRACT §8).
# scale: (min, max); rotation_deg: (min, max); max_occlusion: fracción máxima.
DIFFICULTY_RULES = {
    "basic": {"scale": (0.75, 1.10), "rotation": (-15.0, 15.0), "max_occlusion": 0.05},
    "medium": {"scale": (0.65, 1.10), "rotation": (-25.0, 25.0), "max_occlusion": 0.15},
    "hard": {"scale": (0.55, 1.05), "rotation": (-35.0, 35.0), "max_occlusion": 0.30},
    "extreme": {"scale": (0.45, 1.00), "rotation": (-45.0, 45.0), "max_occlusion": 0.45},
}

# Cotas de reintento (06_SYNTHETIC §6: "bounded placement retries").
MAX_SCENE_ATTEMPTS = 64
MAX_PLACEMENT_SAMPLES = 64

DEFAULT_BACKGROUND_RGB = (255, 255, 255)

# Alpha > 0 es foreground (06_SYNTHETIC §7; enunciado P2-007).
ALPHA_FOREGROUND_THRESHOLD = 0

# Piloto: 10 basic + 10 medium + 10 hard = 30, cubriendo densidades (06_SYNTHETIC §10).
PILOT_QUOTAS = (
    ("basic", 2, 5),
    ("basic", 3, 5),
    ("medium", 4, 5),
    ("medium", 5, 5),
    ("hard", 6, 4),
    ("hard", 7, 3),
    ("hard", 8, 3),
)
PILOT_SCENE_COUNT = 30

# Campos de linaje que deben ser idénticos para toda aparición de un mismo
# source_asset_id a lo largo de todo el assignments.csv (06_SYNTHETIC §4/§9).
LINEAGE_FIELDS = (
    "sku_id",
    "category",
    "metadata_status",
    "cutout_relative_path",
    "cutout_sha256",
)

MANIFEST_COLUMNS = (
    "scene_id",
    "difficulty",
    "seed",
    "planned_object_count",
    "actual_object_count",
    "placement_index",
    "source_asset_id",
    "sku_id",
    "category",
    "metadata_status",
    "cutout_sha256",
    "scale",
    "rotation_deg",
    "x",
    "y",
    "z_order",
    "transformed_area",
    "visible_area",
    "occlusion_fraction",
    "xmin",
    "ymin",
    "xmax",
    "ymax",
    "yolo_xc",
    "yolo_yc",
    "yolo_w",
    "yolo_h",
    "output_image_relative_path",
    "output_label_relative_path",
    "output_image_sha256",
    "output_label_sha256",
    "generator_version",
    "generator_commit",
)

# 7-40 hex: acepta SHA corto o completo de git. No se autodetecta nunca desde
# el cwd; siempre llega explícito por --generator-commit.
GIT_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{7,40}$")


class SceneGenerationError(RuntimeError):
    """La escena no pudo generarse cumpliendo el contrato."""


class SceneRejected(Exception):
    """Intento de escena rechazado; debe reintentarse con otro sub-seed."""


class QAError(AssertionError):
    """Una comprobación de QA automática falló."""


def validate_generator_commit(value):
    """Valida que --generator-commit sea un SHA git bien formado (7-40 hex).

    Nunca se obtiene ejecutando git en el directorio de trabajo actual: debe
    llegar explícito por CLI para que el manifiesto no quede atado en silencio
    al commit de un repositorio o worktree distinto del declarado por quien
    ejecuta la corrida.
    """
    text = (value or "").strip()
    if not GIT_SHA_PATTERN.match(text):
        raise ValueError(
            f"--generator-commit no es un SHA git válido (7-40 caracteres hex): "
            f"{value!r}"
        )
    return text.lower()


def derive_attempt_seed(scene_seed, attempt):
    """Deriva el sub-seed de un reintento a partir del seed de la escena.

    Determinista y explícita: no depende del hash de strings de Python ni del
    orden de iteración. attempt=0 es la primera generación de la escena.
    """
    return (int(scene_seed) * 1_000_003 + int(attempt) * 7_919) % (2 ** 32)


def parse_background_rgb(text):
    """Convierte "R,G,B" en una tupla de tres enteros 0..255."""
    parts = [p.strip() for p in str(text).split(",")]
    if len(parts) != 3:
        raise ValueError(f"--background-rgb debe ser 'R,G,B'; recibido: {text!r}")
    try:
        values = tuple(int(p) for p in parts)
    except ValueError as exc:
        raise ValueError(f"--background-rgb no numérico: {text!r}") from exc
    for value in values:
        if not 0 <= value <= 255:
            raise ValueError(f"--background-rgb fuera de 0..255: {text!r}")
    return values


def validate_source_lineage_consistency(rows):
    """Verifica que cada source_asset_id declare siempre el mismo linaje.

    Si el mismo source_asset_id aparece en más de un placement con sku_id,
    category, metadata_status, cutout_relative_path o cutout_sha256
    distintos, es una contradicción de procedencia y aborta la corrida
    (06_SYNTHETIC §4/§9: la procedencia debe ser exacta y única por fuente).
    """
    seen = {}
    for row in rows:
        source_id = row["source_asset_id"]
        fingerprint = tuple(row.get(field, "") for field in LINEAGE_FIELDS)
        previous = seen.get(source_id)
        if previous is not None and previous != fingerprint:
            mismatched = [
                field
                for field, before, after in zip(LINEAGE_FIELDS, previous, fingerprint)
                if before != after
            ]
            raise SceneGenerationError(
                f"source_asset_id '{source_id}' con metadata contradictoria entre "
                f"placements (campos distintos: {mismatched})"
            )
        seen[source_id] = fingerprint


def resolve_cutout_path(cutout_root, relative_path):
    """Resuelve `relative_path` dentro de `cutout_root`, con defensa en profundidad.

    Revalida la ruta (absoluta/traversal) aunque ya haya pasado por P2-006, por
    si `scene_source_assignments.csv` se editó o construyó a mano; y además
    confirma que la ruta resuelta no escapa de `cutout_root`.
    """
    validated = validate_relative_path(relative_path, "cutout_relative_path")
    root = os.path.realpath(cutout_root)
    candidate = os.path.realpath(os.path.join(cutout_root, validated))
    if os.path.commonpath([root, candidate]) != root:
        raise AssignmentError(
            f"cutout_relative_path escapa de cutout_root: {relative_path!r}"
        )
    return candidate


def group_assignments(rows):
    """Agrupa las filas de asignación por escena preservando el orden del CSV.

    Valida:
    - linaje (sku_id/category/metadata_status/ruta/hash) consistente para
      cada source_asset_id en TODO el archivo, no solo dentro de una escena;
    - difficulty/scene_seed/planned_n_products consistentes entre todos los
      placements de una misma escena (nunca se toma "el primero que llegue");
    - placement_index 0..n-1 sin huecos;
    - número de placements == planned_n_products;
    - ningún source_asset_id repetido dentro de la escena.
    """
    validate_source_lineage_consistency(rows)

    scenes = {}
    order = []
    for row in rows:
        scene_id = row["scene_id"]
        if scene_id not in scenes:
            scenes[scene_id] = {
                "scene_id": scene_id,
                "difficulty": row["difficulty"],
                "scene_seed": row["scene_seed"],
                "planned_n_products": row["planned_n_products"],
                "placements": [],
            }
            order.append(scene_id)
        else:
            scene = scenes[scene_id]
            for field in ("difficulty", "scene_seed", "planned_n_products"):
                if row[field] != scene[field]:
                    raise SceneGenerationError(
                        f"escena {scene_id}: '{field}' inconsistente entre "
                        f"placements ({scene[field]!r} vs {row[field]!r})"
                    )
        scenes[scene_id]["placements"].append(row)

    specs = []
    for scene_id in order:
        scene = scenes[scene_id]
        placements = sorted(scene["placements"], key=lambda r: r["placement_index"])
        indices = [p["placement_index"] for p in placements]
        if indices != list(range(len(placements))):
            raise SceneGenerationError(
                f"escena {scene_id}: placement_index no es 0..n-1 ({indices})"
            )
        if len(placements) != scene["planned_n_products"]:
            raise SceneGenerationError(
                f"escena {scene_id}: {len(placements)} placements para "
                f"planned_n_products={scene['planned_n_products']}"
            )
        source_ids = [p["source_asset_id"] for p in placements]
        if len(set(source_ids)) != len(source_ids):
            raise SceneGenerationError(
                f"escena {scene_id}: source_asset_id repetido dentro de la escena"
            )
        if scene["difficulty"] not in DIFFICULTY_RULES:
            raise SceneGenerationError(
                f"escena {scene_id}: dificultad desconocida '{scene['difficulty']}'"
            )
        scene["placements"] = placements
        specs.append(scene)
    return specs


def select_pilot_scenes(scene_specs):
    """Selecciona determinísticamente las 30 escenas del piloto.

    10 basic (5 con n=2, 5 con n=3), 10 medium (5 con n=4, 5 con n=5) y
    10 hard (4 con n=6, 3 con n=7, 3 con n=8). Extreme queda fuera del piloto.

    La selección toma las primeras escenas de cada combinación ordenadas por
    scene_id, así que no depende del orden de lectura del CSV.
    """
    by_bucket = {}
    for spec in scene_specs:
        key = (spec["difficulty"], spec["planned_n_products"])
        by_bucket.setdefault(key, []).append(spec)

    selected = []
    for difficulty, n_products, quota in PILOT_QUOTAS:
        bucket = sorted(
            by_bucket.get((difficulty, n_products), []), key=lambda s: s["scene_id"]
        )
        if len(bucket) < quota:
            raise SceneGenerationError(
                f"piloto: se necesitan {quota} escenas {difficulty} n={n_products}, "
                f"hay {len(bucket)}"
            )
        selected.extend(bucket[:quota])

    if len(selected) != PILOT_SCENE_COUNT:  # pragma: no cover - invariante
        raise SceneGenerationError(
            f"piloto: se seleccionaron {len(selected)} escenas, se exigen "
            f"{PILOT_SCENE_COUNT}"
        )
    return sorted(selected, key=lambda s: s["scene_id"])


def load_cutout_rgba(path):
    """Carga un cutout como array RGBA uint8 (H, W, 4)."""
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        array = np.array(rgba, dtype=np.uint8)
    if array.ndim != 3 or array.shape[2] != 4:  # pragma: no cover - convert lo garantiza
        raise SceneGenerationError(f"cutout no RGBA tras conversión: {path}")
    if array.shape[0] == 0 or array.shape[1] == 0:
        raise SceneGenerationError(f"cutout vacío: {path}")
    return array


def transform_cutout(rgba, scale, rotation_deg):
    """Escala (preservando aspect ratio) y rota el RGBA manteniendo transparencia.

    Devuelve (rgba_transformado, mask_transformada). La máscara se deriva del
    alpha YA transformado, nunca del alpha original: es la única forma de que
    área transformada y píxeles pintados coincidan.
    """
    image = Image.fromarray(rgba, mode="RGBA")
    width, height = image.size

    scaled_w = max(1, int(round(width * scale)))
    scaled_h = max(1, int(round(height * scale)))
    image = image.resize((scaled_w, scaled_h), resample=Image.BILINEAR)

    # expand=True conserva el objeto completo tras rotar; el relleno nuevo es
    # alpha=0, así que no inventa foreground.
    image = image.rotate(
        rotation_deg, resample=Image.BILINEAR, expand=True, fillcolor=(0, 0, 0, 0)
    )

    transformed = np.array(image, dtype=np.uint8)
    mask = transformed[:, :, 3] > ALPHA_FOREGROUND_THRESHOLD
    return transformed, mask


def build_canvas_mask(local_mask, x, y):
    """Pega una máscara local en un lienzo del tamaño gobernante."""
    height, width = local_mask.shape
    if x < 0 or y < 0 or x + width > CANVAS_WIDTH or y + height > CANVAS_HEIGHT:
        raise SceneRejected(
            f"objeto fuera del lienzo: ({x},{y}) {width}x{height} en "
            f"{CANVAS_WIDTH}x{CANVAS_HEIGHT}"
        )
    canvas_mask = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)
    canvas_mask[y: y + height, x: x + width] = local_mask
    return canvas_mask


def compute_visibility(canvas_masks):
    """Resuelve la visibilidad de cada objeto tras el z-order (06_SYNTHETIC §7).

    `canvas_masks` viene en orden ASCENDENTE de z_order: el último elemento es
    el que queda arriba de todos.

    Para cada objeto:
    - transformed_area = píxeles foreground de su máscara transformada, antes
      de que nada lo tape;
    - visible_mask = su máscara menos la unión de TODAS las máscaras que están
      por encima en z-order;
    - occlusion_fraction = 1 - visible_area / transformed_area.

    Devuelve una lista alineada con la entrada. La caja YOLO se deriva luego de
    `visible_mask`, nunca del rectángulo del objeto transformado.
    """
    results = [None] * len(canvas_masks)
    union_above = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)

    for index in range(len(canvas_masks) - 1, -1, -1):
        mask = canvas_masks[index]
        transformed_area = int(mask.sum())
        if transformed_area == 0:
            raise SceneRejected(f"objeto {index} sin foreground tras transformar")

        visible_mask = mask & ~union_above
        visible_area = int(visible_mask.sum())
        results[index] = {
            "transformed_area": transformed_area,
            "visible_mask": visible_mask,
            "visible_area": visible_area,
            "occlusion_fraction": 1.0 - (visible_area / transformed_area),
        }
        union_above |= mask

    return results


def enforce_occlusion_limits(visibility, max_occlusion):
    """Rechaza el intento si algún objeto queda invisible o demasiado tapado.

    Lanza SceneRejected para que la escena se regenere bajo otro sub-seed
    derivado; nunca elimina el objeto ni reduce el conteo de la escena.
    """
    for index, item in enumerate(visibility):
        if item["visible_area"] == 0:
            raise SceneRejected(f"objeto {index} totalmente oculto")
        if item["occlusion_fraction"] > max_occlusion:
            raise SceneRejected(
                f"objeto {index} con oclusión {item['occlusion_fraction']:.4f} "
                f"> {max_occlusion}"
            )


def _compose_attempt(scene_spec, cutouts, rng):
    """Un intento de composición de escena. Lanza SceneRejected si no cumple.

    Devuelve la lista de objetos colocados con su geometría y máscara visible.
    """
    rules = DIFFICULTY_RULES[scene_spec["difficulty"]]
    scale_lo, scale_hi = rules["scale"]
    rot_lo, rot_hi = rules["rotation"]
    max_occlusion = rules["max_occlusion"]

    placed = []
    for placement in scene_spec["placements"]:
        rgba = cutouts[placement["source_asset_id"]]

        # Muestreo acotado: si el objeto transformado no cabe en el lienzo se
        # vuelve a muestrear; el rng avanza, así que la secuencia sigue siendo
        # determinista para (scene_seed, attempt).
        fitted = None
        for _ in range(MAX_PLACEMENT_SAMPLES):
            scale = rng.uniform(scale_lo, scale_hi)
            rotation_deg = rng.uniform(rot_lo, rot_hi)
            transformed, mask = transform_cutout(rgba, scale, rotation_deg)
            height, width = mask.shape
            if width > CANVAS_WIDTH or height > CANVAS_HEIGHT:
                continue
            if not mask.any():
                continue
            x = rng.randint(0, CANVAS_WIDTH - width)
            y = rng.randint(0, CANVAS_HEIGHT - height)
            fitted = {
                "placement": placement,
                "scale": scale,
                "rotation_deg": rotation_deg,
                "rgba": transformed,
                "local_mask": mask,
                "x": x,
                "y": y,
                "width": width,
                "height": height,
            }
            break

        if fitted is None:
            raise SceneRejected(
                f"escena {scene_spec['scene_id']}: no se pudo encajar el objeto "
                f"{placement['placement_index']} dentro del lienzo"
            )
        placed.append(fitted)

    # z-order determinista: el orden de placement es el orden de apilado;
    # z_order mayor = más arriba.
    for z_order, obj in enumerate(placed):
        obj["z_order"] = z_order

    # Máscaras a lienzo completo, en orden ascendente de z_order.
    canvas_masks = [
        build_canvas_mask(obj["local_mask"], obj["x"], obj["y"]) for obj in placed
    ]

    visibility = compute_visibility(canvas_masks)
    enforce_occlusion_limits(visibility, max_occlusion)

    for obj, canvas_mask, item in zip(placed, canvas_masks, visibility):
        obj["canvas_mask"] = canvas_mask
        obj["transformed_area"] = item["transformed_area"]
        obj["visible_mask"] = item["visible_mask"]
        obj["visible_area"] = item["visible_area"]
        obj["occlusion_fraction"] = item["occlusion_fraction"]

    return placed


def composite_canvas(placed, background_rgb):
    """Alpha compositing de abajo hacia arriba sobre un fondo sólido.

    Conserva el RGB visible de cada cutout; no aplica ningún filtro.
    """
    canvas = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.float64)
    canvas[:, :] = np.array(background_rgb, dtype=np.float64)

    for obj in placed:  # placed ya está en orden ascendente de z_order
        x, y, w, h = obj["x"], obj["y"], obj["width"], obj["height"]
        src = obj["rgba"].astype(np.float64)
        alpha = (src[:, :, 3:4] / 255.0)
        region = canvas[y: y + h, x: x + w, :]
        canvas[y: y + h, x: x + w, :] = src[:, :, :3] * alpha + region * (1.0 - alpha)

    return np.clip(np.rint(canvas), 0, 255).astype(np.uint8)


def _sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_bytes_atomic(path, payload):
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except OSError:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        raise


def generate_scene(scene_spec, cutouts, output_root, background_rgb, generator_commit):
    """Genera una escena completa: imagen PNG, label YOLO y filas de manifiesto.

    Reintenta la escena entera bajo sub-seeds derivados hasta MAX_SCENE_ATTEMPTS.
    Nunca reduce el número de objetos: si no lo consigue, falla.
    """
    last_reason = None
    for attempt in range(MAX_SCENE_ATTEMPTS):
        rng = random.Random(derive_attempt_seed(scene_spec["scene_seed"], attempt))
        try:
            placed = _compose_attempt(scene_spec, cutouts, rng)
        except SceneRejected as exc:
            last_reason = str(exc)
            continue

        canvas = composite_canvas(placed, background_rgb)

        image_relative = f"images/{scene_spec['scene_id']}.png"
        label_relative = f"labels/{scene_spec['scene_id']}.txt"
        image_path = os.path.join(output_root, "images", f"{scene_spec['scene_id']}.png")
        label_path = os.path.join(output_root, "labels", f"{scene_spec['scene_id']}.txt")
        os.makedirs(os.path.dirname(image_path), exist_ok=True)
        os.makedirs(os.path.dirname(label_path), exist_ok=True)

        # PNG sin metadatos variables: mismos píxeles => mismos bytes.
        buffer = io.BytesIO()
        Image.fromarray(canvas, mode="RGB").save(buffer, format="PNG", optimize=False)
        _write_bytes_atomic(image_path, buffer.getvalue())

        label_lines = []
        geometry = []
        for obj in placed:
            visible_mask = obj["visible_mask"]
            yolo_line = compute_yolo_box(visible_mask, class_id=0)
            label_lines.append(yolo_line)
            _, xc, yc, bw, bh = yolo_line.split()
            ys, xs = visible_mask.nonzero()
            geometry.append({
                "xmin": int(xs.min()),
                "ymin": int(ys.min()),
                "xmax": int(xs.max()),
                "ymax": int(ys.max()),
                "yolo_xc": xc,
                "yolo_yc": yc,
                "yolo_w": bw,
                "yolo_h": bh,
            })

        if len(label_lines) != scene_spec["planned_n_products"]:  # pragma: no cover
            raise SceneGenerationError(
                f"escena {scene_spec['scene_id']}: {len(label_lines)} líneas para "
                f"{scene_spec['planned_n_products']} objetos planificados"
            )

        _write_bytes_atomic(
            label_path, ("\n".join(label_lines) + "\n").encode("utf-8")
        )

        image_sha256 = _sha256_file(image_path)
        label_sha256 = _sha256_file(label_path)

        rows = []
        for obj, geom in zip(placed, geometry):
            placement = obj["placement"]
            rows.append({
                "scene_id": scene_spec["scene_id"],
                "difficulty": scene_spec["difficulty"],
                "seed": scene_spec["scene_seed"],
                "planned_object_count": scene_spec["planned_n_products"],
                "actual_object_count": len(placed),
                "placement_index": placement["placement_index"],
                "source_asset_id": placement["source_asset_id"],
                "sku_id": placement["sku_id"],
                "category": placement["category"],
                "metadata_status": placement["metadata_status"],
                "cutout_sha256": placement["cutout_sha256"],
                "scale": f"{obj['scale']:.6f}",
                "rotation_deg": f"{obj['rotation_deg']:.6f}",
                "x": obj["x"],
                "y": obj["y"],
                "z_order": obj["z_order"],
                "transformed_area": obj["transformed_area"],
                "visible_area": obj["visible_area"],
                "occlusion_fraction": f"{obj['occlusion_fraction']:.6f}",
                "xmin": geom["xmin"],
                "ymin": geom["ymin"],
                "xmax": geom["xmax"],
                "ymax": geom["ymax"],
                "yolo_xc": geom["yolo_xc"],
                "yolo_yc": geom["yolo_yc"],
                "yolo_w": geom["yolo_w"],
                "yolo_h": geom["yolo_h"],
                "output_image_relative_path": image_relative,
                "output_label_relative_path": label_relative,
                "output_image_sha256": image_sha256,
                "output_label_sha256": label_sha256,
                "generator_version": GENERATOR_VERSION,
                "generator_commit": generator_commit,
            })
        return rows

    raise SceneGenerationError(
        f"escena {scene_spec['scene_id']}: agotados {MAX_SCENE_ATTEMPTS} intentos "
        f"sin cumplir el contrato (último rechazo: {last_reason}). "
        f"No se reduce el número de objetos."
    )


def load_train_source_allowlist(cutout_manifest_path):
    """Devuelve el conjunto de source_asset_id train aceptados del inventario.

    Se usa para el gate anti-fuga obligatorio: cualquier fuente usada en una
    escena que no esté en esta lista (o que provenga de val/test) hace fallar
    la generación. Ninguna corrida (FULL/PILOT/SELECTED) puede omitir este gate.
    """
    rows, fieldnames = _read_csv_rows(cutout_manifest_path)
    for column in ("source_asset_id", "split", "status"):
        if column not in fieldnames:
            raise QAError(
                f"cutout manifest '{cutout_manifest_path}' sin columna '{column}'"
            )
    allowed = set()
    for row in rows:
        if (row["status"] or "").strip().lower() != ACCEPTED_STATUS:
            continue
        if (row["split"] or "").strip().lower() != TRAIN_SPLIT:
            continue
        allowed.add((row["source_asset_id"] or "").strip())
    return allowed


def validate_outputs(manifest_rows, output_root, expected_scene_ids, allowed_source_ids):
    """QA automático sobre las escenas generadas (06_SYNTHETIC §11, 08_QA_GATES P2-G3).

    `allowed_source_ids` es obligatorio: el gate anti-fuga no es opcional.

    Falla (QAError) si:
    - el número de imágenes o labels no coincide con las escenas solicitadas;
    - un label no tiene exactamente planned_object_count líneas;
    - alguna coordenada YOLO cae fuera de [0,1] o w/h <= 0;
    - una fuente se repite dentro de una escena;
    - aparece una fuente que no está en la allowlist train (fuga val/test);
    - visible_area <= 0 u oclusión por encima del límite de dificultad;
    - falta el manifiesto, un hash, metadata_status o generator_commit, o el
      hash de imagen/label no coincide con el archivo en disco.
    """
    if allowed_source_ids is None:
        raise ValueError(
            "allowed_source_ids es obligatorio en validate_outputs: el gate "
            "anti-fuga no puede omitirse"
        )

    expected_scene_ids = list(expected_scene_ids)
    if not manifest_rows:
        raise QAError("manifiesto vacío: no hay evidencia de escenas generadas")

    by_scene = {}
    for row in manifest_rows:
        by_scene.setdefault(row["scene_id"], []).append(row)

    if sorted(by_scene) != sorted(expected_scene_ids):
        missing = sorted(set(expected_scene_ids) - set(by_scene))
        extra = sorted(set(by_scene) - set(expected_scene_ids))
        raise QAError(
            f"escenas del manifiesto != escenas solicitadas "
            f"(faltan={missing}, sobran={extra})"
        )

    images_dir = os.path.join(output_root, "images")
    labels_dir = os.path.join(output_root, "labels")
    image_files = sorted(
        f for f in os.listdir(images_dir) if f.lower().endswith(".png")
    ) if os.path.isdir(images_dir) else []
    label_files = sorted(
        f for f in os.listdir(labels_dir) if f.lower().endswith(".txt")
    ) if os.path.isdir(labels_dir) else []

    if len(image_files) != len(expected_scene_ids):
        raise QAError(
            f"{len(image_files)} imágenes para {len(expected_scene_ids)} escenas"
        )
    if len(label_files) != len(expected_scene_ids):
        raise QAError(
            f"{len(label_files)} labels para {len(expected_scene_ids)} escenas"
        )

    total_placements = 0
    for scene_id, rows in sorted(by_scene.items()):
        rows = sorted(rows, key=lambda r: int(r["placement_index"]))
        planned = int(rows[0]["planned_object_count"])
        difficulty = rows[0]["difficulty"].strip().lower()
        if difficulty not in DIFFICULTY_RULES:
            raise QAError(f"escena {scene_id}: dificultad desconocida '{difficulty}'")
        max_occlusion = DIFFICULTY_RULES[difficulty]["max_occlusion"]

        if len(rows) != planned:
            raise QAError(
                f"escena {scene_id}: {len(rows)} filas de manifiesto para "
                f"planned_object_count={planned}"
            )
        if int(rows[0]["actual_object_count"]) != planned:
            raise QAError(
                f"escena {scene_id}: actual_object_count "
                f"{rows[0]['actual_object_count']} != planned {planned}"
            )

        source_ids = [r["source_asset_id"] for r in rows]
        if len(set(source_ids)) != len(source_ids):
            raise QAError(f"escena {scene_id}: source_asset_id repetido en la escena")
        forbidden = sorted(set(source_ids) - set(allowed_source_ids))
        if forbidden:
            raise QAError(
                f"escena {scene_id}: fuentes fuera del split train "
                f"(posible fuga val/test): {forbidden}"
            )

        for row in rows:
            for column in (
                "output_image_sha256",
                "output_label_sha256",
                "cutout_sha256",
                "metadata_status",
                "generator_commit",
            ):
                if not (row[column] or "").strip():
                    raise QAError(f"escena {scene_id}: '{column}' vacío en manifiesto")
            for column in (
                "output_image_relative_path",
                "output_label_relative_path",
            ):
                value = row[column] or ""
                if os.path.isabs(value) or ":" in value:
                    raise QAError(
                        f"escena {scene_id}: '{column}' no es relativa ({value})"
                    )

            if int(row["visible_area"]) <= 0:
                raise QAError(f"escena {scene_id}: visible_area <= 0")
            occlusion = float(row["occlusion_fraction"])
            if occlusion > max_occlusion:
                raise QAError(
                    f"escena {scene_id}: oclusión {occlusion} > {max_occlusion} "
                    f"({difficulty})"
                )

            xc, yc = float(row["yolo_xc"]), float(row["yolo_yc"])
            bw, bh = float(row["yolo_w"]), float(row["yolo_h"])
            if bw <= 0 or bh <= 0:
                raise QAError(f"escena {scene_id}: width/height <= 0 ({bw}, {bh})")
            for name, value in (("xc", xc), ("yc", yc), ("w", bw), ("h", bh)):
                if not 0.0 <= value <= 1.0:
                    raise QAError(
                        f"escena {scene_id}: coordenada {name}={value} fuera de [0,1]"
                    )

        image_path = os.path.join(output_root, rows[0]["output_image_relative_path"])
        label_path = os.path.join(output_root, rows[0]["output_label_relative_path"])
        for path in (image_path, label_path):
            if not os.path.exists(path):
                raise QAError(f"escena {scene_id}: falta el archivo {path}")
        if _sha256_file(image_path) != rows[0]["output_image_sha256"]:
            raise QAError(f"escena {scene_id}: sha256 de imagen no coincide")
        if _sha256_file(label_path) != rows[0]["output_label_sha256"]:
            raise QAError(f"escena {scene_id}: sha256 de label no coincide")

        with open(label_path, encoding="utf-8") as handle:
            lines = [line for line in handle.read().splitlines() if line.strip()]
        if len(lines) != planned:
            raise QAError(
                f"escena {scene_id}: label con {len(lines)} líneas, se planificaron "
                f"{planned}"
            )
        for line in lines:
            parts = line.split()
            if len(parts) != 5 or parts[0] != "0":
                raise QAError(f"escena {scene_id}: línea YOLO inválida '{line}'")
            values = [float(p) for p in parts[1:]]
            if values[2] <= 0 or values[3] <= 0:
                raise QAError(f"escena {scene_id}: label con w/h <= 0")
            for value in values:
                if not 0.0 <= value <= 1.0:
                    raise QAError(
                        f"escena {scene_id}: label fuera de [0,1] en '{line}'"
                    )

        total_placements += len(rows)

    return {
        "scenes": len(by_scene),
        "images": len(image_files),
        "labels": len(label_files),
        "placements": total_placements,
    }


def write_manifest(rows, path):
    """Escribe el manifiesto de escenas, una fila por placement."""
    directory = os.path.dirname(os.path.abspath(path))
    os.makedirs(directory, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(MANIFEST_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)


def generate_scenes(
    scene_specs,
    cutout_root,
    output_root,
    allowed_source_ids,
    generator_commit,
    background_rgb=DEFAULT_BACKGROUND_RGB,
):
    """Genera todas las escenas indicadas y devuelve (filas_manifiesto, resumen QA).

    `allowed_source_ids` (gate anti-fuga) y `generator_commit` (procedencia)
    son obligatorios para toda corrida: FULL, PILOT o SELECTED. Antes de leer
    cualquier cutout se verifica su sha256 físico contra el declarado.
    """
    if allowed_source_ids is None:
        raise ValueError(
            "allowed_source_ids es obligatorio (gate anti-fuga train/accepted); "
            "ninguna corrida puede generarse sin la allowlist"
        )
    generator_commit = validate_generator_commit(generator_commit)

    all_placements = [p for spec in scene_specs for p in spec["placements"]]
    validate_source_lineage_consistency(all_placements)

    used = {p["source_asset_id"] for p in all_placements}
    forbidden = sorted(used - set(allowed_source_ids))
    if forbidden:
        raise SceneGenerationError(
            f"fuentes fuera del split train aceptado (fuga val/test): {forbidden}"
        )

    # Los cutouts se cargan una sola vez por source_asset_id, y solo tras
    # verificar que el PNG físico coincide con el cutout_sha256 declarado.
    cutouts = {}
    for placement in all_placements:
        source_id = placement["source_asset_id"]
        if source_id in cutouts:
            continue
        cutout_path = resolve_cutout_path(cutout_root, placement["cutout_relative_path"])
        if not os.path.exists(cutout_path):
            raise SceneGenerationError(f"cutout inexistente: {cutout_path}")

        actual_sha256 = _sha256_file(cutout_path)
        claimed_sha256 = placement["cutout_sha256"]
        if actual_sha256 != claimed_sha256:
            raise SceneGenerationError(
                f"cutout '{cutout_path}': sha256 físico {actual_sha256} != "
                f"cutout_sha256 declarado {claimed_sha256} "
                f"(source_asset_id={source_id})"
            )

        cutouts[source_id] = load_cutout_rgba(cutout_path)

    manifest_rows = []
    for spec in scene_specs:
        manifest_rows.extend(
            generate_scene(spec, cutouts, output_root, background_rgb, generator_commit)
        )

    summary = validate_outputs(
        manifest_rows,
        output_root,
        [s["scene_id"] for s in scene_specs],
        allowed_source_ids=allowed_source_ids,
    )
    return manifest_rows, summary


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "P2-007 — compositor determinista de escenas sintéticas multiproducto."
        )
    )
    parser.add_argument(
        "--assignments", required=True, help="CSV producido por P2-006"
    )
    parser.add_argument(
        "--cutout-root",
        required=True,
        help="raíz (privada, fuera del repo) donde viven los cutouts",
    )
    parser.add_argument(
        "--output-root",
        required=True,
        help="raíz (privada, fuera del repo) para images/ y labels/",
    )
    parser.add_argument("--manifest", required=True, help="CSV de manifiesto de escenas")
    parser.add_argument(
        "--cutout-manifest",
        required=True,
        help=(
            "inventario de cutouts; obligatorio, activa el gate anti-fuga que "
            "rechaza cualquier fuente que no sea train/accepted. Ninguna corrida "
            "(FULL/PILOT/SELECTED) puede omitirlo."
        ),
    )
    parser.add_argument(
        "--generator-commit",
        required=True,
        help=(
            "SHA git (7-40 hex) del commit que produce esta corrida. Debe "
            "llegar explícito; nunca se autodetecta ejecutando git en el cwd."
        ),
    )
    parser.add_argument(
        "--scene-id",
        action="append",
        default=None,
        help="genera solo estas escenas (repetible)",
    )
    parser.add_argument(
        "--pilot",
        action="store_true",
        help="genera solo las 30 escenas del piloto (10 basic / 10 medium / 10 hard)",
    )
    parser.add_argument(
        "--background-rgb",
        default="255,255,255",
        help="color de fondo sólido 'R,G,B' (gobernante inicial: 255,255,255)",
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)

    if args.pilot and args.scene_id:
        print("FAIL: --pilot y --scene-id son excluyentes", file=sys.stderr)
        return 1

    try:
        background_rgb = parse_background_rgb(args.background_rgb)
        generator_commit = validate_generator_commit(args.generator_commit)
        rows = read_assignments(args.assignments)
        scene_specs = group_assignments(rows)

        if args.pilot:
            scene_specs = select_pilot_scenes(scene_specs)
        elif args.scene_id:
            wanted = set(args.scene_id)
            scene_specs = [s for s in scene_specs if s["scene_id"] in wanted]
            missing = wanted - {s["scene_id"] for s in scene_specs}
            if missing:
                raise SceneGenerationError(
                    f"--scene-id no encontrado en assignments: {sorted(missing)}"
                )

        allowed_source_ids = load_train_source_allowlist(args.cutout_manifest)

        manifest_rows, summary = generate_scenes(
            scene_specs,
            args.cutout_root,
            args.output_root,
            allowed_source_ids=allowed_source_ids,
            generator_commit=generator_commit,
            background_rgb=background_rgb,
        )
        write_manifest(manifest_rows, args.manifest)
    except (SceneGenerationError, QAError, AssignmentError, ValueError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    print(f"GENERATOR_VERSION={GENERATOR_VERSION}")
    print(f"GENERATOR_COMMIT={generator_commit}")
    print(f"MODE={'PILOT' if args.pilot else 'SELECTED' if args.scene_id else 'FULL'}")
    print(f"SCENES={summary['scenes']}")
    print(f"IMAGES={summary['images']}")
    print(f"LABELS={summary['labels']}")
    print(f"PLACEMENTS={summary['placements']}")
    print("LEAKAGE_GATE=ON")
    print(f"MANIFEST={args.manifest}")
    print("QA=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
