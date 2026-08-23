"""Tests focalizados para src.data.make_cutouts (P2-005)."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.data.make_cutouts import (
    NotTrainSplitError,
    build_cutout_library,
    build_foreground_mask,
    ensure_train_only,
    make_cutout,
    process_row,
)

ALPHA_THRESHOLD = 127
BG_UNIFORMITY_TOLERANCE = 5.0
FOREGROUND_DELTA = 30.0
MIN_FOREGROUND_PIXELS = 10


def _write_png(path: Path, arr: np.ndarray) -> None:
    mode = "RGBA" if arr.shape[2] == 4 else "RGB"
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(arr.astype(np.uint8), mode=mode).save(path)


def _rgba_with_real_alpha(size=20, box=(5, 5, 15, 15)):
    """Imagen RGBA con transparencia real: bloque opaco sobre borde transparente."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    x0, y0, x1, y1 = box
    arr[y0:y1, x0:x1, 0:3] = [200, 30, 30]
    arr[y0:y1, x0:x1, 3] = 255
    return arr


def _rgb_uniform_background(size=20, box=(5, 5, 15, 15)):
    """Imagen totalmente opaca (RGBA con alpha=255 en todo) con fondo uniforme
    y un bloque de color muy distinto -- fuerza el fallback a make_mask_from_rgb."""
    arr = np.zeros((size, size, 4), dtype=np.uint8)
    arr[:, :, 0:3] = [255, 255, 255]
    x0, y0, x1, y1 = box
    arr[y0:y1, x0:x1, 0:3] = [10, 10, 200]
    arr[:, :, 3] = 255
    return arr


def _sha256_of_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_split_row(
    tmp_path: Path,
    dataset_root: Path,
    *,
    asset_id: str,
    split: str,
    image_arr: np.ndarray,
    filename: str | None = None,
) -> dict:
    filename = filename or f"{asset_id}.png"
    rel_path = f"images/{split}/{filename}"
    image_path = dataset_root / rel_path
    _write_png(image_path, image_arr)
    return {
        "sku_id": f"sku-{asset_id}",
        "source_asset_id": asset_id,
        "duplicate_group_id": f"dup-{asset_id}",
        "class_id": "0",
        "split": split,
        "image_path": rel_path,
        "label_path": f"labels/{split}/{filename.rsplit('.', 1)[0]}.txt",
        "source_sha256": _sha256_of_file(image_path),
        "box_algorithm_version": "pixel-extremes-v1",
        "parameters_hash": "test-hash",
    }


def _write_splits_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------------
# Regla critica: train aceptado, val/test rechazados
# ---------------------------------------------------------------------------

def test_train_row_is_accepted(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path,
        dataset_root,
        asset_id="aaa111",
        split="train",
        image_arr=_rgba_with_real_alpha(),
    )
    ensure_train_only(row)  # no debe lanzar

    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert record["status"] == "accepted"
    assert (tmp_path / "output" / record["cutout_relative_path"]).is_file()


def test_val_row_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path,
        dataset_root,
        asset_id="bbb222",
        split="val",
        image_arr=_rgba_with_real_alpha(),
    )
    with pytest.raises(NotTrainSplitError):
        ensure_train_only(row)


def test_test_row_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path,
        dataset_root,
        asset_id="ccc333",
        split="test",
        image_arr=_rgba_with_real_alpha(),
    )
    with pytest.raises(NotTrainSplitError):
        ensure_train_only(row)


def test_build_cutout_library_never_touches_val_or_test(tmp_path):
    dataset_root = tmp_path / "dataset"
    rows = [
        _make_split_row(
            tmp_path, dataset_root, asset_id="train1", split="train",
            image_arr=_rgba_with_real_alpha(),
        ),
        _make_split_row(
            tmp_path, dataset_root, asset_id="val1", split="val",
            image_arr=_rgba_with_real_alpha(),
        ),
        _make_split_row(
            tmp_path, dataset_root, asset_id="test1", split="test",
            image_arr=_rgba_with_real_alpha(),
        ),
    ]
    splits_path = tmp_path / "splits.csv"
    _write_splits_csv(splits_path, rows)

    output_root = tmp_path / "output"
    manifest_path = tmp_path / "manifest.csv"

    summary = build_cutout_library(
        dataset_root=dataset_root,
        splits_path=splits_path,
        output_root=output_root,
        manifest_path=manifest_path,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )

    assert summary["train_attempted"] == 1
    assert summary["cutout_accepted"] == 1
    assert summary["val_used"] == 0
    assert summary["test_used"] == 0
    assert not (output_root / "cutouts" / "val1.png").exists()
    assert not (output_root / "cutouts" / "test1.png").exists()


# ---------------------------------------------------------------------------
# Metodos de mascara
# ---------------------------------------------------------------------------

def test_alpha_mask_used_when_real_transparency():
    arr = _rgba_with_real_alpha()
    mask, method = build_foreground_mask(
        arr,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert method == "alpha"
    assert mask.any()


def test_rgb_mask_used_when_fully_opaque():
    arr = _rgb_uniform_background()
    mask, method = build_foreground_mask(
        arr,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert method == "rgb"
    assert mask.any()


# ---------------------------------------------------------------------------
# Geometria y contenido del cutout
# ---------------------------------------------------------------------------

def test_cutout_dimensions_match_pixel_extremes(tmp_path):
    box = (5, 5, 15, 15)
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path, dataset_root, asset_id="dims1", split="train",
        image_arr=_rgba_with_real_alpha(box=box),
    )
    image_path = dataset_root / row["image_path"]

    result = make_cutout(
        image_path,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )

    expected_w = box[2] - box[0]
    expected_h = box[3] - box[1]
    assert result["cutout_width"] == expected_w
    assert result["cutout_height"] == expected_h
    assert result["cutout_image"].size == (expected_w, expected_h)


def test_alpha_cutout_matches_foreground_mask(tmp_path):
    box = (5, 5, 15, 15)
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path, dataset_root, asset_id="alpha1", split="train",
        image_arr=_rgba_with_real_alpha(box=box),
    )
    image_path = dataset_root / row["image_path"]

    result = make_cutout(
        image_path,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )

    cutout_arr = np.array(result["cutout_image"])
    # El bloque entero fue definido como foreground (alpha=255) en el fixture;
    # tras el recorte exacto a los extremos, todo el alpha del cutout debe ser 255.
    assert (cutout_arr[:, :, 3] == 255).all()


def test_hash_is_reproducible_across_runs(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path, dataset_root, asset_id="hash1", split="train",
        image_arr=_rgba_with_real_alpha(),
    )
    image_path = dataset_root / row["image_path"]

    kwargs = dict(
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    result_1 = make_cutout(image_path, **kwargs)
    result_2 = make_cutout(image_path, **kwargs)

    from src.data.make_cutouts import _png_bytes, sha256_bytes

    hash_1 = sha256_bytes(_png_bytes(result_1["cutout_image"]))
    hash_2 = sha256_bytes(_png_bytes(result_2["cutout_image"]))
    assert hash_1 == hash_2


def test_source_identity_is_preserved(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(
        tmp_path, dataset_root, asset_id="identity-xyz", split="train",
        image_arr=_rgba_with_real_alpha(),
    )
    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert record["source_asset_id"] == "identity-xyz"
    assert record["cutout_relative_path"] == "cutouts/identity-xyz.png"


# ---------------------------------------------------------------------------
# Sin rutas absolutas en el manifest
# ---------------------------------------------------------------------------

def test_manifest_never_contains_absolute_paths(tmp_path):
    dataset_root = tmp_path / "dataset_root_abs"
    output_root = tmp_path / "output_root_abs"

    rows = [
        _make_split_row(
            tmp_path, dataset_root, asset_id="pathcheck1", split="train",
            image_arr=_rgba_with_real_alpha(),
        ),
    ]
    splits_path = tmp_path / "splits.csv"
    _write_splits_csv(splits_path, rows)
    manifest_path = tmp_path / "manifest.csv"

    build_cutout_library(
        dataset_root=dataset_root,
        splits_path=splits_path,
        output_root=output_root,
        manifest_path=manifest_path,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )

    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert str(dataset_root) not in manifest_text
    assert str(output_root) not in manifest_text
    assert str(tmp_path) not in manifest_text
