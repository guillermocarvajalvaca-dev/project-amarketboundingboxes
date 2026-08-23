"""
Tests P2-007 para src/data/make_synthetic_scenes.py

Cubren geometría de oclusión, semántica de caja visible, determinismo por seed,
rangos de transformación por dificultad, gates anti-fuga obligatorios,
integridad de hash de cutout, integridad de rutas, consistencia de linaje y
el piloto de 30 escenas, según
docs/governance/03_PHASE2/06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md §5-§11.

TODOS los cutouts son fixtures RGBA construidos programáticamente en directorios
temporales. No se usa ninguna imagen real de AMARKET ni se versiona ninguna
imagen en el repositorio.
"""
import csv
import hashlib
import os

import numpy as np
import pytest
from PIL import Image

from src.data.assign_synthetic_sources import (
    AssignmentError,
    assign_sources,
    load_cutout_library,
    load_scene_plan,
    write_assignments,
)
from src.data.make_boxes import compute_yolo_box
from src.data.make_synthetic_scenes import (
    CANVAS_HEIGHT,
    CANVAS_WIDTH,
    DIFFICULTY_RULES,
    PILOT_SCENE_COUNT,
    MANIFEST_COLUMNS,
    QAError,
    SceneGenerationError,
    SceneRejected,
    build_canvas_mask,
    compute_visibility,
    derive_attempt_seed,
    enforce_occlusion_limits,
    generate_scenes,
    group_assignments,
    load_train_source_allowlist,
    main,
    parse_background_rgb,
    resolve_cutout_path,
    select_pilot_scenes,
    transform_cutout,
    validate_generator_commit,
    validate_outputs,
    validate_source_lineage_consistency,
    write_manifest,
)
from tests.test_assign_synthetic_sources import (
    cutout_rows,
    write_cutout_manifest,
    write_scene_plan,
)

# SHA git fijo de fixture: nunca se autodetecta desde el repositorio real.
FIXTURE_GENERATOR_COMMIT = "0123456789abcdef0123456789abcdef01234567"


# --------------------------------------------------------------------------
# Fixtures RGBA programáticos
# --------------------------------------------------------------------------

def make_rgba_rectangle(width, height, rgb=(200, 30, 40)):
    """Rectángulo RGBA totalmente opaco: alpha=255 en todo el objeto."""
    rgba = np.zeros((height, width, 4), dtype=np.uint8)
    rgba[:, :, 0] = rgb[0]
    rgba[:, :, 1] = rgb[1]
    rgba[:, :, 2] = rgb[2]
    rgba[:, :, 3] = 255
    return rgba


def rect_mask(x, y, width, height):
    """Máscara de lienzo completo con un rectángulo foreground."""
    mask = np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH), dtype=bool)
    mask[y: y + height, x: x + width] = True
    return mask


def write_cutout_png(path, rgba):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    Image.fromarray(rgba, mode="RGBA").save(path, format="PNG")
    return path


def build_cutout_library(tmp_path, count, size=(96, 128), name="cutouts"):
    """Crea `count` cutouts PNG RGBA y su manifiesto CSV train/accepted.

    Devuelve (cutout_root, manifest_path, filas_del_manifiesto). El
    cutout_sha256 de cada fila es el hash real del PNG físico escrito.
    """
    cutout_root = tmp_path / name
    rows = cutout_rows(count)
    width, height = size
    for index, row in enumerate(rows):
        rgba = make_rgba_rectangle(
            width, height, rgb=(40 + index * 7 % 200, 90, 150)
        )
        png_path = str(cutout_root / row["cutout_relative_path"])
        write_cutout_png(png_path, rgba)
        row["cutout_sha256"] = hashlib.sha256(
            open(png_path, "rb").read()
        ).hexdigest()

    manifest_path = write_cutout_manifest(str(tmp_path / f"{name}_manifest.csv"), rows)
    return str(cutout_root), manifest_path, rows


def build_scene_specs(tmp_path, scene_defs, cutout_manifest_path, plan_name="plan.csv"):
    """Construye specs de escena usando el asignador P2-006 en modo no gobernante."""
    plan_path = write_scene_plan(str(tmp_path / plan_name), scene_defs)
    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(cutout_manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)
    return group_assignments(assignments)


def run_generate_scenes(specs, cutout_root, output_root, manifest_path, **overrides):
    """Envoltorio de test: llena allowed_source_ids/generator_commit por defecto.

    Ambos son obligatorios en generate_scenes(); este helper evita repetir el
    boilerplate en cada test mientras conserva la posibilidad de pasar valores
    explícitos (incluidos None) para probar los propios gates.
    """
    kwargs = {
        "allowed_source_ids": load_train_source_allowlist(manifest_path),
        "generator_commit": FIXTURE_GENERATOR_COMMIT,
    }
    kwargs.update(overrides)
    return generate_scenes(specs, cutout_root, output_root, **kwargs)


# --------------------------------------------------------------------------
# Geometría de oclusión y caja visible
# --------------------------------------------------------------------------

def test_dos_objetos_sin_overlap_no_tienen_oclusion():
    """Objetos disjuntos: visible_area == transformed_area, oclusión 0."""
    masks = [rect_mask(100, 100, 200, 300), rect_mask(600, 700, 150, 150)]
    visibility = compute_visibility(masks)

    assert visibility[0]["transformed_area"] == 200 * 300
    assert visibility[0]["visible_area"] == 200 * 300
    assert visibility[0]["occlusion_fraction"] == 0.0
    assert visibility[1]["visible_area"] == 150 * 150
    assert visibility[1]["occlusion_fraction"] == 0.0


def test_bbox_visible_de_objeto_sin_overlap_es_su_rectangulo():
    """Sin oclusión, la caja visible coincide con el objeto transformado."""
    masks = [rect_mask(100, 100, 200, 300)]
    visibility = compute_visibility(masks)

    line = compute_yolo_box(visibility[0]["visible_mask"], class_id=0)
    # x: 100..299 -> x0=100, x1=300 ; y: 100..399 -> y0=100, y1=400
    expected_xc = ((100 + 300) / 2) / CANVAS_WIDTH
    expected_yc = ((100 + 400) / 2) / CANVAS_HEIGHT
    expected_w = 200 / CANVAS_WIDTH
    expected_h = 300 / CANVAS_HEIGHT
    assert line == (
        f"0 {expected_xc:.6f} {expected_yc:.6f} {expected_w:.6f} {expected_h:.6f}"
    )


def test_bbox_visible_se_encoge_cuando_el_objeto_queda_parcialmente_tapado():
    """La caja se calcula sobre la máscara VISIBLE, no sobre el rectángulo original.

    Objeto de fondo en x=100..299; encima se coloca uno que tapa x=200..399.
    La parte visible del de abajo es x=100..199, así que su caja debe encogerse.
    """
    bottom = rect_mask(100, 100, 200, 200)   # x 100..299, y 100..299
    top = rect_mask(200, 100, 200, 200)      # x 200..399, y 100..299
    visibility = compute_visibility([bottom, top])

    visible_bottom = visibility[0]["visible_mask"]
    ys, xs = visible_bottom.nonzero()
    assert (int(xs.min()), int(xs.max())) == (100, 199)
    assert (int(ys.min()), int(ys.max())) == (100, 299)

    line = compute_yolo_box(visible_bottom, class_id=0)
    expected_xc = ((100 + 200) / 2) / CANVAS_WIDTH
    expected_w = 100 / CANVAS_WIDTH
    assert line.split()[1] == f"{expected_xc:.6f}"
    assert line.split()[3] == f"{expected_w:.6f}"

    # El objeto de arriba no pierde nada.
    assert visibility[1]["occlusion_fraction"] == 0.0


def test_occlusion_fraction_exacta():
    """Tapar la mitad exacta del objeto de abajo da occlusion_fraction = 0.5."""
    bottom = rect_mask(100, 100, 200, 200)   # 40000 px
    top = rect_mask(200, 100, 100, 200)      # tapa 100x200 = 20000 px del de abajo
    visibility = compute_visibility([bottom, top])

    assert visibility[0]["transformed_area"] == 40000
    assert visibility[0]["visible_area"] == 20000
    assert visibility[0]["occlusion_fraction"] == pytest.approx(0.5)


def test_occlusion_se_mide_contra_todos_los_objetos_por_encima():
    """El z-order se resuelve contra la unión de TODAS las capas superiores."""
    bottom = rect_mask(100, 100, 300, 100)          # 30000 px
    middle = rect_mask(100, 100, 100, 100)          # tapa 10000
    top = rect_mask(200, 100, 100, 100)             # tapa otros 10000
    visibility = compute_visibility([bottom, middle, top])

    assert visibility[0]["visible_area"] == 10000
    assert visibility[0]["occlusion_fraction"] == pytest.approx(2 / 3)


def test_rechazo_por_superar_max_occlusion():
    """Basic tolera 0.05: una oclusión de 0.5 debe rechazar el intento."""
    bottom = rect_mask(100, 100, 200, 200)
    top = rect_mask(200, 100, 100, 200)
    visibility = compute_visibility([bottom, top])

    with pytest.raises(SceneRejected, match="oclusión"):
        enforce_occlusion_limits(visibility, DIFFICULTY_RULES["basic"]["max_occlusion"])


def test_oclusion_dentro_del_limite_no_rechaza():
    """Extreme tolera 0.45: una oclusión de 0.25 pasa."""
    bottom = rect_mask(100, 100, 200, 200)
    top = rect_mask(250, 100, 50, 200)   # tapa 50x200 = 10000 de 40000 -> 0.25
    visibility = compute_visibility([bottom, top])

    assert visibility[0]["occlusion_fraction"] == pytest.approx(0.25)
    enforce_occlusion_limits(visibility, DIFFICULTY_RULES["extreme"]["max_occlusion"])


def test_objeto_totalmente_oculto_es_rechazado():
    """visible_area == 0 invalida el placement aunque la dificultad sea extreme."""
    bottom = rect_mask(200, 200, 100, 100)
    top = rect_mask(100, 100, 400, 400)   # cubre por completo al de abajo
    visibility = compute_visibility([bottom, top])

    assert visibility[0]["visible_area"] == 0
    assert visibility[0]["occlusion_fraction"] == 1.0
    with pytest.raises(SceneRejected, match="totalmente oculto"):
        enforce_occlusion_limits(
            visibility, DIFFICULTY_RULES["extreme"]["max_occlusion"]
        )


def test_build_canvas_mask_rechaza_objeto_fuera_del_lienzo():
    local = np.ones((100, 100), dtype=bool)
    with pytest.raises(SceneRejected, match="fuera del lienzo"):
        build_canvas_mask(local, CANVAS_WIDTH - 50, 0)


# --------------------------------------------------------------------------
# Transformación
# --------------------------------------------------------------------------

def test_transform_preserva_aspect_ratio_sin_rotacion():
    rgba = make_rgba_rectangle(100, 200)
    transformed, mask = transform_cutout(rgba, scale=0.5, rotation_deg=0.0)

    assert transformed.shape[:2] == (100, 50)
    assert mask.shape == (100, 50)
    assert mask.all()


def test_transform_rotado_conserva_transparencia_fuera_del_objeto():
    """Tras rotar, las esquinas nuevas son alpha=0: no se inventa foreground."""
    rgba = make_rgba_rectangle(100, 100)
    transformed, mask = transform_cutout(rgba, scale=1.0, rotation_deg=45.0)

    assert transformed.shape[2] == 4
    assert not mask[0, 0]           # esquina de relleno
    assert mask[mask.shape[0] // 2, mask.shape[1] // 2]   # centro sigue siendo objeto
    assert mask.sum() < mask.size   # el bounding rotado no está lleno


# --------------------------------------------------------------------------
# Determinismo del sub-seed
# --------------------------------------------------------------------------

def test_derive_attempt_seed_es_determinista_y_distingue_intentos():
    assert derive_attempt_seed(42001, 0) == derive_attempt_seed(42001, 0)
    assert derive_attempt_seed(42001, 0) != derive_attempt_seed(42001, 1)
    assert derive_attempt_seed(42001, 0) != derive_attempt_seed(42002, 0)


def test_parse_background_rgb():
    assert parse_background_rgb("255,255,255") == (255, 255, 255)
    assert parse_background_rgb(" 0 , 10 ,20 ") == (0, 10, 20)
    with pytest.raises(ValueError):
        parse_background_rgb("255,255")
    with pytest.raises(ValueError):
        parse_background_rgb("255,255,300")


# --------------------------------------------------------------------------
# Procedencia del generador (auditoría CHANGES_REQUIRED, punto 2)
# --------------------------------------------------------------------------

def test_validate_generator_commit_acepta_sha_completo():
    assert validate_generator_commit(FIXTURE_GENERATOR_COMMIT) == FIXTURE_GENERATOR_COMMIT


def test_validate_generator_commit_acepta_sha_corto():
    assert validate_generator_commit("3ea3488") == "3ea3488"


def test_validate_generator_commit_normaliza_mayusculas():
    assert validate_generator_commit("3EA3488") == "3ea3488"


def test_validate_generator_commit_rechaza_no_hex():
    with pytest.raises(ValueError, match="SHA git"):
        validate_generator_commit("not-a-sha!")


def test_validate_generator_commit_rechaza_vacio():
    with pytest.raises(ValueError, match="SHA git"):
        validate_generator_commit("")


def test_validate_generator_commit_rechaza_muy_corto():
    with pytest.raises(ValueError, match="SHA git"):
        validate_generator_commit("abc12")


def test_generator_commit_se_registra_en_el_manifiesto(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    rows, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)

    for row in rows:
        assert row["generator_commit"] == FIXTURE_GENERATOR_COMMIT
        assert row["generator_version"]


def test_generate_scenes_rechaza_generator_commit_invalido(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    with pytest.raises(ValueError, match="SHA git"):
        run_generate_scenes(
            specs, cutout_root, str(tmp_path / "out"), manifest_path,
            generator_commit="no-es-un-sha",
        )


# --------------------------------------------------------------------------
# Generación end-to-end con fixtures
# --------------------------------------------------------------------------

def test_escena_basica_produce_label_con_lineas_exactas(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(
        tmp_path, [("basic", 2), ("basic", 3)], manifest_path
    )
    output_root = str(tmp_path / "out")

    rows, summary = run_generate_scenes(specs, cutout_root, output_root, manifest_path)

    assert summary["scenes"] == 2
    assert summary["images"] == 2
    assert summary["labels"] == 2
    assert summary["placements"] == 5

    for spec in specs:
        label_path = os.path.join(output_root, "labels", f"{spec['scene_id']}.txt")
        lines = [
            line for line in open(label_path, encoding="utf-8").read().splitlines()
            if line.strip()
        ]
        assert len(lines) == spec["planned_n_products"]
        for line in lines:
            assert line.startswith("0 ")


def test_coordenadas_dentro_de_cero_uno(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 8)
    specs = build_scene_specs(tmp_path, [("medium", 4), ("hard", 6)], manifest_path)
    rows, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)

    for row in rows:
        for column in ("yolo_xc", "yolo_yc", "yolo_w", "yolo_h"):
            value = float(row[column])
            assert 0.0 <= value <= 1.0
        assert float(row["yolo_w"]) > 0
        assert float(row["yolo_h"]) > 0
        assert int(row["visible_area"]) > 0


def test_manifiesto_tiene_todas_las_columnas_y_rutas_relativas(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    rows, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)

    for row in rows:
        assert set(row) == set(MANIFEST_COLUMNS)
        for column in ("output_image_relative_path", "output_label_relative_path"):
            assert not os.path.isabs(row[column])
            assert ":" not in row[column]
        assert row["output_image_sha256"]
        assert row["output_label_sha256"]
        assert row["generator_version"]
        assert row["generator_commit"] == FIXTURE_GENERATOR_COMMIT
        assert int(row["actual_object_count"]) == int(row["planned_object_count"])


def test_mismo_seed_produce_mismos_hashes(tmp_path):
    """Mismo input + mismo seed => mismos bytes de imagen y label."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs_a = build_scene_specs(tmp_path, [("basic", 3)], manifest_path, "plan_a.csv")
    specs_b = build_scene_specs(tmp_path, [("basic", 3)], manifest_path, "plan_b.csv")

    rows_a, _ = run_generate_scenes(specs_a, cutout_root, str(tmp_path / "out_a"), manifest_path)
    rows_b, _ = run_generate_scenes(specs_b, cutout_root, str(tmp_path / "out_b"), manifest_path)

    assert [r["output_image_sha256"] for r in rows_a] == [
        r["output_image_sha256"] for r in rows_b
    ]
    assert [r["output_label_sha256"] for r in rows_a] == [
        r["output_label_sha256"] for r in rows_b
    ]
    assert [r["scale"] for r in rows_a] == [r["scale"] for r in rows_b]
    assert [r["x"] for r in rows_a] == [r["x"] for r in rows_b]


def test_seed_distinto_produce_escena_distinta(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 3)], manifest_path)

    rows_a, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out_a"), manifest_path)

    # Mismas fuentes y misma dificultad, pero otro scene_seed.
    other = [dict(spec) for spec in specs]
    other[0]["scene_seed"] = specs[0]["scene_seed"] + 1
    other[0]["placements"] = [dict(p, scene_seed=other[0]["scene_seed"]) for p in specs[0]["placements"]]
    rows_b, _ = run_generate_scenes(other, cutout_root, str(tmp_path / "out_b"), manifest_path)

    assert rows_a[0]["output_image_sha256"] != rows_b[0]["output_image_sha256"]


def test_fondo_configurable_cambia_los_pixeles(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    run_generate_scenes(
        specs, cutout_root, str(tmp_path / "white"), manifest_path,
        background_rgb=(255, 255, 255),
    )
    run_generate_scenes(
        specs, cutout_root, str(tmp_path / "black"), manifest_path,
        background_rgb=(0, 0, 0),
    )

    white = np.array(Image.open(
        os.path.join(str(tmp_path / "white"), "images", f"{specs[0]['scene_id']}.png")
    ))
    black = np.array(Image.open(
        os.path.join(str(tmp_path / "black"), "images", f"{specs[0]['scene_id']}.png")
    ))

    assert white[0, 0].tolist() == [255, 255, 255]
    assert black[0, 0].tolist() == [0, 0, 0]


def test_rgb_del_cutout_se_conserva_en_el_compuesto(tmp_path):
    """El compositor no aplica filtros: el color opaco del cutout sobrevive."""
    cutout_root, manifest_path, rows = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    manifest_rows, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)

    image = np.array(Image.open(
        os.path.join(str(tmp_path / "out"), "images", f"{specs[0]['scene_id']}.png")
    ))
    first = manifest_rows[0]
    source_rgba = np.array(Image.open(
        os.path.join(cutout_root, "cutouts", f"{first['source_asset_id']}.png")
    ))
    expected_rgb = source_rgba[0, 0, :3].tolist()

    # El color del cutout aparece en el lienzo (alpha=255 => sustitución exacta).
    matches = np.all(image == np.array(expected_rgb, dtype=np.uint8), axis=2)
    assert matches.any()


# --------------------------------------------------------------------------
# Rangos de transformación por dificultad
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "difficulty,n_products",
    [("basic", 2), ("medium", 4), ("hard", 6), ("extreme", 9)],
)
def test_rangos_de_transformacion_por_dificultad(tmp_path, difficulty, n_products):
    """scale y rotation deben caer en el rango gobernante de cada nivel."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 12)
    specs = build_scene_specs(
        tmp_path, [(difficulty, n_products)] * 3, manifest_path
    )
    rows, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)

    rules = DIFFICULTY_RULES[difficulty]
    scale_lo, scale_hi = rules["scale"]
    rot_lo, rot_hi = rules["rotation"]

    assert len(rows) == 3 * n_products
    for row in rows:
        assert row["difficulty"] == difficulty
        assert scale_lo <= float(row["scale"]) <= scale_hi
        assert rot_lo <= float(row["rotation_deg"]) <= rot_hi
        assert float(row["occlusion_fraction"]) <= rules["max_occlusion"]


# --------------------------------------------------------------------------
# Nunca reducir el conteo: fallo fuerte
# --------------------------------------------------------------------------

def test_escena_imposible_falla_sin_reducir_objetos(tmp_path):
    """Cutouts enormes en basic: el solape es inevitable y la escena debe fallar.

    El contrato prohíbe bajar n_products en silencio; se exige error explícito.
    """
    cutout_root = tmp_path / "big_cutouts"
    rows = cutout_rows(2)
    for row in rows:
        rgba = make_rgba_rectangle(900, 900)
        png_path = str(cutout_root / row["cutout_relative_path"])
        write_cutout_png(png_path, rgba)
        row["cutout_sha256"] = hashlib.sha256(open(png_path, "rb").read()).hexdigest()
    manifest_path = write_cutout_manifest(str(tmp_path / "big_manifest.csv"), rows)

    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    with pytest.raises(SceneGenerationError, match="agotados"):
        run_generate_scenes(specs, str(cutout_root), str(tmp_path / "out"), manifest_path)


# --------------------------------------------------------------------------
# Gates de fuga y de integridad de entrada
# --------------------------------------------------------------------------

def test_fuente_repetida_dentro_de_escena_falla(tmp_path):
    """Aunque el CSV de entrada venga corrupto, el compositor lo detecta.

    Se copia el linaje COMPLETO del primer placement (no solo source_asset_id)
    para que el único problema detectable sea la repetición dentro de la
    escena, y no dispare primero el gate de linaje contradictorio (que cubre
    un caso distinto: mismo source_asset_id con metadata distinta).
    """
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    first = specs[0]["placements"][0]
    corrupted = []
    for placement in specs[0]["placements"]:
        row = dict(placement)
        for field in (
            "source_asset_id", "sku_id", "category", "metadata_status",
            "cutout_relative_path", "cutout_sha256",
        ):
            row[field] = first[field]
        corrupted.append(row)

    with pytest.raises(SceneGenerationError, match="repetido"):
        group_assignments(corrupted)


def test_fuente_val_es_rechazada_por_el_gate_antifuga(tmp_path):
    """Una fuente que no está en la allowlist train aborta la generación."""
    cutout_root, manifest_path, rows = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    # Se marca como val exactamente una fuente que SÍ participa en la escena,
    # para que el gate tenga que dispararse (sin depender del reparto de cuotas).
    leaked_id = specs[0]["placements"][0]["source_asset_id"]
    leaky_rows = [dict(row) for row in rows]
    for row in leaky_rows:
        if row["source_asset_id"] == leaked_id:
            row["split"] = "val"
    leaky_manifest = write_cutout_manifest(str(tmp_path / "leaky.csv"), leaky_rows)
    allowed = load_train_source_allowlist(leaky_manifest)

    assert leaked_id not in allowed

    with pytest.raises(SceneGenerationError, match="fuga val/test"):
        generate_scenes(
            specs,
            cutout_root,
            str(tmp_path / "out"),
            allowed_source_ids=allowed,
            generator_commit=FIXTURE_GENERATOR_COMMIT,
        )


def test_fuente_test_es_rechazada_por_el_gate_antifuga(tmp_path):
    cutout_root, manifest_path, rows = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2), ("basic", 2)], manifest_path)

    leaky_rows = [dict(row) for row in rows]
    for row in leaky_rows:
        row["split"] = "test"
    leaky_manifest = write_cutout_manifest(str(tmp_path / "leaky_test.csv"), leaky_rows)
    allowed = load_train_source_allowlist(leaky_manifest)

    assert allowed == set()
    with pytest.raises(SceneGenerationError, match="fuga val/test"):
        generate_scenes(
            specs, cutout_root, str(tmp_path / "out"),
            allowed_source_ids=allowed,
            generator_commit=FIXTURE_GENERATOR_COMMIT,
        )


def test_cutout_inexistente_falla(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    with pytest.raises(SceneGenerationError, match="cutout inexistente"):
        run_generate_scenes(
            specs, str(tmp_path / "no_such_root"), str(tmp_path / "out"), manifest_path
        )


# --------------------------------------------------------------------------
# Gate anti-fuga OBLIGATORIO (auditoría CHANGES_REQUIRED, punto 4)
# --------------------------------------------------------------------------

def test_generate_scenes_rechaza_allowed_source_ids_none(tmp_path):
    """El leakage gate no puede omitirse pasando None: generate_scenes lo exige."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    with pytest.raises(ValueError, match="allowed_source_ids"):
        generate_scenes(
            specs, cutout_root, str(tmp_path / "out"),
            allowed_source_ids=None,
            generator_commit=FIXTURE_GENERATOR_COMMIT,
        )


def test_validate_outputs_rechaza_allowed_source_ids_none(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    rows, _ = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)

    with pytest.raises(ValueError, match="allowed_source_ids"):
        validate_outputs(
            rows, str(tmp_path / "out"), [specs[0]["scene_id"]], allowed_source_ids=None
        )


def test_cli_sin_cutout_manifest_falla(tmp_path, capsys):
    """--cutout-manifest es obligatorio: sin él, argparse rechaza la invocación."""
    with pytest.raises(SystemExit) as excinfo:
        main([
            "--assignments", str(tmp_path / "assignments.csv"),
            "--cutout-root", str(tmp_path / "cutouts"),
            "--output-root", str(tmp_path / "out"),
            "--manifest", str(tmp_path / "m.csv"),
            "--generator-commit", FIXTURE_GENERATOR_COMMIT,
        ])
    assert excinfo.value.code != 0


def test_cli_sin_generator_commit_falla(tmp_path):
    """--generator-commit es obligatorio: sin él, argparse rechaza la invocación."""
    with pytest.raises(SystemExit) as excinfo:
        main([
            "--assignments", str(tmp_path / "assignments.csv"),
            "--cutout-root", str(tmp_path / "cutouts"),
            "--output-root", str(tmp_path / "out"),
            "--manifest", str(tmp_path / "m.csv"),
            "--cutout-manifest", str(tmp_path / "cutout_manifest.csv"),
        ])
    assert excinfo.value.code != 0


def test_cli_exitoso_siempre_reporta_leakage_gate_on(tmp_path, capsys):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    plan_path = write_scene_plan(
        str(tmp_path / "plan.csv"), [("basic", 2), ("basic", 3)]
    )
    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)

    assignments_path = tmp_path / "assignments.csv"
    write_assignments(assignments, str(assignments_path))

    exit_code = main([
        "--assignments", str(assignments_path),
        "--cutout-root", cutout_root,
        "--output-root", str(tmp_path / "out"),
        "--manifest", str(tmp_path / "scene_manifest.csv"),
        "--cutout-manifest", manifest_path,
        "--generator-commit", FIXTURE_GENERATOR_COMMIT,
        "--scene-id", "SYN_0001",
        "--background-rgb", "255,255,255",
    ])
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "SCENES=1" in captured
    assert "LEAKAGE_GATE=ON" in captured
    assert f"GENERATOR_COMMIT={FIXTURE_GENERATOR_COMMIT}" in captured
    assert "QA=PASS" in captured
    assert os.path.exists(str(tmp_path / "out" / "images" / "SYN_0001.png"))
    assert os.path.exists(str(tmp_path / "out" / "labels" / "SYN_0001.txt"))


# --------------------------------------------------------------------------
# Integridad de hash de cutout (auditoría CHANGES_REQUIRED, punto 3)
# --------------------------------------------------------------------------

def test_cutout_hash_correcto_pasa(tmp_path):
    """El caso feliz: el sha256 físico coincide con el declarado."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    rows, summary = run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)
    assert summary["scenes"] == 1


def test_cutout_fisico_alterado_falla(tmp_path):
    """Si el PNG físico cambia después de declarar su hash, la corrida debe fallar."""
    cutout_root, manifest_path, rows = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    used_id = specs[0]["placements"][0]["source_asset_id"]
    used_row = next(r for r in rows if r["source_asset_id"] == used_id)
    png_path = os.path.join(cutout_root, used_row["cutout_relative_path"])

    # Se reemplaza el PNG físico por otro contenido válido pero distinto:
    # el hash declarado en el manifiesto queda desactualizado.
    tampered = make_rgba_rectangle(50, 50, rgb=(1, 2, 3))
    Image.fromarray(tampered, mode="RGBA").save(png_path, format="PNG")

    with pytest.raises(SceneGenerationError, match="sha256 físico"):
        run_generate_scenes(specs, cutout_root, str(tmp_path / "out"), manifest_path)


def test_hash_declarado_incorrecto_falla(tmp_path):
    """Si cutout_sha256 en el assignments no coincide con el archivo, falla."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    tampered_specs = [dict(spec) for spec in specs]
    tampered_specs[0]["placements"] = [
        dict(p, cutout_sha256="0" * 64) for p in specs[0]["placements"]
    ]

    with pytest.raises(SceneGenerationError, match="sha256 físico"):
        run_generate_scenes(
            tampered_specs, cutout_root, str(tmp_path / "out"), manifest_path
        )


def test_mismo_source_con_metadata_contradictoria_falla(tmp_path):
    """El mismo source_asset_id no puede declarar linaje distinto entre placements.

    3 fuentes y 2 escenas de n=2 (4 placements) fuerzan por construcción de
    cuotas (divmod(4,3)=(1,1)) que exactamente una fuente se use dos veces, en
    dos escenas distintas: la repetición entre escenas está garantizada, no es
    un azar del reparto.
    """
    _, manifest_path, _ = build_cutout_library(tmp_path, 3)
    specs = build_scene_specs(tmp_path, [("basic", 2), ("basic", 2)], manifest_path)

    all_placements = [p for s in specs for p in s["placements"]]
    from collections import Counter

    usage = Counter(p["source_asset_id"] for p in all_placements)
    target_id = next(source_id for source_id, count in usage.items() if count > 1)
    assert usage[target_id] > 1  # garantizado por el reparto de cuotas 1+1

    corrupted_rows = []
    seen_target = False
    for row in all_placements:
        row = dict(row)
        if row["source_asset_id"] == target_id and not seen_target:
            seen_target = True
        elif row["source_asset_id"] == target_id:
            row["sku_id"] = row["sku_id"] + "-CONTRADICTORIO"
        corrupted_rows.append(row)

    with pytest.raises(SceneGenerationError, match="contradictoria"):
        validate_source_lineage_consistency(corrupted_rows)


def test_validate_source_lineage_consistency_pasa_con_datos_coherentes(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2), ("basic", 2)], manifest_path)
    all_placements = [p for s in specs for p in s["placements"]]

    validate_source_lineage_consistency(all_placements)  # no debe lanzar


def test_group_assignments_detecta_contradiccion_de_linaje(tmp_path):
    """group_assignments debe abortar si el CSV de assignments trae linaje inconsistente.

    Igual que el test anterior: 3 fuentes y 2 escenas de n=2 garantizan por
    construcción de cuotas que una fuente se repite entre escenas.
    """
    _, manifest_path, _ = build_cutout_library(tmp_path, 3)
    specs = build_scene_specs(tmp_path, [("basic", 2), ("basic", 2)], manifest_path)
    all_placements = [p for s in specs for p in s["placements"]]

    from collections import Counter

    usage = Counter(p["source_asset_id"] for p in all_placements)
    target_id = next(source_id for source_id, count in usage.items() if count > 1)

    corrupted = [dict(p) for p in all_placements]
    touched = False
    for row in corrupted:
        if row["source_asset_id"] == target_id:
            if not touched:
                touched = True
                continue
            row["category"] = (row["category"] or "") + "-DISTINTA"
            break

    with pytest.raises(SceneGenerationError, match="contradictoria"):
        group_assignments(corrupted)


# --------------------------------------------------------------------------
# Integridad de rutas (auditoría CHANGES_REQUIRED, punto 5)
# --------------------------------------------------------------------------

def test_resolve_cutout_path_resuelve_ruta_normal(tmp_path):
    cutout_root = tmp_path / "root"
    (cutout_root / "cutouts").mkdir(parents=True)
    target = cutout_root / "cutouts" / "a.png"
    target.write_bytes(b"fake")

    resolved = resolve_cutout_path(str(cutout_root), "cutouts/a.png")
    assert os.path.realpath(resolved) == os.path.realpath(str(target))


def test_resolve_cutout_path_rechaza_absoluta(tmp_path):
    with pytest.raises(AssignmentError, match="absoluta"):
        resolve_cutout_path(str(tmp_path), "/etc/passwd")


def test_resolve_cutout_path_rechaza_traversal(tmp_path):
    with pytest.raises(AssignmentError, match="traversal"):
        resolve_cutout_path(str(tmp_path), "../outside.png")


def test_generate_scenes_rechaza_traversal_en_placement(tmp_path):
    """Aunque P2-006 ya valide, el compositor revalida por defensa en profundidad."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    tampered_specs = [dict(spec) for spec in specs]
    tampered_placements = [dict(p) for p in specs[0]["placements"]]
    tampered_placements[0]["cutout_relative_path"] = "../../outside.png"
    tampered_specs[0]["placements"] = tampered_placements

    with pytest.raises(AssignmentError, match="traversal"):
        run_generate_scenes(
            tampered_specs, cutout_root, str(tmp_path / "out"), manifest_path
        )


# --------------------------------------------------------------------------
# Consistencia de entrada dentro de una escena (auditoría CHANGES_REQUIRED, punto 6)
# --------------------------------------------------------------------------

def test_group_assignments_detecta_difficulty_inconsistente(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    placements = [dict(p) for p in specs[0]["placements"]]
    placements[1]["difficulty"] = "medium"

    with pytest.raises(SceneGenerationError, match="difficulty"):
        group_assignments(placements)


def test_group_assignments_detecta_scene_seed_inconsistente(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    placements = [dict(p) for p in specs[0]["placements"]]
    placements[1]["scene_seed"] = placements[1]["scene_seed"] + 1

    with pytest.raises(SceneGenerationError, match="scene_seed"):
        group_assignments(placements)


def test_group_assignments_detecta_planned_n_products_inconsistente(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    placements = [dict(p) for p in specs[0]["placements"]]
    placements[1]["planned_n_products"] = 99

    with pytest.raises(SceneGenerationError, match="planned_n_products"):
        group_assignments(placements)


# --------------------------------------------------------------------------
# QA automático
# --------------------------------------------------------------------------

def test_qa_detecta_label_con_lineas_de_menos(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 3)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    label_path = os.path.join(output_root, rows[0]["output_label_relative_path"])
    with open(label_path, "w", encoding="utf-8") as handle:
        handle.write("0 0.500000 0.500000 0.100000 0.100000\n")

    with pytest.raises(QAError):
        validate_outputs(
            rows, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_coordenada_fuera_de_rango(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    tampered = [dict(row) for row in rows]
    tampered[0]["yolo_xc"] = "1.500000"
    with pytest.raises(QAError, match="fuera de \\[0,1\\]"):
        validate_outputs(
            tampered, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_oclusion_por_encima_del_limite(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    tampered = [dict(row) for row in rows]
    tampered[0]["occlusion_fraction"] = "0.900000"
    with pytest.raises(QAError, match="oclusión"):
        validate_outputs(
            tampered, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_visible_area_cero(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    tampered = [dict(row) for row in rows]
    tampered[0]["visible_area"] = "0"
    with pytest.raises(QAError, match="visible_area"):
        validate_outputs(
            tampered, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_hash_faltante(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    tampered = [dict(row) for row in rows]
    tampered[0]["output_image_sha256"] = ""
    with pytest.raises(QAError, match="vacío"):
        validate_outputs(
            tampered, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_metadata_status_faltante(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    tampered = [dict(row) for row in rows]
    tampered[0]["metadata_status"] = ""
    with pytest.raises(QAError, match="metadata_status"):
        validate_outputs(
            tampered, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_generator_commit_faltante(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    tampered = [dict(row) for row in rows]
    tampered[0]["generator_commit"] = ""
    with pytest.raises(QAError, match="generator_commit"):
        validate_outputs(
            tampered, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_imagen_modificada_por_hash(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    image_path = os.path.join(output_root, rows[0]["output_image_relative_path"])
    Image.fromarray(
        np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8), mode="RGB"
    ).save(image_path, format="PNG")

    with pytest.raises(QAError, match="sha256 de imagen"):
        validate_outputs(
            rows, output_root, [specs[0]["scene_id"]], allowed_source_ids=allowed
        )


def test_qa_detecta_conteo_de_imagenes_incorrecto(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 2), ("basic", 3)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = run_generate_scenes(specs, cutout_root, output_root, manifest_path)
    allowed = load_train_source_allowlist(manifest_path)

    os.remove(os.path.join(output_root, "images", f"{specs[1]['scene_id']}.png"))
    with pytest.raises(QAError, match="imágenes para"):
        validate_outputs(
            rows, output_root, [s["scene_id"] for s in specs], allowed_source_ids=allowed
        )


# --------------------------------------------------------------------------
# Piloto
# --------------------------------------------------------------------------

PILOT_PLAN = (
    [("basic", 2)] * 5
    + [("basic", 3)] * 5
    + [("medium", 4)] * 5
    + [("medium", 5)] * 5
    + [("hard", 6)] * 4
    + [("hard", 7)] * 3
    + [("hard", 8)] * 3
)


def test_piloto_selecciona_exactamente_30_escenas_10_10_10(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 12)
    # Plan amplio: más escenas de las necesarias en cada bucket, más extreme.
    plan = (
        [("basic", 2)] * 12
        + [("basic", 3)] * 12
        + [("medium", 4)] * 12
        + [("medium", 5)] * 12
        + [("hard", 6)] * 8
        + [("hard", 7)] * 8
        + [("hard", 8)] * 8
        + [("extreme", 9)] * 5
    )
    specs = build_scene_specs(tmp_path, plan, manifest_path)
    pilot = select_pilot_scenes(specs)

    assert len(pilot) == PILOT_SCENE_COUNT == 30

    from collections import Counter

    by_difficulty = Counter(s["difficulty"] for s in pilot)
    assert by_difficulty == Counter({"basic": 10, "medium": 10, "hard": 10})
    assert "extreme" not in by_difficulty

    by_density = Counter(
        (s["difficulty"], s["planned_n_products"]) for s in pilot
    )
    assert by_density == Counter({
        ("basic", 2): 5,
        ("basic", 3): 5,
        ("medium", 4): 5,
        ("medium", 5): 5,
        ("hard", 6): 4,
        ("hard", 7): 3,
        ("hard", 8): 3,
    })


def test_piloto_es_determinista(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 12)
    specs = build_scene_specs(tmp_path, PILOT_PLAN, manifest_path)

    first = [s["scene_id"] for s in select_pilot_scenes(specs)]
    second = [s["scene_id"] for s in select_pilot_scenes(list(reversed(specs)))]
    assert first == second


def test_piloto_falla_si_no_hay_escenas_suficientes(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 2)] * 2, manifest_path)

    with pytest.raises(SceneGenerationError, match="piloto"):
        select_pilot_scenes(specs)


def test_piloto_de_fixtures_genera_30_escenas_completas(tmp_path):
    """Piloto de fixtures: 30 escenas generadas y validadas de extremo a extremo.

    No sustituye al piloto gobernante (P2-008), que requiere los cutouts reales
    de P2-005; demuestra que el compositor produce las 30 escenas del gate con
    el leakage gate y generator_commit obligatorios activos.
    """
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 12)
    specs = build_scene_specs(tmp_path, PILOT_PLAN, manifest_path)
    pilot = select_pilot_scenes(specs)
    assert len(pilot) == 30

    output_root = str(tmp_path / "pilot_out")
    rows, summary = run_generate_scenes(pilot, cutout_root, output_root, manifest_path)

    assert summary["scenes"] == 30
    assert summary["images"] == 30
    assert summary["labels"] == 30
    assert summary["placements"] == sum(s["planned_n_products"] for s in pilot)

    manifest_out = str(tmp_path / "pilot_manifest.csv")
    write_manifest(rows, manifest_out)
    with open(manifest_out, newline="", encoding="utf-8") as handle:
        written = list(csv.DictReader(handle))
    assert len(written) == len(rows)
    assert list(written[0].keys()) == list(MANIFEST_COLUMNS)


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------

def test_cli_genera_escenas_seleccionadas(tmp_path, capsys):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    plan_path = write_scene_plan(
        str(tmp_path / "plan.csv"), [("basic", 2), ("basic", 3)]
    )
    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)

    assignments_path = tmp_path / "assignments.csv"
    write_assignments(assignments, str(assignments_path))

    exit_code = main([
        "--assignments", str(assignments_path),
        "--cutout-root", cutout_root,
        "--output-root", str(tmp_path / "out"),
        "--manifest", str(tmp_path / "scene_manifest.csv"),
        "--cutout-manifest", manifest_path,
        "--generator-commit", FIXTURE_GENERATOR_COMMIT,
        "--scene-id", "SYN_0001",
        "--background-rgb", "255,255,255",
    ])
    assert exit_code == 0

    captured = capsys.readouterr().out
    assert "SCENES=1" in captured
    assert "LEAKAGE_GATE=ON" in captured
    assert "QA=PASS" in captured
    assert os.path.exists(str(tmp_path / "out" / "images" / "SYN_0001.png"))
    assert os.path.exists(str(tmp_path / "out" / "labels" / "SYN_0001.txt"))


def test_cli_rechaza_pilot_y_scene_id_juntos(tmp_path, capsys):
    exit_code = main([
        "--assignments", str(tmp_path / "nope.csv"),
        "--cutout-root", str(tmp_path),
        "--output-root", str(tmp_path / "out"),
        "--manifest", str(tmp_path / "m.csv"),
        "--cutout-manifest", str(tmp_path / "cm.csv"),
        "--generator-commit", FIXTURE_GENERATOR_COMMIT,
        "--pilot",
        "--scene-id", "SYN_0001",
    ])
    assert exit_code == 1
    assert "excluyentes" in capsys.readouterr().err


def test_cli_generator_commit_invalido_falla(tmp_path, capsys):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    plan_path = write_scene_plan(str(tmp_path / "plan.csv"), [("basic", 2)])
    plan = load_scene_plan(plan_path, governing=False)
    sources, _ = load_cutout_library(manifest_path, governing=False)
    assignments = assign_sources(plan, sources, governing=False)
    assignments_path = tmp_path / "assignments.csv"
    write_assignments(assignments, str(assignments_path))

    exit_code = main([
        "--assignments", str(assignments_path),
        "--cutout-root", cutout_root,
        "--output-root", str(tmp_path / "out"),
        "--manifest", str(tmp_path / "m.csv"),
        "--cutout-manifest", manifest_path,
        "--generator-commit", "not-hex!",
    ])
    assert exit_code == 1
    assert "FAIL" in capsys.readouterr().err
