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


def make_mask_from_alpha(rgba: np.ndarray, alpha_threshold: float) -> np.ndarray:
    """
    Genera máscara de foreground desde un canal alpha real (RGBA), §4 del contrato.

    Args:
        rgba: array (H, W, 4) uint8.
        alpha_threshold: umbral por encima del cual un píxel es foreground.

    Returns:
        máscara booleana (H, W).

    Raises:
        ValueError: si el canal alpha está completamente opaco (no demuestra
        transparencia real; debe procesarse como caso RGB en su lugar).
    """
    if rgba.ndim != 3 or rgba.shape[2] != 4:
        raise ValueError(f"Se esperaba array RGBA (H,W,4); recibido shape: {rgba.shape}")

    alpha = rgba[:, :, 3].astype(float)

    if np.all(alpha == 255) or np.all(alpha == alpha.max()):
        raise ValueError(
            "Canal alpha completamente opaco: no demuestra fondo transparente real, "
            "usar make_mask_from_rgb en su lugar."
        )

    return alpha > alpha_threshold


def make_mask_from_rgb(
    rgb: np.ndarray,
    background_uniformity_tolerance: float,
    foreground_delta: float,
    min_foreground_pixels: int,
) -> np.ndarray:
    """
    Genera máscara de foreground desde una imagen RGB con fondo uniforme, §4 del contrato.

    Pasos (según contrato):
    1. Reunir píxeles del borde.
    2. Calcular color de fondo por mediana de canal.
    3. Verificar uniformidad del borde con tolerancia configurada.
    4. Calcular distancia de cada píxel al fondo.
    5. Marcar primer plano cuando la distancia supera foreground_delta.
    6. Rechazar si fondo, máscara o número de componentes no satisfacen el contrato.

    Args:
        rgb: array (H, W, 3) uint8.
        background_uniformity_tolerance: desviación máxima permitida en el borde.
        foreground_delta: distancia mínima al color de fondo para ser foreground.
        min_foreground_pixels: mínimo de píxeles foreground para aceptar la máscara.

    Returns:
        máscara booleana (H, W).

    Raises:
        ValueError: si el fondo no es uniforme, o si el foreground resultante
        es menor a min_foreground_pixels (rechazo).
    """
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError(f"Se esperaba array RGB (H,W,3); recibido shape: {rgb.shape}")

    H, W, _ = rgb.shape

    # 1. Reunir píxeles del borde
    border_pixels = np.concatenate([
        rgb[0, :, :],
        rgb[-1, :, :],
        rgb[:, 0, :],
        rgb[:, -1, :],
    ], axis=0).astype(float)

    # 2. Color de fondo por mediana de canal
    background_color = np.median(border_pixels, axis=0)

    # 3. Verificar uniformidad del borde
    border_distances = np.linalg.norm(border_pixels - background_color, axis=1)
    if border_distances.std() > background_uniformity_tolerance:
        raise ValueError(
            f"fondo no uniforme: desviación del borde ({border_distances.std():.2f}) "
            f"excede la tolerancia ({background_uniformity_tolerance})"
        )

    # 4. Distancia de cada píxel al fondo
    pixel_distances = np.linalg.norm(rgb.astype(float) - background_color, axis=2)

    # 5. Foreground cuando la distancia supera foreground_delta
    mask = pixel_distances > foreground_delta

    # 6. Rechazar si el foreground es insuficiente
    if mask.sum() < min_foreground_pixels:
        raise ValueError(
            f"foreground insuficiente: {mask.sum()} píxeles, mínimo requerido: {min_foreground_pixels}"
        )

    return mask


def load_and_validate_image(path: str) -> np.ndarray:
    """
    Carga una imagen desde disco y valida que sea decodificable, §3 del contrato:
    "imagen decodificable con W>0, H>0".

    Args:
        path: ruta al archivo de imagen.

    Returns:
        array numpy (H, W, C) con la imagen decodificada.

    Raises:
        ValueError: si el archivo no es decodificable como imagen, o si
        W<=0 o H<=0 (rechazo trazable, §9 del contrato T09).
    """
    from PIL import Image, UnidentifiedImageError

    try:
        img = Image.open(path)
        img.load()  # fuerza la decodificación completa, no solo el header
    except (UnidentifiedImageError, OSError) as e:
        raise ValueError(f"Imagen no decodificable en '{path}': {e}") from e

    arr = np.array(img)

    if arr.ndim < 2:
        raise ValueError(f"Imagen no decodificable en '{path}': shape inválido {arr.shape}")

    H, W = arr.shape[0], arr.shape[1]
    if W <= 0 or H <= 0:
        raise ValueError(f"Imagen no decodificable en '{path}': W={W}, H={H} debe ser >0")

    return arr


def check_no_orphans(images_dir: str, labels_dir: str) -> None:
    """T10 (§8 contrato): verifica que no haya imágenes ni labels huérfanos.

    Un huérfano es:
    - una imagen sin su .txt correspondiente (mismo nombre base), o
    - un label .txt sin su imagen correspondiente.

    El gate falla (ValueError) si se encuentra al menos un huérfano.
    No modifica ni borra nada; solo detecta y reporta.
    """
    import os

    image_exts = (".jpg", ".jpeg", ".png", ".bmp", ".webp")

    image_stems = {
        os.path.splitext(f)[0]
        for f in os.listdir(images_dir)
        if os.path.splitext(f)[1].lower() in image_exts
    }
    label_stems = {
        os.path.splitext(f)[0]
        for f in os.listdir(labels_dir)
        if f.lower().endswith(".txt")
    }

    orphan_images = sorted(image_stems - label_stems)
    orphan_labels = sorted(label_stems - image_stems)

    if orphan_images or orphan_labels:
        details = []
        if orphan_images:
            details.append(f"imágenes huérfanas (sin label): {orphan_images}")
        if orphan_labels:
            details.append(f"labels huérfanos (sin imagen): {orphan_labels}")
        raise ValueError("Gate T10 falla — " + "; ".join(details))


def audit_image(
    image_path: str,
    source_asset_id: str,
    sku_id: str,
    labels_dir: str,
    alpha_threshold: float,
    algorithm_version: str,
    class_id: int = 0,
) -> dict:
    """Procesa una imagen y devuelve una fila de auditoría (§7 contrato):
    29 columnas exactas. Un rechazo conserva fila y no crea .txt.

    Reutiliza load_and_validate_image, make_mask_from_alpha y
    compute_yolo_box; no reimplementa la fórmula YOLO.
    """
    import hashlib
    import json
    import os

    params = {"alpha_threshold": alpha_threshold, "algorithm_version": algorithm_version}
    parameters_hash = hashlib.sha256(
        json.dumps(params, sort_keys=True).encode("utf-8")
    ).hexdigest()

    with open(image_path, "rb") as f:
        file_bytes = f.read()
    source_sha256 = hashlib.sha256(file_bytes).hexdigest()

    row = {
        "source_asset_id": source_asset_id,
        "sku_id": sku_id,
        "class_id": class_id,
        "image_path": image_path,
        "label_path": "",
        "image_width_px": 0,
        "image_height_px": 0,
        "mask_method": "alpha",
        "algorithm_version": algorithm_version,
        "parameters_hash": parameters_hash,
        "foreground_pixel_count": 0,
        "x_min": 0, "y_min": 0, "x_max": 0, "y_max": 0,
        "x0": 0, "y0": 0, "x1": 0, "y1": 0,
        "x_center_px": 0.0, "y_center_px": 0.0,
        "box_width_px": 0, "box_height_px": 0,
        "x_center": 0.0, "y_center": 0.0, "width": 0.0, "height": 0.0,
        "source_sha256": source_sha256,
        "status": "accepted",
        "rejection_reason": "",
    }

    try:
        rgba = load_and_validate_image(image_path)
        h, w = rgba.shape[0], rgba.shape[1]
        row["image_width_px"] = w
        row["image_height_px"] = h

        mask = make_mask_from_alpha(rgba, alpha_threshold)

        ys, xs = mask.nonzero()
        x_min, x_max = int(xs.min()), int(xs.max())
        y_min, y_max = int(ys.min()), int(ys.max())
        x0, y0 = x_min, y_min
        x1, y1 = x_max + 1, y_max + 1
        box_width_px = x1 - x0
        box_height_px = y1 - y0
        x_center_px = x0 + box_width_px / 2
        y_center_px = y0 + box_height_px / 2

        yolo_line = compute_yolo_box(mask, class_id=class_id)
        _, x_center, y_center, width, height = yolo_line.split()

        os.makedirs(labels_dir, exist_ok=True)
        label_path = os.path.join(labels_dir, f"{source_asset_id}.txt")
        with open(label_path, "w") as f:
            f.write(yolo_line + "\n")

        row.update({
            "label_path": label_path,
            "foreground_pixel_count": int(mask.sum()),
            "x_min": x_min, "y_min": y_min, "x_max": x_max, "y_max": y_max,
            "x0": x0, "y0": y0, "x1": x1, "y1": y1,
            "x_center_px": x_center_px, "y_center_px": y_center_px,
            "box_width_px": box_width_px, "box_height_px": box_height_px,
            "x_center": float(x_center), "y_center": float(y_center),
            "width": float(width), "height": float(height),
            "status": "accepted",
            "rejection_reason": "",
        })
    except ValueError as e:
        row["status"] = "rejected"
        row["rejection_reason"] = str(e)
        row["label_path"] = ""

    return row
