"""
src/data/make_boxes.py

Genera cajas delimitadoras (bounding boxes) en formato YOLO a partir de una
máscara de primer plano, según el contrato:
docs/governance/02_CONTRACTS/BOUNDING_BOX_ALGORITHM_CONTRACT.md

Autor: Andrés Poiche (BOX-001)
"""
import numpy as np


def compute_yolo_box(mask: np.ndarray, class_id: int = 0) -> str:
    """
    Calcula la caja delimitadora de una máscara booleana de primer plano
    y devuelve la línea en formato YOLO: "class_id x_center y_center width height"

    Sigue §5-§6 del contrato: bordes semiabiertos (x1=x_max+1, y1=y_max+1),
    coordenadas normalizadas con 6 decimales.

    Args:
        mask: array booleano (H, W) donde True = foreground.
        class_id: debe ser 0 (§2 del contrato — dataset monoclase).

    Returns:
        str con la línea YOLO formateada.

    Raises:
        ValueError: si class_id != 0, o si la máscara no tiene foreground.
    """
    if class_id != 0:
        raise ValueError(
            f"class_id debe ser 0 (dataset monoclase 'product'); recibido: {class_id}"
        )

    if mask.ndim != 2:
        raise ValueError(f"mask debe ser 2D (H, W); recibido shape: {mask.shape}")

    H, W = mask.shape

    ys, xs = np.where(mask)
    if xs.size == 0 or ys.size == 0:
        raise ValueError("Máscara vacía: no hay píxeles de foreground (rechazo, sin label).")

    x_min = int(xs.min())
    x_max = int(xs.max())
    y_min = int(ys.min())
    y_max = int(ys.max())

    # Bordes semiabiertos, §5 del contrato
    x0 = x_min
    x1 = x_max + 1
    y0 = y_min
    y1 = y_max + 1

    box_width_px = x1 - x0
    box_height_px = y1 - y0
    x_center_px = (x0 + x1) / 2
    y_center_px = (y0 + y1) / 2

    x_center = x_center_px / W
    y_center = y_center_px / H
    width = box_width_px / W
    height = box_height_px / H

    return f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}"
