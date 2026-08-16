"""
Tests T01-T10 para src/data/make_boxes.py
Casos y valores esperados según docs/governance/02_CONTRACTS/BOUNDING_BOX_ALGORITHM_CONTRACT.md §8

Convención: mask es un array booleano (H, W) donde True = foreground.
La función bajo test (a implementar en make_boxes.py) debe tomar la mask
y devolver la línea YOLO formateada: "0 x_center y_center width height"
"""
import numpy as np
import pytest

from src.data.make_boxes import compute_yolo_box  # aún no existe -> test falla (rojo)


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
    """fondo no uniforme -> rechazo (placeholder: requiere función de detección de máscara RGB,
    no solo compute_yolo_box; ajustar cuando se implemente make_mask_from_rgb)"""
    pytest.skip("Pendiente: requiere implementar detección de máscara RGB con fondo no uniforme")


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


def test_T09_imagen_corrupta():
    """imagen corrupta -> rechazo trazable (placeholder: requiere función de carga de imagen,
    no solo compute_yolo_box; ajustar cuando se implemente load_and_validate_image)"""
    pytest.skip("Pendiente: requiere implementar carga/validación de imagen corrupta")


def test_T10_label_imagen_huerfano():
    """label/imagen huérfano -> gate falla (placeholder: requiere lógica a nivel de pipeline/dataset,
    no de la función unitaria compute_yolo_box; se testea en integración, no acá)"""
    pytest.skip("Pendiente: se valida a nivel de auditoría del dataset completo, no unitariamente")
