"""
Tests P2-007 para src/data/make_synthetic_scenes.py

Cubren geometría de oclusión, semántica de caja visible, determinismo por seed,
rangos de transformación por dificultad, gates anti-fuga y el piloto de 30
escenas, según
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
    assign_sources,
    load_cutout_library,
    load_scene_plan,
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
    select_pilot_scenes,
    transform_cutout,
    validate_outputs,
    write_manifest,
)
from tests.test_assign_synthetic_sources import (
    cutout_rows,
    write_cutout_manifest,
    write_scene_plan,
)


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

    Devuelve (cutout_root, manifest_path, filas_del_manifiesto).
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
# Generación end-to-end con fixtures
# --------------------------------------------------------------------------

def test_escena_basica_produce_label_con_lineas_exactas(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(
        tmp_path, [("basic", 2), ("basic", 3)], manifest_path
    )
    output_root = str(tmp_path / "out")

    rows, summary = generate_scenes(specs, cutout_root, output_root)

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
    rows, _ = generate_scenes(specs, cutout_root, str(tmp_path / "out"))

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
    rows, _ = generate_scenes(specs, cutout_root, str(tmp_path / "out"))

    for row in rows:
        assert set(row) == set(MANIFEST_COLUMNS)
        for column in ("output_image_relative_path", "output_label_relative_path"):
            assert not os.path.isabs(row[column])
            assert ":" not in row[column]
        assert row["output_image_sha256"]
        assert row["output_label_sha256"]
        assert row["generator_version"]
        assert int(row["actual_object_count"]) == int(row["planned_object_count"])


def test_mismo_seed_produce_mismos_hashes(tmp_path):
    """Mismo input + mismo seed => mismos bytes de imagen y label."""
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs_a = build_scene_specs(tmp_path, [("basic", 3)], manifest_path, "plan_a.csv")
    specs_b = build_scene_specs(tmp_path, [("basic", 3)], manifest_path, "plan_b.csv")

    rows_a, _ = generate_scenes(specs_a, cutout_root, str(tmp_path / "out_a"))
    rows_b, _ = generate_scenes(specs_b, cutout_root, str(tmp_path / "out_b"))

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

    rows_a, _ = generate_scenes(specs, cutout_root, str(tmp_path / "out_a"))

    # Mismas fuentes y misma dificultad, pero otro scene_seed.
    other = [dict(spec) for spec in specs]
    other[0]["scene_seed"] = specs[0]["scene_seed"] + 1
    rows_b, _ = generate_scenes(other, cutout_root, str(tmp_path / "out_b"))

    assert rows_a[0]["output_image_sha256"] != rows_b[0]["output_image_sha256"]


def test_fondo_configurable_cambia_los_pixeles(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    generate_scenes(specs, cutout_root, str(tmp_path / "white"), background_rgb=(255, 255, 255))
    generate_scenes(specs, cutout_root, str(tmp_path / "black"), background_rgb=(0, 0, 0))

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
    manifest_rows, _ = generate_scenes(specs, cutout_root, str(tmp_path / "out"))

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
    rows, _ = generate_scenes(specs, cutout_root, str(tmp_path / "out"))

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
        generate_scenes(specs, str(cutout_root), str(tmp_path / "out"))


# --------------------------------------------------------------------------
# Gates de fuga y de integridad de entrada
# --------------------------------------------------------------------------

def test_fuente_repetida_dentro_de_escena_falla(tmp_path):
    """Aunque el CSV de entrada venga corrupto, el compositor lo detecta."""
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    corrupted = []
    for placement in specs[0]["placements"]:
        row = dict(placement)
        row["source_asset_id"] = specs[0]["placements"][0]["source_asset_id"]
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
            specs, cutout_root, str(tmp_path / "out"), allowed_source_ids=allowed
        )


def test_cutout_inexistente_falla(tmp_path):
    _, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)

    with pytest.raises(SceneGenerationError, match="cutout inexistente"):
        generate_scenes(specs, str(tmp_path / "no_such_root"), str(tmp_path / "out"))


# --------------------------------------------------------------------------
# QA automático
# --------------------------------------------------------------------------

def test_qa_detecta_label_con_lineas_de_menos(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 3)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    label_path = os.path.join(output_root, rows[0]["output_label_relative_path"])
    with open(label_path, "w", encoding="utf-8") as handle:
        handle.write("0 0.500000 0.500000 0.100000 0.100000\n")

    with pytest.raises(QAError):
        validate_outputs(rows, output_root, [specs[0]["scene_id"]])


def test_qa_detecta_coordenada_fuera_de_rango(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    tampered = [dict(row) for row in rows]
    tampered[0]["yolo_xc"] = "1.500000"
    with pytest.raises(QAError, match="fuera de \\[0,1\\]"):
        validate_outputs(tampered, output_root, [specs[0]["scene_id"]])


def test_qa_detecta_oclusion_por_encima_del_limite(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    tampered = [dict(row) for row in rows]
    tampered[0]["occlusion_fraction"] = "0.900000"
    with pytest.raises(QAError, match="oclusión"):
        validate_outputs(tampered, output_root, [specs[0]["scene_id"]])


def test_qa_detecta_visible_area_cero(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    tampered = [dict(row) for row in rows]
    tampered[0]["visible_area"] = "0"
    with pytest.raises(QAError, match="visible_area"):
        validate_outputs(tampered, output_root, [specs[0]["scene_id"]])


def test_qa_detecta_hash_faltante(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    tampered = [dict(row) for row in rows]
    tampered[0]["output_image_sha256"] = ""
    with pytest.raises(QAError, match="vacío"):
        validate_outputs(tampered, output_root, [specs[0]["scene_id"]])


def test_qa_detecta_imagen_modificada_por_hash(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 4)
    specs = build_scene_specs(tmp_path, [("basic", 2)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    image_path = os.path.join(output_root, rows[0]["output_image_relative_path"])
    Image.fromarray(
        np.zeros((CANVAS_HEIGHT, CANVAS_WIDTH, 3), dtype=np.uint8), mode="RGB"
    ).save(image_path, format="PNG")

    with pytest.raises(QAError, match="sha256 de imagen"):
        validate_outputs(rows, output_root, [specs[0]["scene_id"]])


def test_qa_detecta_conteo_de_imagenes_incorrecto(tmp_path):
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 6)
    specs = build_scene_specs(tmp_path, [("basic", 2), ("basic", 3)], manifest_path)
    output_root = str(tmp_path / "out")
    rows, _ = generate_scenes(specs, cutout_root, output_root)

    os.remove(os.path.join(output_root, "images", f"{specs[1]['scene_id']}.png"))
    with pytest.raises(QAError, match="imágenes para"):
        validate_outputs(rows, output_root, [s["scene_id"] for s in specs])


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
    """Piloto REAL de fixtures: 30 escenas generadas y validadas de extremo a extremo.

    No sustituye al piloto gobernante (P2-008), que requiere los cutouts reales
    de P2-005; demuestra que el compositor produce las 30 escenas del gate.
    """
    cutout_root, manifest_path, _ = build_cutout_library(tmp_path, 12)
    specs = build_scene_specs(tmp_path, PILOT_PLAN, manifest_path)
    pilot = select_pilot_scenes(specs)
    assert len(pilot) == 30

    allowed = load_train_source_allowlist(manifest_path)
    output_root = str(tmp_path / "pilot_out")
    rows, summary = generate_scenes(
        pilot, cutout_root, output_root, allowed_source_ids=allowed
    )

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
    from src.data.assign_synthetic_sources import write_assignments

    write_assignments(assignments, str(assignments_path))

    exit_code = main([
        "--assignments", str(assignments_path),
        "--cutout-root", cutout_root,
        "--output-root", str(tmp_path / "out"),
        "--manifest", str(tmp_path / "scene_manifest.csv"),
        "--cutout-manifest", manifest_path,
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
        "--pilot",
        "--scene-id", "SYN_0001",
    ])
    assert exit_code == 1
    assert "excluyentes" in capsys.readouterr().err
