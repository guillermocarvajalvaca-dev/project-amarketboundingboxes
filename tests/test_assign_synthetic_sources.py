"""
Tests P2-006 para src/data/assign_synthetic_sources.py

Cubren las reglas gobernantes de
docs/governance/03_PHASE2/06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md §1/§3/§4/§9:
459 fuentes train, 655 escenas, 3287 placements, reparto 74x8 + 385x7,
sin repetición dentro de escena, linaje de categoría propagado y con salida
byte a byte reproducible.

Los fixtures se generan programáticamente: no se usa ninguna imagen ni
manifiesto real de AMARKET.
"""
import csv
import hashlib

import pytest

from src.data.assign_synthetic_sources import (
    GOVERNING_PLACEMENT_COUNT,
    GOVERNING_SCENE_COUNT,
    GOVERNING_SOURCE_COUNT,
    AssignmentError,
    SplitLeakageError,
    assign_sources,
    compute_usage_quotas,
    load_cutout_library,
    load_scene_plan,
    main,
    validate_relative_path,
    write_assignments,
)

CUTOUT_COLUMNS = [
    "source_asset_id",
    "sku_id",
    "split",
    "category",
    "metadata_status",
    "cutout_relative_path",
    "cutout_sha256",
    "status",
]

# Distribución gobernante del plan congelado (01_CONTRACT §6): 655 escenas,
# 3287 placements. Se reconstruye aquí para no depender del archivo FROZEN.
GOVERNING_DISTRIBUTION = [
    ("basic", 2, 110),
    ("basic", 3, 110),
    ("medium", 4, 110),
    ("medium", 5, 110),
    ("hard", 6, 50),
    ("hard", 7, 50),
    ("hard", 8, 50),
    ("extreme", 9, 20),
    ("extreme", 10, 15),
    ("extreme", 11, 10),
    ("extreme", 12, 10),
    ("extreme", 13, 5),
    ("extreme", 14, 3),
    ("extreme", 15, 2),
]

CATEGORIES = ("beverages", "snacks", "dairy", "cleaning", "personal_care")


def fake_source_id(index):
    """ID sintético con la forma sha256 de los assets reales, sin serlo."""
    return hashlib.sha256(f"fixture-source-{index}".encode()).hexdigest()


def write_scene_plan(path, specs, seed_column="seed"):
    """specs: lista de (difficulty, n_products) en orden de escena."""
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["scene_id", "difficulty", "n_products", seed_column, "status"])
        for index, (difficulty, n_products) in enumerate(specs, start=1):
            writer.writerow(
                [f"SYN_{index:04d}", difficulty, n_products, 42000 + index, "PLANNED"]
            )
    return path


def governing_scene_specs():
    specs = []
    for difficulty, n_products, count in GOVERNING_DISTRIBUTION:
        specs.extend([(difficulty, n_products)] * count)
    return specs


def write_cutout_manifest(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CUTOUT_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return path


def cutout_rows(count, split="train", status="accepted", start=0, category=None):
    """Filas de cutout manifest con category/metadata_status siempre presentes.

    category=None hace que cada fila reciba una categoría determinista de
    CATEGORIES (nunca vacía); pasar category="" simula explícitamente el caso
    de categoría vacía con metadata_status igualmente explícito.
    """
    rows = []
    for index in range(start, start + count):
        source_id = fake_source_id(index)
        row_category = CATEGORIES[index % len(CATEGORIES)] if category is None else category
        rows.append({
            "source_asset_id": source_id,
            "sku_id": f"SKU{index:05d}",
            "split": split,
            "category": row_category,
            "metadata_status": "ok",
            "cutout_relative_path": f"cutouts/{source_id}.png",
            "cutout_sha256": hashlib.sha256(f"cut-{index}".encode()).hexdigest(),
            "status": status,
        })
    return rows


@pytest.fixture
def governing_plan(tmp_path):
    return write_scene_plan(
        str(tmp_path / "scene_plan.csv"), governing_scene_specs()
    )


@pytest.fixture
def governing_manifest(tmp_path):
    return write_cutout_manifest(
        str(tmp_path / "cutouts.csv"), cutout_rows(GOVERNING_SOURCE_COUNT)
    )


def test_459_train_aceptados(governing_manifest):
    """459 fuentes train/accepted son admitidas en modo gobernante."""
    sources, skipped = load_cutout_library(governing_manifest, governing=True)
    assert len(sources) == GOVERNING_SOURCE_COUNT
    assert skipped == 0


def test_split_val_rechazado(tmp_path):
    """Un cutout aceptado con split=val es fuga y aborta la corrida."""
    rows = cutout_rows(GOVERNING_SOURCE_COUNT - 1)
    rows.extend(cutout_rows(1, split="val", start=10_000))
    path = write_cutout_manifest(str(tmp_path / "with_val.csv"), rows)

    with pytest.raises(SplitLeakageError, match="split='val'"):
        load_cutout_library(path, governing=True)


def test_split_test_rechazado(tmp_path):
    """Un cutout aceptado con split=test es fuga y aborta la corrida."""
    rows = cutout_rows(GOVERNING_SOURCE_COUNT - 1)
    rows.extend(cutout_rows(1, split="test", start=20_000))
    path = write_cutout_manifest(str(tmp_path / "with_test.csv"), rows)

    with pytest.raises(SplitLeakageError, match="split='test'"):
        load_cutout_library(path, governing=True)


def test_status_no_accepted_se_descarta_sin_fallar(tmp_path):
    """Las filas rejected no son fuente, pero no abortan: solo se cuentan."""
    rows = cutout_rows(GOVERNING_SOURCE_COUNT)
    rows.extend(cutout_rows(3, status="rejected", start=30_000))
    path = write_cutout_manifest(str(tmp_path / "with_rejected.csv"), rows)

    sources, skipped = load_cutout_library(path, governing=True)
    assert len(sources) == GOVERNING_SOURCE_COUNT
    assert skipped == 3


def test_menos_de_459_falla_en_modo_gobernante(tmp_path):
    """458 fuentes no bastan para la corrida gobernante."""
    path = write_cutout_manifest(
        str(tmp_path / "short.csv"), cutout_rows(GOVERNING_SOURCE_COUNT - 1)
    )
    with pytest.raises(AssignmentError, match="exactamente 459"):
        load_cutout_library(path, governing=True)


def test_scene_plan_655_escenas(governing_plan):
    plan = load_scene_plan(governing_plan, governing=True)
    assert len(plan) == GOVERNING_SCENE_COUNT
    assert sum(s["n_products"] for s in plan) == GOVERNING_PLACEMENT_COUNT


def test_scene_plan_distinto_de_655_falla(tmp_path):
    path = write_scene_plan(
        str(tmp_path / "short_plan.csv"), governing_scene_specs()[:10]
    )
    with pytest.raises(AssignmentError, match="655 escenas"):
        load_scene_plan(path, governing=True)


def test_cuotas_gobernantes_son_74x8_mas_385x7():
    """La regla del contrato se deriva de divmod(3287, 459), no se hardcodea."""
    ordered = sorted(fake_source_id(i) for i in range(GOVERNING_SOURCE_COUNT))
    quotas = compute_usage_quotas(ordered, GOVERNING_PLACEMENT_COUNT)

    assert sum(quotas.values()) == GOVERNING_PLACEMENT_COUNT
    assert sum(1 for q in quotas.values() if q == 8) == 74
    assert sum(1 for q in quotas.values() if q == 7) == 385
    # Los 8 usos van a los 74 primeros IDs del orden lexicográfico congelado.
    assert all(quotas[source_id] == 8 for source_id in ordered[:74])
    assert all(quotas[source_id] == 7 for source_id in ordered[74:])


@pytest.fixture
def governing_assignments(governing_plan, governing_manifest):
    plan = load_scene_plan(governing_plan, governing=True)
    sources, _ = load_cutout_library(governing_manifest, governing=True)
    return plan, sources, assign_sources(plan, sources, governing=True)


def test_placement_count_3287(governing_assignments):
    _, _, assignments = governing_assignments
    assert len(assignments) == GOVERNING_PLACEMENT_COUNT


def test_frecuencias_74x8_y_385x7(governing_assignments):
    from collections import Counter

    _, _, assignments = governing_assignments
    usage = Counter(row["source_asset_id"] for row in assignments)
    histogram = Counter(usage.values())
    assert histogram == Counter({8: 74, 7: 385})


def test_sin_duplicados_dentro_de_escena(governing_assignments):
    _, _, assignments = governing_assignments
    per_scene = {}
    for row in assignments:
        per_scene.setdefault(row["scene_id"], []).append(row["source_asset_id"])

    duplicated = {
        scene_id: ids
        for scene_id, ids in per_scene.items()
        if len(set(ids)) != len(ids)
    }
    assert duplicated == {}


def test_escenas_completas_y_ordenadas(governing_assignments):
    plan, _, assignments = governing_assignments
    per_scene = {}
    for row in assignments:
        per_scene.setdefault(row["scene_id"], []).append(row)

    assert len(per_scene) == GOVERNING_SCENE_COUNT
    for scene in plan:
        rows = per_scene[scene["scene_id"]]
        assert len(rows) == scene["n_products"]
        assert [r["placement_index"] for r in rows] == list(range(scene["n_products"]))


def test_ejecucion_repetida_es_identica(governing_plan, governing_manifest, tmp_path):
    """Mismo input => mismo archivo byte a byte (contrato de determinismo)."""
    outputs = []
    for run in range(2):
        plan = load_scene_plan(governing_plan, governing=True)
        sources, _ = load_cutout_library(governing_manifest, governing=True)
        assignments = assign_sources(plan, sources, governing=True)
        out_path = tmp_path / f"assignments_{run}.csv"
        write_assignments(assignments, str(out_path))
        outputs.append(out_path.read_bytes())

    assert outputs[0] == outputs[1]
    assert hashlib.sha256(outputs[0]).hexdigest() == hashlib.sha256(
        outputs[1]
    ).hexdigest()


def test_cli_end_to_end(governing_plan, governing_manifest, tmp_path, capsys):
    out_path = tmp_path / "scene_source_assignments.csv"
    exit_code = main([
        "--scene-plan", governing_plan,
        "--cutout-manifest", governing_manifest,
        "--output", str(out_path),
    ])
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "ROWS=3287" in captured
    assert "USAGE_HISTOGRAM=385x7+74x8" in captured

    with open(out_path, newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == GOVERNING_PLACEMENT_COUNT
    assert rows[0]["scene_id"] == "SYN_0001"


def test_cli_falla_con_manifiesto_incompleto(governing_plan, tmp_path, capsys):
    short_manifest = write_cutout_manifest(
        str(tmp_path / "short.csv"), cutout_rows(100)
    )
    exit_code = main([
        "--scene-plan", governing_plan,
        "--cutout-manifest", short_manifest,
        "--output", str(tmp_path / "out.csv"),
    ])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err


def test_modo_no_gobernante_permite_inventario_pequeno(tmp_path):
    """Con --non-governing se puede probar con pocos assets y pocas escenas."""
    plan_path = write_scene_plan(
        str(tmp_path / "small_plan.csv"),
        [("basic", 2), ("basic", 3), ("medium", 4)],
    )
    manifest_path = write_cutout_manifest(
        str(tmp_path / "small_cutouts.csv"), cutout_rows(6)
    )

    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)

    assert len(assignments) == 9
    per_scene = {}
    for row in assignments:
        per_scene.setdefault(row["scene_id"], []).append(row["source_asset_id"])
    for ids in per_scene.values():
        assert len(set(ids)) == len(ids)


def test_escena_pide_mas_fuentes_de_las_disponibles(tmp_path):
    """Nunca se reduce el número de objetos: se falla en voz alta."""
    plan_path = write_scene_plan(str(tmp_path / "plan.csv"), [("extreme", 9)])
    manifest_path = write_cutout_manifest(
        str(tmp_path / "cutouts.csv"), cutout_rows(4)
    )
    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)

    with pytest.raises(AssignmentError, match="fuentes distintas"):
        assign_sources(plan, sources, governing=False)


def test_manifiesto_sin_columnas_requeridas(tmp_path):
    path = tmp_path / "bad.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["source_asset_id", "sku_id"])
        writer.writerow(["a", "b"])

    with pytest.raises(AssignmentError, match="sin columnas requeridas"):
        load_cutout_library(str(path), governing=False)


def test_scene_plan_acepta_alias_scene_seed(tmp_path):
    path = write_scene_plan(
        str(tmp_path / "alias.csv"), [("basic", 2)], seed_column="scene_seed"
    )
    plan = load_scene_plan(path, governing=False)
    assert plan[0]["scene_seed"] == 42001


# --------------------------------------------------------------------------
# Linaje de categoría y metadata_status (auditoría CHANGES_REQUIRED, punto 1)
# --------------------------------------------------------------------------

def test_manifiesto_sin_columna_category_falla(tmp_path):
    """category y metadata_status son columnas obligatorias del esquema gobernante."""
    columns = [c for c in CUTOUT_COLUMNS if c != "category"]
    path = tmp_path / "no_category.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        row = cutout_rows(1)[0]
        del row["category"]
        writer.writerow(row)

    with pytest.raises(AssignmentError, match="sin columnas requeridas"):
        load_cutout_library(str(path), governing=False)


def test_manifiesto_sin_columna_metadata_status_falla(tmp_path):
    columns = [c for c in CUTOUT_COLUMNS if c != "metadata_status"]
    path = tmp_path / "no_metadata_status.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, lineterminator="\n")
        writer.writeheader()
        row = cutout_rows(1)[0]
        del row["metadata_status"]
        writer.writerow(row)

    with pytest.raises(AssignmentError, match="sin columnas requeridas"):
        load_cutout_library(str(path), governing=False)


def test_metadata_status_vacio_falla(tmp_path):
    """metadata_status vacío no se tolera aunque category tenga un valor."""
    rows = cutout_rows(1)
    rows[0]["metadata_status"] = ""
    path = write_cutout_manifest(str(tmp_path / "empty_status.csv"), rows)

    with pytest.raises(AssignmentError, match="metadata_status"):
        load_cutout_library(str(path), governing=False)


def test_categoria_vacia_permitida_con_metadata_status_explicito(tmp_path):
    """category vacía es válida SOLO si metadata_status es explícito y no vacío."""
    rows = cutout_rows(1, category="")
    rows[0]["metadata_status"] = "missing"
    path = write_cutout_manifest(str(tmp_path / "empty_category.csv"), rows)

    sources, _ = load_cutout_library(str(path), governing=False)
    source = next(iter(sources.values()))
    assert source["category"] == ""
    assert source["metadata_status"] == "missing"


def test_categoria_no_se_inventa_se_preserva_literal(tmp_path):
    """El valor de category se copia tal cual, sin normalizarlo ni inventarlo."""
    rows = cutout_rows(1, category="Bebidas / Refrescos")
    path = write_cutout_manifest(str(tmp_path / "literal_category.csv"), rows)

    sources, _ = load_cutout_library(str(path), governing=False)
    source = next(iter(sources.values()))
    assert source["category"] == "Bebidas / Refrescos"


def test_categoria_y_metadata_status_se_propagan_a_assignments(tmp_path):
    """P2-006 propaga category/metadata_status desde el cutout manifest a cada fila."""
    plan_path = write_scene_plan(str(tmp_path / "plan.csv"), [("basic", 2)])
    manifest_rows = cutout_rows(4)
    manifest_rows[0]["category"] = "beverages"
    manifest_rows[0]["metadata_status"] = "ok"
    manifest_rows[1]["category"] = ""
    manifest_rows[1]["metadata_status"] = "missing"
    manifest_path = write_cutout_manifest(str(tmp_path / "cutouts.csv"), manifest_rows)

    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)

    for row in assignments:
        source = sources[row["source_asset_id"]]
        assert row["category"] == source["category"]
        assert row["metadata_status"] == source["metadata_status"]
        assert row["metadata_status"] != ""


def test_write_assignments_incluye_columnas_de_linaje(tmp_path):
    plan_path = write_scene_plan(str(tmp_path / "plan.csv"), [("basic", 2)])
    manifest_path = write_cutout_manifest(
        str(tmp_path / "cutouts.csv"), cutout_rows(4)
    )
    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)

    out_path = tmp_path / "assignments.csv"
    write_assignments(assignments, str(out_path))

    with open(out_path, newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))
    assert "category" in header
    assert "metadata_status" in header


# --------------------------------------------------------------------------
# Integridad de rutas (auditoría CHANGES_REQUIRED, punto 5)
# --------------------------------------------------------------------------

def test_validate_relative_path_acepta_ruta_relativa_normal():
    assert validate_relative_path("cutouts/abc123.png", "cutout_relative_path") == (
        "cutouts/abc123.png"
    )


def test_validate_relative_path_rechaza_ruta_absoluta_posix():
    with pytest.raises(AssignmentError, match="absoluta"):
        validate_relative_path("/etc/passwd", "cutout_relative_path")


def test_validate_relative_path_rechaza_ruta_absoluta_windows():
    with pytest.raises(AssignmentError, match="absoluta"):
        validate_relative_path("C:\\Windows\\System32\\evil.png", "cutout_relative_path")


def test_validate_relative_path_rechaza_traversal():
    with pytest.raises(AssignmentError, match="traversal"):
        validate_relative_path("../../etc/passwd", "cutout_relative_path")


def test_validate_relative_path_rechaza_traversal_interno():
    with pytest.raises(AssignmentError, match="traversal"):
        validate_relative_path("cutouts/../../secret.png", "cutout_relative_path")


def test_cutout_relative_path_absoluta_en_manifiesto_falla(tmp_path):
    rows = cutout_rows(1)
    rows[0]["cutout_relative_path"] = "/etc/passwd"
    path = write_cutout_manifest(str(tmp_path / "absolute.csv"), rows)

    with pytest.raises(AssignmentError, match="absoluta"):
        load_cutout_library(str(path), governing=False)


def test_cutout_relative_path_con_traversal_en_manifiesto_falla(tmp_path):
    rows = cutout_rows(1)
    rows[0]["cutout_relative_path"] = "../../outside.png"
    path = write_cutout_manifest(str(tmp_path / "traversal.csv"), rows)

    with pytest.raises(AssignmentError, match="traversal"):
        load_cutout_library(str(path), governing=False)
