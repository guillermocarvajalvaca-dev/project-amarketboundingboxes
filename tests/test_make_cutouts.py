"""Tests focalizados para src.data.make_cutouts (P2-005)."""

from __future__ import annotations

import csv
import hashlib
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.data.make_cutouts import (
    EnrichedManifestError,
    MissingMetadataStatusError,
    NotTrainSplitError,
    build_cutout_library,
    build_foreground_mask,
    ensure_train_only,
    load_enriched_manifest,
    make_cutout,
    process_row,
    validate_enriched_join,
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


def _make_enriched_row(split_row: dict, *, category: str = "", metadata_status: str = "OK") -> dict:
    """Fila de source_assets_enriched.csv coherente con una fila de splits.csv.

    sku_id/sha256/split se copian del split_row para que el join determinista
    (validate_enriched_join) pase por defecto; los tests de discrepancia
    modifican explicitamente estos valores para forzar el rechazo.
    """
    return {
        "source_asset_id": split_row["source_asset_id"],
        "sku_id": split_row["sku_id"],
        "sha256": split_row["source_sha256"],
        "split": split_row["split"],
        "category": category,
        "metadata_status": metadata_status,
    }


def _write_enriched_csv(path: Path, rows: list[dict]) -> None:
    fieldnames = ["source_asset_id", "sku_id", "sha256", "split", "category", "metadata_status"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _build_library(
    tmp_path: Path,
    dataset_root: Path,
    split_rows: list[dict],
    enriched_rows: list[dict],
    **overrides,
) -> dict:
    splits_path = overrides.pop("splits_path", tmp_path / "splits.csv")
    enriched_path = overrides.pop("enriched_manifest_path", tmp_path / "enriched.csv")
    output_root = overrides.pop("output_root", tmp_path / "output")
    manifest_path = overrides.pop("manifest_path", tmp_path / "manifest.csv")

    _write_splits_csv(splits_path, split_rows)
    _write_enriched_csv(enriched_path, enriched_rows)

    kwargs = dict(
        dataset_root=dataset_root,
        splits_path=splits_path,
        enriched_manifest_path=enriched_path,
        output_root=output_root,
        manifest_path=manifest_path,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    kwargs.update(overrides)
    return build_cutout_library(**kwargs)


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

    enriched_row = _make_enriched_row(row)
    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        enriched_row=enriched_row,
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
    enriched_rows = [_make_enriched_row(r) for r in rows]
    output_root = tmp_path / "output"

    summary = _build_library(tmp_path, dataset_root, rows, enriched_rows, output_root=output_root)

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
    enriched_row = _make_enriched_row(row)
    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        enriched_row=enriched_row,
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
    enriched_rows = [_make_enriched_row(r) for r in rows]
    manifest_path = tmp_path / "manifest.csv"

    _build_library(
        tmp_path, dataset_root, rows, enriched_rows,
        output_root=output_root, manifest_path=manifest_path,
    )

    manifest_text = manifest_path.read_text(encoding="utf-8")
    assert str(dataset_root) not in manifest_text
    assert str(output_root) not in manifest_text
    assert str(tmp_path) not in manifest_text


# ---------------------------------------------------------------------------
# P2-005 correccion: join determinista contra source_assets_enriched.csv
# ---------------------------------------------------------------------------

def test_enriched_join_exact_match_by_source_asset_id(tmp_path):
    dataset_root = tmp_path / "dataset"
    rows = [
        _make_split_row(tmp_path, dataset_root, asset_id="j1", split="train", image_arr=_rgba_with_real_alpha()),
        _make_split_row(tmp_path, dataset_root, asset_id="j2", split="val", image_arr=_rgba_with_real_alpha()),
    ]
    enriched_rows = [_make_enriched_row(r) for r in rows]

    summary = _build_library(tmp_path, dataset_root, rows, enriched_rows)

    assert summary["enriched_rows"] == 2
    assert summary["splits_rows"] == 2
    assert summary["join_matched"] == 2
    assert summary["join_missing"] == 0
    assert summary["join_extra"] == 0
    assert summary["sku_mismatches"] == 0
    assert summary["hash_mismatches"] == 0
    assert summary["split_mismatches"] == 0


def test_duplicate_source_asset_id_in_enriched_manifest_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="dup1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_rows = [_make_enriched_row(row), _make_enriched_row(row)]

    splits_path = tmp_path / "splits.csv"
    enriched_path = tmp_path / "enriched.csv"
    _write_splits_csv(splits_path, [row])
    _write_enriched_csv(enriched_path, enriched_rows)

    with pytest.raises(EnrichedManifestError):
        load_enriched_manifest(enriched_path)


def test_missing_source_in_enriched_manifest_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    rows = [
        _make_split_row(tmp_path, dataset_root, asset_id="m1", split="train", image_arr=_rgba_with_real_alpha()),
        _make_split_row(tmp_path, dataset_root, asset_id="m2", split="train", image_arr=_rgba_with_real_alpha()),
    ]
    enriched_rows = [_make_enriched_row(rows[0])]  # falta m2

    with pytest.raises(EnrichedManifestError):
        _build_library(tmp_path, dataset_root, rows, enriched_rows)


def test_extra_source_in_enriched_manifest_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="e1", split="train", image_arr=_rgba_with_real_alpha())
    extra_row = _make_split_row(tmp_path, dataset_root, asset_id="e2-not-in-splits", split="train", image_arr=_rgba_with_real_alpha())
    enriched_rows = [_make_enriched_row(row), _make_enriched_row(extra_row)]

    with pytest.raises(EnrichedManifestError):
        _build_library(tmp_path, dataset_root, [row], enriched_rows)


def test_sku_mismatch_between_manifests_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="sku1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row)
    enriched_row["sku_id"] = "sku-DIFFERENT"

    with pytest.raises(EnrichedManifestError):
        _build_library(tmp_path, dataset_root, [row], [enriched_row])


def test_sha_mismatch_between_manifests_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="sha1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row)
    enriched_row["sha256"] = "0" * 64

    with pytest.raises(EnrichedManifestError):
        _build_library(tmp_path, dataset_root, [row], [enriched_row])


def test_split_mismatch_between_manifests_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="split1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row)
    enriched_row["split"] = "val"

    with pytest.raises(EnrichedManifestError):
        _build_library(tmp_path, dataset_root, [row], [enriched_row])


def test_empty_metadata_status_is_rejected(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="nostatus1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row, metadata_status="")

    with pytest.raises(MissingMetadataStatusError):
        _build_library(tmp_path, dataset_root, [row], [enriched_row])


def test_nonempty_category_is_propagated_literally(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="cat1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row, category="Bebidas")

    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        enriched_row=enriched_row,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert record["category"] == "Bebidas"


def test_empty_category_is_allowed(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="cat2", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row, category="")

    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        enriched_row=enriched_row,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert record["category"] == ""
    assert record["status"] == "accepted"


def test_failed_metadata_status_is_propagated(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="failstatus1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row, metadata_status="FAILED")

    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        enriched_row=enriched_row,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert record["metadata_status"] == "FAILED"


def test_failed_metadata_row_is_still_accepted_as_cutout(tmp_path):
    """metadata_status=FAILED no debe excluir el cutout: la aceptacion depende
    solo de imagen/mascara, nunca del resultado del scraping de metadata."""
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="failaccept1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row, metadata_status="FAILED")

    record = process_row(
        row,
        dataset_root=dataset_root,
        output_root=tmp_path / "output",
        enriched_row=enriched_row,
        alpha_threshold=ALPHA_THRESHOLD,
        background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA,
        min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    assert record["status"] == "accepted"
    assert record["metadata_status"] == "FAILED"


def test_final_schema_contains_category_and_metadata_status(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="schema1", split="train", image_arr=_rgba_with_real_alpha())
    enriched_row = _make_enriched_row(row, category="Snacks", metadata_status="OK")
    manifest_path = tmp_path / "manifest.csv"

    _build_library(tmp_path, dataset_root, [row], [enriched_row], manifest_path=manifest_path)

    with manifest_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert "category" in reader.fieldnames
        assert "metadata_status" in reader.fieldnames
        rows_out = list(reader)
    assert len(rows_out) == 1
    assert rows_out[0]["category"] == "Snacks"
    assert rows_out[0]["metadata_status"] == "OK"


def test_cutout_hash_dimensions_and_path_unaffected_by_metadata(tmp_path):
    """Los campos derivados del cutout (hash/dimensiones/ruta) no deben
    depender de category/metadata_status -- solo de la imagen fuente."""
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="stable1", split="train", image_arr=_rgba_with_real_alpha())

    enriched_ok = _make_enriched_row(row, category="", metadata_status="OK")
    enriched_failed = _make_enriched_row(row, category="Chocolates", metadata_status="FAILED")

    record_ok = process_row(
        row, dataset_root=dataset_root, output_root=tmp_path / "output_ok",
        enriched_row=enriched_ok,
        alpha_threshold=ALPHA_THRESHOLD, background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA, min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )
    record_failed = process_row(
        row, dataset_root=dataset_root, output_root=tmp_path / "output_failed",
        enriched_row=enriched_failed,
        alpha_threshold=ALPHA_THRESHOLD, background_uniformity_tolerance=BG_UNIFORMITY_TOLERANCE,
        foreground_delta=FOREGROUND_DELTA, min_foreground_pixels=MIN_FOREGROUND_PIXELS,
    )

    assert record_ok["cutout_sha256"] == record_failed["cutout_sha256"]
    assert record_ok["cutout_width"] == record_failed["cutout_width"]
    assert record_ok["cutout_height"] == record_failed["cutout_height"]
    assert record_ok["cutout_relative_path"] == record_failed["cutout_relative_path"]


def test_load_enriched_manifest_rejects_duplicates_directly(tmp_path):
    dataset_root = tmp_path / "dataset"
    row = _make_split_row(tmp_path, dataset_root, asset_id="direct-dup", split="train", image_arr=_rgba_with_real_alpha())
    enriched_path = tmp_path / "enriched.csv"
    _write_enriched_csv(enriched_path, [_make_enriched_row(row), _make_enriched_row(row)])

    with pytest.raises(EnrichedManifestError):
        load_enriched_manifest(enriched_path)


def test_validate_enriched_join_passes_for_consistent_manifests(tmp_path):
    dataset_root = tmp_path / "dataset"
    rows = [
        _make_split_row(tmp_path, dataset_root, asset_id="ok1", split="train", image_arr=_rgba_with_real_alpha()),
        _make_split_row(tmp_path, dataset_root, asset_id="ok2", split="test", image_arr=_rgba_with_real_alpha()),
    ]
    enriched_by_id = {r["source_asset_id"]: _make_enriched_row(r) for r in rows}

    result = validate_enriched_join(rows, enriched_by_id)
    assert result["join_missing"] == 0
    assert result["join_extra"] == 0
    assert result["sku_mismatches"] == 0
    assert result["hash_mismatches"] == 0
    assert result["split_mismatches"] == 0
    assert result["join_matched"] == 2


def test_cli_requires_enriched_manifest_argument(tmp_path, monkeypatch, capsys):
    from src.data import make_cutouts

    argv = [
        "make_cutouts.py",
        "--dataset-root", str(tmp_path / "dataset"),
        "--splits", str(tmp_path / "splits.csv"),
        "--output-root", str(tmp_path / "output"),
        "--manifest", str(tmp_path / "manifest.csv"),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        make_cutouts.main()

    captured = capsys.readouterr()
    assert "--enriched-manifest" in captured.err
