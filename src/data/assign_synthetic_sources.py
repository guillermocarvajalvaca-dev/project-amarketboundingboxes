"""
src/data/assign_synthetic_sources.py

P2-006 — Asignación determinista de productos fuente a los placements del plan
de escenas sintéticas de Fase 2.

Contratos aplicables:
- docs/governance/03_PHASE2/01_CONTRACT_SDD_PHASE2_v2_0_0_FROZEN.md §6, §8
- docs/governance/03_PHASE2/06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md §1, §3, §4, §9
- docs/governance/03_PHASE2/11_ENRICHED_MANIFEST_SCHEMA.csv (linaje de categoría)

Reglas gobernantes:
- solo cutouts con status=accepted y split=train pueden ser fuente;
- cualquier fila accepted con split val/test es fuga de datos y aborta la corrida;
- la corrida gobernante exige exactamente 459 source_asset_id únicos;
- el plan gobernante son 655 escenas y 3287 placements;
- el orden lexicográfico de source_asset_id congela el reparto de cuotas:
  74 productos usados 8 veces y 385 usados 7 veces (derivado de divmod(3287, 459));
- ningún source_asset_id se repite dentro de una misma escena;
- la asignación es totalmente determinista: mismo input => mismo output byte a byte;
- category y metadata_status se propagan literalmente desde el cutout manifest
  (§9 del contrato de generación exige registrar categoría para análisis);
  category puede quedar vacía, pero solo si metadata_status es explícito y no vacío;
- ninguna ruta de cutout puede ser absoluta ni contener traversal ('..').

No se usa aleatoriedad en ningún punto. Las colisiones dentro de escena se
resuelven por rotación determinista de la cola (§4 del contrato de generación).

Uso:
    python -m src.data.assign_synthetic_sources \
        --scene-plan docs/governance/03_PHASE2/10_SCENE_PLAN_655.csv \
        --cutout-manifest <ruta>/p2_cutout_library.csv \
        --output <ruta>/scene_source_assignments.csv
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, deque

# Constantes gobernantes (01_CONTRACT §6, 06_SYNTHETIC §1/§4)
GOVERNING_SCENE_COUNT = 655
GOVERNING_PLACEMENT_COUNT = 3287
GOVERNING_SOURCE_COUNT = 459

ACCEPTED_STATUS = "accepted"
TRAIN_SPLIT = "train"

# category se propaga literal (puede quedar vacía); metadata_status es
# obligatorio y no vacío: es el único caso en que una categoría vacía es
# aceptable, porque queda acompañada de un estado explícito (06_SYNTHETIC §9).
REQUIRED_CUTOUT_COLUMNS = (
    "source_asset_id",
    "sku_id",
    "split",
    "category",
    "metadata_status",
    "cutout_relative_path",
    "cutout_sha256",
    "status",
)

REQUIRED_SCENE_PLAN_COLUMNS = ("scene_id", "difficulty", "n_products")

# El plan congelado nombra la columna `seed`; se acepta `scene_seed` como alias
# por si un plan futuro la renombra, pero nunca se inventa un seed ausente.
SEED_COLUMN_CANDIDATES = ("seed", "scene_seed")

ASSIGNMENT_COLUMNS = (
    "scene_id",
    "difficulty",
    "scene_seed",
    "planned_n_products",
    "placement_index",
    "source_asset_id",
    "sku_id",
    "category",
    "metadata_status",
    "cutout_relative_path",
    "cutout_sha256",
)

_DRIVE_LETTER_PATTERN = re.compile(r"^[A-Za-z]:[\\/]")


class AssignmentError(ValueError):
    """Error de asignación determinista de fuentes."""


class SplitLeakageError(AssignmentError):
    """Se detectó un cutout aceptado que no pertenece al split train."""


def validate_relative_path(value, column_name):
    """Rechaza rutas absolutas o con traversal ('..') en un campo de ruta relativa.

    Nunca se confía en una ruta declarada por un CSV para escapar de su raíz:
    ni rutas absolutas POSIX ('/...'), ni rutas con unidad Windows ('C:\\...'),
    ni segmentos '..' en ninguna posición.

    Devuelve el valor saneado (sin espacios en los extremos) si es válido.
    """
    text = (value or "").strip()
    if not text:
        raise AssignmentError(f"'{column_name}' vacío")

    if (
        os.path.isabs(text)
        or _DRIVE_LETTER_PATTERN.match(text)
        or text.startswith("/")
        or text.startswith("\\")
    ):
        raise AssignmentError(
            f"'{column_name}' no puede ser una ruta absoluta: {text!r}"
        )

    normalized = text.replace("\\", "/")
    if any(part == ".." for part in normalized.split("/")):
        raise AssignmentError(
            f"'{column_name}' no puede contener traversal '..': {text!r}"
        )

    return text


def _read_csv_rows(path):
    """Lee un CSV a lista de dicts preservando el orden del archivo."""
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise AssignmentError(f"CSV sin cabecera: {path}")
        return list(reader), list(reader.fieldnames)


def load_scene_plan(path, governing=True):
    """Carga el plan de escenas y valida su forma.

    Devuelve una lista de dicts con claves scene_id, difficulty, scene_seed y
    n_products, en el orden exacto del archivo (el orden del plan es parte del
    contrato: el generador no puede reordenar escenas).
    """
    rows, fieldnames = _read_csv_rows(path)

    missing = [c for c in REQUIRED_SCENE_PLAN_COLUMNS if c not in fieldnames]
    if missing:
        raise AssignmentError(
            f"scene plan '{path}' sin columnas requeridas: {missing}"
        )

    seed_column = next((c for c in SEED_COLUMN_CANDIDATES if c in fieldnames), None)
    if seed_column is None:
        raise AssignmentError(
            f"scene plan '{path}' sin columna de seed "
            f"(se esperaba una de {list(SEED_COLUMN_CANDIDATES)})"
        )

    plan = []
    seen_ids = set()
    for lineno, row in enumerate(rows, start=2):
        scene_id = (row["scene_id"] or "").strip()
        if not scene_id:
            raise AssignmentError(f"scene plan línea {lineno}: scene_id vacío")
        if scene_id in seen_ids:
            raise AssignmentError(f"scene plan: scene_id duplicado '{scene_id}'")
        seen_ids.add(scene_id)

        try:
            n_products = int(row["n_products"])
            scene_seed = int(row[seed_column])
        except (TypeError, ValueError) as exc:
            raise AssignmentError(
                f"scene plan línea {lineno}: n_products/seed no enteros ({exc})"
            ) from exc

        if n_products <= 0:
            raise AssignmentError(
                f"scene plan línea {lineno}: n_products debe ser >0, es {n_products}"
            )

        plan.append({
            "scene_id": scene_id,
            "difficulty": (row["difficulty"] or "").strip().lower(),
            "scene_seed": scene_seed,
            "n_products": n_products,
        })

    if governing:
        if len(plan) != GOVERNING_SCENE_COUNT:
            raise AssignmentError(
                f"modo gobernante: se exigen {GOVERNING_SCENE_COUNT} escenas, "
                f"el plan trae {len(plan)}"
            )
        total = sum(s["n_products"] for s in plan)
        if total != GOVERNING_PLACEMENT_COUNT:
            raise AssignmentError(
                f"modo gobernante: se exigen {GOVERNING_PLACEMENT_COUNT} placements, "
                f"el plan suma {total}"
            )

    return plan


def load_cutout_library(path, governing=True):
    """Carga el manifiesto de cutouts y devuelve las fuentes elegibles.

    Filtra status!=accepted. Entre las aceptadas, cualquier split distinto de
    train es fuga (01_CONTRACT §4/§13) y aborta: no se descarta en silencio.

    category se preserva literal (nunca se inventa); metadata_status es
    obligatorio y no vacío — es la única forma en que una categoría vacía
    queda justificada (06_SYNTHETIC §9). cutout_relative_path se valida contra
    rutas absolutas y traversal.

    Devuelve un dict source_asset_id -> fila, y el conteo de descartes por status.
    """
    rows, fieldnames = _read_csv_rows(path)

    missing = [c for c in REQUIRED_CUTOUT_COLUMNS if c not in fieldnames]
    if missing:
        raise AssignmentError(
            f"cutout manifest '{path}' sin columnas requeridas: {missing}"
        )

    sources = {}
    skipped_not_accepted = 0
    for lineno, row in enumerate(rows, start=2):
        status = (row["status"] or "").strip().lower()
        if status != ACCEPTED_STATUS:
            skipped_not_accepted += 1
            continue

        split = (row["split"] or "").strip().lower()
        if split != TRAIN_SPLIT:
            raise SplitLeakageError(
                f"cutout manifest línea {lineno}: cutout aceptado con split='{split}' "
                f"(source_asset_id={row['source_asset_id']}). Solo se admite train; "
                f"val/test no pueden ser fuente sintética."
            )

        source_asset_id = (row["source_asset_id"] or "").strip()
        if not source_asset_id:
            raise AssignmentError(
                f"cutout manifest línea {lineno}: source_asset_id vacío"
            )
        if source_asset_id in sources:
            raise AssignmentError(
                f"cutout manifest: source_asset_id duplicado '{source_asset_id}'"
            )

        for column in ("cutout_sha256", "sku_id"):
            if not (row[column] or "").strip():
                raise AssignmentError(
                    f"cutout manifest línea {lineno}: '{column}' vacío para "
                    f"{source_asset_id}"
                )

        cutout_relative_path = validate_relative_path(
            row["cutout_relative_path"], "cutout_relative_path"
        )

        metadata_status = (row["metadata_status"] or "").strip()
        if not metadata_status:
            raise AssignmentError(
                f"cutout manifest línea {lineno}: 'metadata_status' vacío para "
                f"{source_asset_id} (una categoría vacía solo se permite "
                f"acompañada de un estado de metadata explícito)"
            )
        # category se preserva literal; puede quedar vacía si metadata_status
        # (ya verificado no vacío arriba) documenta por qué.
        category = (row["category"] or "").strip()

        sources[source_asset_id] = {
            "source_asset_id": source_asset_id,
            "sku_id": row["sku_id"].strip(),
            "category": category,
            "metadata_status": metadata_status,
            "cutout_relative_path": cutout_relative_path,
            "cutout_sha256": row["cutout_sha256"].strip(),
        }

    if governing and len(sources) != GOVERNING_SOURCE_COUNT:
        raise AssignmentError(
            f"modo gobernante: se exigen exactamente {GOVERNING_SOURCE_COUNT} "
            f"source_asset_id train aceptados, hay {len(sources)}"
        )

    if not sources:
        raise AssignmentError(f"cutout manifest '{path}': ninguna fuente elegible")

    return sources, skipped_not_accepted


def compute_usage_quotas(ordered_source_ids, total_placements):
    """Reparte `total_placements` entre las fuentes de forma determinista.

    base, remainder = divmod(total_placements, n_sources). Las primeras
    `remainder` fuentes del orden lexicográfico reciben base+1 y el resto base.

    Para la corrida gobernante (3287, 459) esto produce exactamente la regla
    del contrato: 74 fuentes con 8 usos y 385 con 7. La regla no está
    hardcodeada: se deriva del plan y del inventario.
    """
    n_sources = len(ordered_source_ids)
    if n_sources == 0:
        raise AssignmentError("no hay fuentes para repartir cuotas")

    base, remainder = divmod(total_placements, n_sources)
    return {
        source_id: base + (1 if index < remainder else 0)
        for index, source_id in enumerate(ordered_source_ids)
    }


def build_placement_queue(ordered_source_ids, quotas):
    """Construye la cola de placements en pasadas completas.

    La pasada p incluye toda fuente cuya cuota sea > p, en orden lexicográfico.
    Con cuotas 8/7 esto da 7 pasadas de 459 más una pasada final de 74: cada
    uso de una fuente queda separado del anterior por ~459 posiciones, así que
    las colisiones dentro de escena (máximo 15 objetos) son estructuralmente
    improbables y, si aparecen, se resuelven por rotación.
    """
    max_quota = max(quotas.values())
    queue = []
    for pass_index in range(max_quota):
        for source_id in ordered_source_ids:
            if quotas[source_id] > pass_index:
                queue.append(source_id)
    return queue


def assign_sources(scene_plan, sources, governing=True):
    """Asigna fuentes a cada placement de cada escena, de forma determinista.

    Recorre el plan en su orden congelado y consume la cola de placements. Si
    la fuente en cabeza ya se usó en la escena actual, se difiere: se aparta y
    se reinserta al frente de la cola para la siguiente escena (rotación
    determinista, §4 del contrato de generación). Ninguna cuota se pierde.
    """
    ordered_source_ids = sorted(sources)
    total_placements = sum(scene["n_products"] for scene in scene_plan)

    quotas = compute_usage_quotas(ordered_source_ids, total_placements)
    queue = deque(build_placement_queue(ordered_source_ids, quotas))

    if len(queue) != total_placements:  # pragma: no cover - invariante
        raise AssignmentError(
            f"cola de {len(queue)} entradas para {total_placements} placements"
        )

    assignments = []
    for scene in scene_plan:
        n_products = scene["n_products"]
        if n_products > len(ordered_source_ids):
            raise AssignmentError(
                f"escena {scene['scene_id']} pide {n_products} fuentes distintas "
                f"pero solo hay {len(ordered_source_ids)} disponibles"
            )

        chosen = []
        chosen_set = set()
        deferred = []
        # Cota dura: no se inspecciona la cola más de una vuelta completa.
        max_scans = len(queue)
        scans = 0
        while len(chosen) < n_products:
            if not queue or scans >= max_scans:
                raise AssignmentError(
                    f"escena {scene['scene_id']}: cola agotada sin poder completar "
                    f"{n_products} fuentes distintas"
                )
            candidate = queue.popleft()
            scans += 1
            if candidate in chosen_set:
                deferred.append(candidate)
            else:
                chosen.append(candidate)
                chosen_set.add(candidate)

        # Los diferidos vuelven al frente conservando su orden relativo.
        queue.extendleft(reversed(deferred))

        for placement_index, source_id in enumerate(chosen):
            source = sources[source_id]
            assignments.append({
                "scene_id": scene["scene_id"],
                "difficulty": scene["difficulty"],
                "scene_seed": scene["scene_seed"],
                "planned_n_products": n_products,
                "placement_index": placement_index,
                "source_asset_id": source_id,
                "sku_id": source["sku_id"],
                "category": source["category"],
                "metadata_status": source["metadata_status"],
                "cutout_relative_path": source["cutout_relative_path"],
                "cutout_sha256": source["cutout_sha256"],
            })

    if queue:  # pragma: no cover - invariante
        raise AssignmentError(f"quedaron {len(queue)} placements sin asignar")

    validate_assignments(assignments, scene_plan, quotas, governing=governing)
    return assignments


def validate_assignments(assignments, scene_plan, quotas, governing=True):
    """Verifica las invariantes contractuales sobre la asignación producida."""
    expected_rows = sum(scene["n_products"] for scene in scene_plan)
    if len(assignments) != expected_rows:
        raise AssignmentError(
            f"se esperaban {expected_rows} placements, hay {len(assignments)}"
        )

    per_scene = {}
    for row in assignments:
        per_scene.setdefault(row["scene_id"], []).append(row)

    if len(per_scene) != len(scene_plan):
        raise AssignmentError(
            f"se esperaban {len(scene_plan)} escenas asignadas, hay {len(per_scene)}"
        )

    for scene in scene_plan:
        rows = per_scene[scene["scene_id"]]
        if len(rows) != scene["n_products"]:
            raise AssignmentError(
                f"escena {scene['scene_id']}: {len(rows)} placements, "
                f"se planificaron {scene['n_products']}"
            )
        source_ids = [r["source_asset_id"] for r in rows]
        if len(set(source_ids)) != len(source_ids):
            duplicated = sorted(s for s, c in Counter(source_ids).items() if c > 1)
            raise AssignmentError(
                f"escena {scene['scene_id']}: source_asset_id repetido {duplicated}"
            )
        if [r["placement_index"] for r in rows] != list(range(len(rows))):
            raise AssignmentError(
                f"escena {scene['scene_id']}: placement_index no es 0..n-1"
            )

    usage = Counter(row["source_asset_id"] for row in assignments)
    for source_id, expected in quotas.items():
        if usage[source_id] != expected:
            raise AssignmentError(
                f"fuente {source_id}: {usage[source_id]} usos, se esperaban {expected}"
            )

    if governing:
        frequency_histogram = Counter(usage.values())
        if frequency_histogram != Counter({7: 385, 8: 74}):
            raise AssignmentError(
                "modo gobernante: la distribución de uso debe ser 74x8 + 385x7, "
                f"se obtuvo {dict(frequency_histogram)}"
            )
        if len(assignments) != GOVERNING_PLACEMENT_COUNT:
            raise AssignmentError(
                f"modo gobernante: se exigen {GOVERNING_PLACEMENT_COUNT} placements"
            )


def write_assignments(assignments, path):
    """Escribe el CSV long-form, una fila por placement.

    lineterminator="\\n" fija los bytes de salida en cualquier plataforma: el
    contrato exige que la misma entrada produzca el mismo archivo byte a byte.
    """
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=list(ASSIGNMENT_COLUMNS), lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(assignments)


def read_assignments(path):
    """Relee el CSV de asignaciones tipando los campos numéricos.

    Lo usa el compositor P2-007 para no reinterpretar el esquema por su cuenta.
    Exige category y metadata_status: un assignments.csv producido por una
    versión anterior de P2-006 (sin esas columnas) se rechaza explícitamente
    en vez de generar escenas sin linaje de categoría.
    """
    rows, fieldnames = _read_csv_rows(path)
    missing = [c for c in ASSIGNMENT_COLUMNS if c not in fieldnames]
    if missing:
        raise AssignmentError(
            f"assignments '{path}' sin columnas requeridas: {missing}"
        )

    parsed = []
    for lineno, row in enumerate(rows, start=2):
        try:
            row = dict(row)
            row["scene_seed"] = int(row["scene_seed"])
            row["planned_n_products"] = int(row["planned_n_products"])
            row["placement_index"] = int(row["placement_index"])
        except (TypeError, ValueError) as exc:
            raise AssignmentError(
                f"assignments línea {lineno}: campo numérico inválido ({exc})"
            ) from exc
        row["difficulty"] = row["difficulty"].strip().lower()
        parsed.append(row)
    return parsed


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "P2-006 — asignación determinista de cutouts train a los placements "
            "del plan de escenas sintéticas."
        )
    )
    parser.add_argument("--scene-plan", required=True, help="CSV del plan de escenas")
    parser.add_argument(
        "--cutout-manifest", required=True, help="CSV del inventario de cutouts"
    )
    parser.add_argument("--output", required=True, help="CSV de salida (long-form)")
    parser.add_argument(
        "--non-governing",
        action="store_true",
        help=(
            "relaja los conteos exactos (655/3287/459). Solo para pruebas y "
            "exploración: la corrida gobernante NO debe usar este flag."
        ),
    )
    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    governing = not args.non_governing

    try:
        scene_plan = load_scene_plan(args.scene_plan, governing=governing)
        sources, skipped = load_cutout_library(
            args.cutout_manifest, governing=governing
        )
        assignments = assign_sources(scene_plan, sources, governing=governing)
        write_assignments(assignments, args.output)
    except AssignmentError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1

    usage = Counter(row["source_asset_id"] for row in assignments)
    histogram = Counter(usage.values())
    print(f"MODE={'GOVERNING' if governing else 'NON_GOVERNING'}")
    print(f"SCENES={len(scene_plan)}")
    print(f"SOURCES={len(sources)}")
    print(f"SKIPPED_NOT_ACCEPTED={skipped}")
    print(f"ROWS={len(assignments)}")
    print(
        "USAGE_HISTOGRAM="
        + "+".join(f"{count}x{freq}" for freq, count in sorted(histogram.items()))
    )
    print(f"OUTPUT={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
