"""
Tests para audit_image en src/data/make_boxes.py
Según docs/governance/02_CONTRACTS/BOUNDING_BOX_ALGORITHM_CONTRACT.md §7
(Auditoría mínima) — 29 columnas exactas, un rechazo conserva fila sin .txt
"""
import os
import numpy as np
import pytest
from PIL import Image

from src.data.make_boxes import audit_image

EXPECTED_COLUMNS = [
    "source_asset_id", "sku_id", "class_id", "image_path", "label_path",
    "image_width_px", "image_height_px", "mask_method", "algorithm_version",
    "parameters_hash", "foreground_pixel_count", "x_min", "y_min", "x_max",
    "y_max", "x0", "y0", "x1", "y1", "x_center_px", "y_center_px",
    "box_width_px", "box_height_px", "x_center", "y_center", "width",
    "height", "source_sha256", "status", "rejection_reason",
]


def make_rgba_image(path, w=10, h=10, fg_box=(2, 1, 6, 5)):
    """Crea una imagen RGBA con un rectángulo opaco (foreground) sobre
    fondo transparente. fg_box = (x0, y0, x1, y1) semiabierto."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    x0, y0, x1, y1 = fg_box
    arr[y0:y1, x0:x1, 3] = 255  # alpha opaco = foreground
    arr[y0:y1, x0:x1, :3] = 128
    Image.fromarray(arr, mode="RGBA").save(path)


def make_empty_rgba_image(path, w=10, h=10):
    """Imagen RGBA totalmente transparente -> máscara vacía -> rechazo."""
    arr = np.zeros((h, w, 4), dtype=np.uint8)
    Image.fromarray(arr, mode="RGBA").save(path)


def test_audit_image_aceptada_tiene_las_29_columnas(tmp_path):
    img_path = tmp_path / "A001.png"
    make_rgba_image(str(img_path))
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    row = audit_image(
        image_path=str(img_path),
        source_asset_id="A001",
        sku_id="SKU001",
        labels_dir=str(labels_dir),
        alpha_threshold=127,
        algorithm_version="v1",
    )

    assert set(row.keys()) == set(EXPECTED_COLUMNS)
    assert row["status"] == "accepted"
    assert row["rejection_reason"] == ""
    assert row["class_id"] == 0
    assert row["label_path"] != ""
    assert os.path.exists(row["label_path"])


def test_audit_image_rechazada_mascara_vacia_no_crea_txt(tmp_path):
    img_path = tmp_path / "A002.png"
    make_empty_rgba_image(str(img_path))
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    row = audit_image(
        image_path=str(img_path),
        source_asset_id="A002",
        sku_id="SKU002",
        labels_dir=str(labels_dir),
        alpha_threshold=127,
        algorithm_version="v1",
    )

    assert row["status"] == "rejected"
    assert row["rejection_reason"] != ""
    assert row["label_path"] == ""
    assert set(row.keys()) == set(EXPECTED_COLUMNS)
    assert list(labels_dir.iterdir()) == []


def test_audit_image_idempotente_mismos_bytes(tmp_path):
    """T07 aplicado a audit_image: mismo input/config dos veces -> mismos
    bytes de label, sin duplicar fila de audit."""
    img_path = tmp_path / "A003.png"
    make_rgba_image(str(img_path))
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    row1 = audit_image(
        image_path=str(img_path), source_asset_id="A003", sku_id="SKU003",
        labels_dir=str(labels_dir), alpha_threshold=127, algorithm_version="v1",
    )
    with open(row1["label_path"], "rb") as f:
        bytes1 = f.read()

    row2 = audit_image(
        image_path=str(img_path), source_asset_id="A003", sku_id="SKU003",
        labels_dir=str(labels_dir), alpha_threshold=127, algorithm_version="v1",
    )
    with open(row2["label_path"], "rb") as f:
        bytes2 = f.read()

    assert bytes1 == bytes2
    assert row1["parameters_hash"] == row2["parameters_hash"]


def test_audit_image_label_escritura_atomica_no_deja_parcial_ante_fallo(tmp_path, monkeypatch):
    """§6 contrato: la escritura del label debe ser atómica. Si falla a
    mitad de camino, no debe quedar ningún archivo .txt parcial ni
    temporal en el directorio de labels."""
    img_path = tmp_path / "A006.png"
    make_rgba_image(str(img_path))
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    import os as os_module

    def failing_replace(*args, **kwargs):
        raise OSError("fallo simulado durante la publicación atómica")

    monkeypatch.setattr(os_module, "replace", failing_replace)

    with pytest.raises(OSError):
        audit_image(
            image_path=str(img_path),
            source_asset_id="A006",
            sku_id="SKU006",
            labels_dir=str(labels_dir),
            alpha_threshold=127,
            algorithm_version="v1",
        )

    monkeypatch.undo()

    remaining_files = list(labels_dir.iterdir())
    assert remaining_files == [], (
        f"no debe quedar ningún archivo tras fallo atómico, encontrado: {remaining_files}"
    )


def test_audit_image_label_atomico_sin_fallo_contenido_correcto(tmp_path):
    """Control: sin fallo, el label se escribe completo y correcto,
    sin dejar archivos temporales sueltos."""
    img_path = tmp_path / "A007.png"
    make_rgba_image(str(img_path))
    labels_dir = tmp_path / "labels"
    labels_dir.mkdir()

    row = audit_image(
        image_path=str(img_path),
        source_asset_id="A007",
        sku_id="SKU007",
        labels_dir=str(labels_dir),
        alpha_threshold=127,
        algorithm_version="v1",
    )

    files = list(labels_dir.iterdir())
    assert len(files) == 1
    assert files[0].name == "A007.txt"
    assert row["label_path"] == str(files[0])
