"""Utilidades comunes de reproducibilidad del proyecto.

Este módulo concentra dos operaciones pequeñas y auditables:

1. fijar las fuentes de aleatoriedad controlables desde Python;
2. obtener una huella SHA-256 canónica de una configuración efectiva.

No promete determinismo bit-a-bit entre hardware, sistemas operativos o
versiones diferentes de librerías. PYTHONHASHSEED solamente controla de forma
completa el hash aleatorio del intérprete cuando está definido antes de iniciar
Python; aquí también se registra esa limitación explícitamente.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np


MAX_NUMPY_SEED = (2**32) - 1


def validar_seed(seed: int) -> int:
    """Valida una semilla compatible con NumPy RandomState."""
    if isinstance(seed, bool) or not isinstance(seed, int):
        raise TypeError("seed debe ser un entero")

    if not 0 <= seed <= MAX_NUMPY_SEED:
        raise ValueError(
            f"seed debe estar entre 0 y {MAX_NUMPY_SEED}"
        )

    return seed


def fijar_semillas(seed: int) -> dict[str, Any]:
    """Fija las fuentes de aleatoriedad controlables del proceso.

    Devuelve evidencia estructurada de la operación. La función no afirma
    determinismo entre hardware o versiones distintas.
    """
    seed = validar_seed(seed)

    pythonhashseed_previo = os.environ.get("PYTHONHASHSEED")

    # Tiene efecto completo sobre hashing solo si está presente antes de
    # arrancar el intérprete. Sí queda disponible para procesos hijos.
    os.environ["PYTHONHASHSEED"] = str(seed)

    random.seed(seed)
    np.random.seed(seed)

    torch_disponible = False
    cuda_disponible = False

    try:
        import torch
    except ImportError:
        torch = None
    else:
        torch_disponible = True
        torch.manual_seed(seed)

        cuda_disponible = bool(torch.cuda.is_available())

        if cuda_disponible:
            torch.cuda.manual_seed_all(seed)

        cudnn = getattr(torch.backends, "cudnn", None)

        if cudnn is not None:
            cudnn.deterministic = True
            cudnn.benchmark = False

    return {
        "seed": seed,
        "pythonhashseed_previo": pythonhashseed_previo,
        "pythonhashseed_declarado": os.environ["PYTHONHASHSEED"],
        "torch_disponible": torch_disponible,
        "cuda_disponible": cuda_disponible,
        "alcance": (
            "Semillas fijadas para random, numpy y torch cuando está "
            "disponible. No se garantiza determinismo bit-a-bit entre "
            "hardware, sistemas operativos o versiones diferentes. "
            "PYTHONHASHSEED solo controla completamente el hashing del "
            "intérprete cuando se define antes de iniciar Python."
        ),
    }


def _normalizar_config(valor: Any) -> Any:
    """Convierte una configuración a tipos JSON canónicos y explícitos."""
    if valor is None or isinstance(valor, (str, int, float, bool)):
        return valor

    if isinstance(valor, Path):
        return valor.as_posix()

    if isinstance(valor, Mapping):
        return {
            str(clave): _normalizar_config(contenido)
            for clave, contenido in sorted(
                valor.items(),
                key=lambda item: str(item[0]),
            )
        }

    if isinstance(valor, Sequence) and not isinstance(
        valor,
        (str, bytes, bytearray),
    ):
        return [_normalizar_config(item) for item in valor]

    raise TypeError(
        "tipo no soportado en configuración reproducible: "
        f"{type(valor).__name__}"
    )


def serializar_config_canonica(config: Mapping[str, Any]) -> bytes:
    """Serializa una configuración semánticamente equivalente igual."""
    if not isinstance(config, Mapping):
        raise TypeError("config debe ser un mapping")

    normalizada = _normalizar_config(config)

    texto = json.dumps(
        normalizada,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )

    return texto.encode("utf-8")


def fingerprint_config(config: Mapping[str, Any]) -> str:
    """Devuelve SHA-256 de la representación canónica de una configuración."""
    return hashlib.sha256(
        serializar_config_canonica(config)
    ).hexdigest()


def sha256_archivo(path: str | Path) -> str:
    """Calcula SHA-256 de un artefacto sin cargarlo entero en memoria."""
    ruta = Path(path)

    if not ruta.is_file():
        raise FileNotFoundError(ruta)

    digest = hashlib.sha256()

    with ruta.open("rb") as handle:
        for bloque in iter(
            lambda: handle.read(1024 * 1024),
            b"",
        ):
            digest.update(bloque)

    return digest.hexdigest()