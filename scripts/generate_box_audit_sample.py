"""
Genera una muestra reproducible para BOX-001 (§7, §9 contrato):
- outputs/box_audit.csv (auditoría de 5 imágenes sintéticas)
- outputs/box_audit_grid.png (grilla visual: imagen + caja dibujada)

No depende del dataset real de Monserrat (SCR-001) — usa imágenes
sintéticas generadas aquí mismo, con seed fija para reproducibilidad.
"""
import csv
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.data.make_boxes import audit_image

OUTPUT_DIR = "outputs"
LABELS_DIR = os.path.join(OUTPUT_DIR, "labels")
IMAGES_DIR = os.path.join(OUTPUT_DIR, "sample_images")
CSV_PATH = os.path.join(OUTPUT_DIR, "box_audit.csv")
GRID_PATH = os.path.join(OUTPUT_DIR, "box_audit_grid.png")

CSV_COLUMNS = [
    "source_asset_id", "sku_id", "class_id", "image_path", "label_path",
    "image_width_px", "image_height_px", "mask_method", "algorithm_version",
    "parameters_hash", "foreground_pixel_count", "x_min", "y_min", "x_max",
    "y_max", "x0", "y0", "x1", "y1", "x_center_px", "y_center_px",
    "box_width_px", "box_height_px", "x_center", "y_center", "width",
    "height", "source_sha256", "status", "rejection_reason",
]


def make_rgba_image(path, w, h, fg_box):
    """fg_box=(x0,y0,x1,y1) semiabierto, o None para máscara vacía (rechazo)."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    if fg_box is not None:
        x0, y0, x1, y1 = fg_box
        arr[y0:y1, x0:x1, 3] = 255
        arr[y0:y1, x0:x1, :3] = [180, 120, 60]
    Image.fromarray(arr, mode="RGBA").save(path)


def build_sample_set():
    """5 imágenes sintéticas: casos normales, borde, y un rechazo."""
    return [
        dict(source_asset_id="SAMPLE_001", sku_id="SKU_A", w=64, h=64, fg_box=(10, 10, 40, 45)),
        dict(source_asset_id="SAMPLE_002", sku_id="SKU_B", w=50, h=80, fg_box=(5, 5, 45, 75)),
        dict(source_asset_id="SAMPLE_003", sku_id="SKU_C", w=64, h=64, fg_box=(0, 0, 64, 64)),  # toca bordes
        dict(source_asset_id="SAMPLE_004", sku_id="SKU_D", w=64, h=64, fg_box=(20, 20, 60, 50)),
        dict(source_asset_id="SAMPLE_005", sku_id="SKU_E", w=64, h=64, fg_box=None),  # rechazo: máscara vacía
    ]


def draw_box_overlay(image_path, row):
    """Dibuja la caja auditada sobre la imagen (fondo blanco para visualizar
    alpha), o marca REJECTED si no se aceptó."""
    rgba = Image.open(image_path).convert("RGBA")
    bg = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    composited = Image.alpha_composite(bg, rgba).convert("RGB")
    draw = ImageDraw.Draw(composited)

    if row["status"] == "accepted":
        draw.rectangle(
            [row["x0"], row["y0"], row["x1"] - 1, row["y1"] - 1],
            outline=(220, 30, 30), width=2,
        )
    return composited


def main():
    os.makedirs(IMAGES_DIR, exist_ok=True)
    os.makedirs(LABELS_DIR, exist_ok=True)

    samples = build_sample_set()
    rows = []
    tiles = []

    for s in samples:
        img_path = os.path.join(IMAGES_DIR, f"{s['source_asset_id']}.png")
        make_rgba_image(img_path, s["w"], s["h"], s["fg_box"])

        row = audit_image(
            image_path=img_path,
            source_asset_id=s["source_asset_id"],
            sku_id=s["sku_id"],
            labels_dir=LABELS_DIR,
            alpha_threshold=127,
            algorithm_version="v1_sample",
        )
        rows.append(row)
        tiles.append(draw_box_overlay(img_path, row))

    # Escritura del CSV (atómica: escribe a .tmp, luego renombra)
    tmp_csv = CSV_PATH + ".tmp"
    with open(tmp_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    os.replace(tmp_csv, CSV_PATH)

    # Grilla visual: todas las tiles en una fila, con padding y banda
    # de etiqueta debajo (texto dibujado DESPUES del resize para que no
    # se corte)
    tile_w, tile_h = 100, 100
    label_band_h = 34
    padding = 10
    grid_w = len(tiles) * (tile_w + padding) + padding
    grid_h = tile_h + label_band_h + 2 * padding
    grid = Image.new("RGB", (grid_w, grid_h), (245, 245, 245))
    draw_grid = ImageDraw.Draw(grid)

    for i, (tile, row) in enumerate(zip(tiles, rows)):
        tile_resized = tile.resize((tile_w, tile_h))
        x = padding + i * (tile_w + padding)
        grid.paste(tile_resized, (x, padding))

        line1 = row["source_asset_id"]
        line2 = "ACCEPTED" if row["status"] == "accepted" else "REJECTED"
        text_color = (20, 120, 20) if row["status"] == "accepted" else (180, 20, 20)
        draw_grid.text((x, padding + tile_h + 4), line1, fill=(0, 0, 0))
        draw_grid.text((x, padding + tile_h + 18), line2, fill=text_color)

    grid.save(GRID_PATH)

    n_accepted = sum(1 for r in rows if r["status"] == "accepted")
    n_rejected = sum(1 for r in rows if r["status"] == "rejected")
    print(f"CSV escrito en: {CSV_PATH}")
    print(f"Grilla visual escrita en: {GRID_PATH}")
    print(f"Total: {len(rows)} | Aceptadas: {n_accepted} | Rechazadas: {n_rejected}")


if __name__ == "__main__":
    main()
