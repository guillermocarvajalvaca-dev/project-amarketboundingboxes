"""
Tests T01-T10 para src/data/make_boxes.py
Casos y valores esperados según docs/governance/02_CONTRACTS/BOUNDING_BOX_ALGORITHM_CONTRACT.md §8

Convención: mask es un array booleano (H, W) donde True = foreground.
La función bajo test (a implementar en make_boxes.py) debe tomar la mask
y devolver la línea YOLO formateada: "0 x_center y_center width height"
"""
import numpy as np
import pytest

from src.data.make_boxes import compute_yolo_box, check_no_orphans


def make_mask(h, w, x_range, y_range):
    """Crea una máscara booleana HxW con foreground en el rectángulo dado.
    x_range, y_range son tuplas (inicio, fin) INCLUSIVE."""
    mask = np.zeros((h, w), dtype=bool)
    x0, x1 = x_range
    y0, y1 = y_range
    mask[y0:y1 + 1, x0:x1 + 1] = True
    return mask


def test_T01_caso_base():
    """10x8, x=2..6, y=1..5 -> 0 0.450000 0.437500 0.500000 0.625000"""
    mask = make_mask(h=8, w=10, x_range=(2, 6), y_range=(1, 5))
    result = compute_yolo_box(mask, class_id=0)
    assert result == "0 0.450000 0.437500 0.500000 0.625000"


def test_T02_pixel_unico():
    """píxel (0,0) en 10x20 -> 0 0.050000 0.025000 0.100000 0.050000"""
    mask = make_mask(h=20, w=10, x_range=(0, 0), y_range=(0, 0))
    result = compute_yolo_box(mask, class_id=0)
    assert result == "0 0.050000 0.025000 0.100000 0.050000"


def test_T03_imagen_completa():
    """toda la imagen -> 0 0.500000 0.500000 1.000000 1.000000"""
    h, w = 8, 10
    mask = np.ones((h, w), dtype=bool)
    result = compute_yolo_box(mask, class_id=0)
    assert result == "0 0.500000 0.500000 1.000000 1.000000"


def test_T04_mascara_vacia():
    """máscara vacía -> rechazo, sin label"""
    mask = np.zeros((8, 10), dtype=bool)
    with pytest.raises(ValueError):
        compute_yolo_box(mask, class_id=0)


def test_T05_toca_bordes_sin_truncar():
    """toca derecha/abajo -> sin truncamiento (verificar que x1,y1 no se recortan a W-1,H-1)"""
    h, w = 8, 10
    mask = make_mask(h=h, w=w, x_range=(5, w - 1), y_range=(3, h - 1))
    result = compute_yolo_box(mask, class_id=0)
    parts = result.split()
    width = float(parts[3])
    height = float(parts[4])
    expected_width = (w - 5) / w
    expected_height = (h - 3) / h
    assert abs(width - expected_width) < 1e-6
    assert abs(height - expected_height) < 1e-6


def test_T06_fondo_no_uniforme():
    """fondo no uniforme -> rechazo"""
    from src.data.make_boxes import make_mask_from_rgb

    h, w = 20, 20
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = [255, 255, 255]  # fondo blanco base
    # Ruido fuerte en el borde para romper la uniformidad
    rng = np.random.default_rng(42)
    img[0, :] = rng.integers(0, 255, size=(w, 3))
    img[-1, :] = rng.integers(0, 255, size=(w, 3))
    img[:, 0] = rng.integers(0, 255, size=(h, 3))
    img[:, -1] = rng.integers(0, 255, size=(h, 3))

    with pytest.raises(ValueError, match="fondo no uniforme"):
        make_mask_from_rgb(
            img,
            background_uniformity_tolerance=5.0,
            foreground_delta=30.0,
            min_foreground_pixels=10,
        )


def test_T07_idempotencia():
    """mismo input/config dos veces -> mismos bytes, sin duplicar audit"""
    mask = make_mask(h=8, w=10, x_range=(2, 6), y_range=(1, 5))
    result1 = compute_yolo_box(mask, class_id=0)
    result2 = compute_yolo_box(mask, class_id=0)
    assert result1 == result2


def test_T08_clase_distinta_de_cero():
    """clase distinta de 0 -> fallo, sin outputs parciales"""
    mask = make_mask(h=8, w=10, x_range=(2, 6), y_range=(1, 5))
    with pytest.raises(ValueError):
        compute_yolo_box(mask, class_id=1)


def test_T09_imagen_corrupta(tmp_path):
    """imagen corrupta -> rechazo trazable"""
    from src.data.make_boxes import load_and_validate_image

    corrupt_path = tmp_path / "corrupt.png"
    corrupt_path.write_bytes(b"esto no es una imagen valida, solo bytes basura")

    with pytest.raises(ValueError, match="decodificable"):
        load_and_validate_image(str(corrupt_path))


def test_T09b_imagen_valida_decodifica(tmp_path):
    """control: una imagen válida sí debe decodificar sin error"""
    from PIL import Image
    from src.data.make_boxes import load_and_validate_image

    valid_path = tmp_path / "valid.png"
    img = Image.new("RGB", (10, 8), color=(255, 0, 0))
    img.save(valid_path)

    result = load_and_validate_image(str(valid_path))
    assert result.shape[:2] == (8, 10)  # (H, W, ...)


def test_T10_orphan_imagen_sin_label(tmp_path):
    """T10: imagen sin su label correspondiente -> gate falla (ValueError)."""
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()

    (images_dir / "A001.jpg").write_bytes(b"fake")
    (images_dir / "A002.jpg").write_bytes(b"fake")
    (labels_dir / "A001.txt").write_text("0 0.5 0.5 0.5 0.5\n")
    # A002.txt falta -> A002.jpg es huérfano

    with pytest.raises(ValueError, match="huérfan"):
        check_no_orphans(str(images_dir), str(labels_dir))


def test_T10_orphan_label_sin_imagen(tmp_path):
    """T10: label sin su imagen correspondiente -> gate falla (ValueError)."""
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()

    (images_dir / "A001.jpg").write_bytes(b"fake")
    (labels_dir / "A001.txt").write_text("0 0.5 0.5 0.5 0.5\n")
    (labels_dir / "A002.txt").write_text("0 0.5 0.5 0.5 0.5\n")
    # A002.jpg falta -> A002.txt es huérfano

    with pytest.raises(ValueError, match="huérfan"):
        check_no_orphans(str(images_dir), str(labels_dir))


def test_T10_sin_huerfanos_pasa(tmp_path):
    """T10 control: todo cruza correctamente -> no lanza excepción."""
    images_dir = tmp_path / "images"
    labels_dir = tmp_path / "labels"
    images_dir.mkdir()
    labels_dir.mkdir()

    for stem in ("A001", "A002", "A003"):
        (images_dir / f"{stem}.jpg").write_bytes(b"fake")
        (labels_dir / f"{stem}.txt").write_text("0 0.5 0.5 0.5 0.5\n")

    check_no_orphans(str(images_dir), str(labels_dir))  # no debe lanzar
