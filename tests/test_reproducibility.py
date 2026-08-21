"""Tests focalizados para src.common.reproducibility."""

from __future__ import annotations

import os
import random
from pathlib import Path

import numpy as np
import pytest

from src.common.reproducibility import (
    MAX_NUMPY_SEED,
    fijar_semillas,
    fingerprint_config,
    serializar_config_canonica,
    sha256_archivo,
    validar_seed,
)


@pytest.mark.parametrize(
    "seed",
    [-1, MAX_NUMPY_SEED + 1],
)
def test_validar_seed_rechaza_fuera_de_rango(seed):
    with pytest.raises(ValueError):
        validar_seed(seed)


@pytest.mark.parametrize(
    "seed",
    [True, 42.0, "42", None],
)
def test_validar_seed_rechaza_no_enteros(seed):
    with pytest.raises(TypeError):
        validar_seed(seed)


def test_fijar_semillas_reproduce_random_y_numpy(monkeypatch):
    monkeypatch.delenv("PYTHONHASHSEED", raising=False)

    evidencia_1 = fijar_semillas(42)

    python_1 = [random.random() for _ in range(5)]
    numpy_1 = np.random.random(5).tolist()

    evidencia_2 = fijar_semillas(42)

    python_2 = [random.random() for _ in range(5)]
    numpy_2 = np.random.random(5).tolist()

    assert python_1 == python_2
    assert numpy_1 == numpy_2
    assert evidencia_1["seed"] == 42
    assert evidencia_2["seed"] == 42
    assert os.environ["PYTHONHASHSEED"] == "42"


def test_fijar_semillas_reproduce_torch():
    torch = pytest.importorskip("torch")

    fijar_semillas(42)
    valores_1 = torch.rand(5)

    fijar_semillas(42)
    valores_2 = torch.rand(5)

    assert torch.equal(valores_1, valores_2)


def test_fingerprint_config_independiente_del_orden():
    config_a = {
        "seed": 42,
        "modelo": "yolo11n.pt",
        "train": {
            "batch": 8,
            "imgsz": 416,
        },
        "splits": [0.70, 0.15, 0.15],
    }

    config_b = {
        "splits": [0.70, 0.15, 0.15],
        "train": {
            "imgsz": 416,
            "batch": 8,
        },
        "modelo": "yolo11n.pt",
        "seed": 42,
    }

    assert (
        serializar_config_canonica(config_a)
        == serializar_config_canonica(config_b)
    )
    assert fingerprint_config(config_a) == fingerprint_config(config_b)


def test_fingerprint_config_cambia_si_cambia_valor():
    config_a = {
        "seed": 42,
        "imgsz": 416,
    }
    config_b = {
        "seed": 42,
        "imgsz": 640,
    }

    assert fingerprint_config(config_a) != fingerprint_config(config_b)


def test_fingerprint_normaliza_path():
    config_path = {
        "data": Path("configs") / "dataset.yaml",
    }
    config_text = {
        "data": "configs/dataset.yaml",
    }

    assert fingerprint_config(config_path) == fingerprint_config(config_text)


def test_config_rechaza_objeto_no_soportado():
    with pytest.raises(TypeError):
        fingerprint_config({"objeto": object()})


def test_sha256_archivo(tmp_path):
    artefacto = tmp_path / "artefacto.bin"
    artefacto.write_bytes(b"amarket-reproducibility")

    assert sha256_archivo(artefacto) == (
        "94353d8c8c3d85baef9f51dbe51e0a6f"
        "04ac7ada9d28867e6c950a2e27ffd9d5"
    )


def test_sha256_archivo_rechaza_ruta_inexistente(tmp_path):
    with pytest.raises(FileNotFoundError):
        sha256_archivo(tmp_path / "missing.bin")