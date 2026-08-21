"""
src/data/make_splits.py

Genera splits train/val/test para el dataset de bounding boxes,
respetando la exclusividad de grupo (sku_id y duplicate_group_id)
según docs/governance/02_CONTRACTS/DATA_AND_SPLIT_CONTRACT.yaml §split_policy.
"""
import random
from collections import defaultdict

import pandas as pd

SPLIT_NAMES = ("train", "val", "test")


def _build_groups(manifest: pd.DataFrame):
    """Une sku_id, source_asset_id y duplicate_group_id en componentes conexos (group_exclusivity, contrato).

    Si dos filas comparten sku_id, o comparten duplicate_group_id,
    o (transitivamente) quedan conectadas por otras filas, todas
    sus imágenes deben terminar en el mismo split.
    """
    parent = {}

    def find(x):
        parent.setdefault(x, x)
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for _, row in manifest.iterrows():
        sku_node = ("sku", row["sku_id"])
        dup_node = ("dup", row["duplicate_group_id"])
        asset_node = ("asset", row["source_asset_id"])
        union(sku_node, dup_node)
        union(sku_node, asset_node)

    groups = defaultdict(list)
    for idx, row in manifest.iterrows():
        sku_node = ("sku", row["sku_id"])
        root = find(sku_node)
        groups[root].append(idx)

    return list(groups.values())


def make_splits(manifest: pd.DataFrame, ratios=(0.7, 0.15, 0.15), seed=42):
    """Asigna cada fila del manifest a un split (train/val/test).

    Respeta exclusividad de grupo: ningún sku_id ni duplicate_group_id
    cruza splits. Los grupos completos (con todas sus filas) se asignan
    a un solo split, buscando acercarse a `ratios` por cantidad de imágenes.

    Si no hay al menos 3 grupos distintos, no es posible garantizar
    independencia real entre los 3 splits y se detiene con ValueError
    (no se crea independencia artificial mediante copias, §6 SDD).
    """
    _validate_manifest_contract(manifest)
    _validate_ratios(ratios)

    groups = _build_groups(manifest)

    if len(groups) < 3:
        raise ValueError(
            f"grupos insuficientes: se necesitan al menos 3 grupos "
            f"independientes para train/val/test, hay {len(groups)}"
        )

    rng = random.Random(seed)
    shuffled = groups[:]
    rng.shuffle(shuffled)

    total_images = sum(len(g) for g in groups)
    targets = {name: ratios[i] * total_images for i, name in enumerate(SPLIT_NAMES)}
    counts = {name: 0 for name in SPLIT_NAMES}

    split_by_row_idx = {}
    for group in shuffled:
        deficit = {name: targets[name] - counts[name] for name in SPLIT_NAMES}
        chosen = max(deficit, key=deficit.get)
        counts[chosen] += len(group)
        for idx in group:
            split_by_row_idx[idx] = chosen

    result = manifest.copy()
    result["split"] = result.index.map(split_by_row_idx)
    return result

REQUIRED_COLUMNS = ("sku_id", "source_asset_id", "duplicate_group_id")


def _validate_manifest_contract(manifest: pd.DataFrame) -> None:
    """Valida columnas obligatorias, ausencia de nulos en identificadores
    de grupo, y class_id == 0 si esa columna esta presente. No admite
    defaults ocultos: cualquier incumplimiento levanta ValueError claro.
    """
    missing = [c for c in REQUIRED_COLUMNS if c not in manifest.columns]
    if missing:
        raise ValueError(
            f"columnas obligatorias faltantes en el manifest: {missing}"
        )

    for col in REQUIRED_COLUMNS:
        if manifest[col].isnull().any():
            raise ValueError(
                f"columna '{col}' contiene valores nulos; los "
                f"identificadores de grupo no pueden ser nulos"
            )

    if "class_id" in manifest.columns:
        if not (manifest["class_id"] == 0).all():
            raise ValueError(
                "class_id debe ser 0 para todas las filas (dataset "
                "monoclase 'product')"
            )


def _validate_ratios(ratios) -> None:
    """Valida que ratios tenga exactamente 3 valores numericos no
    negativos que sumen 1 (con tolerancia de punto flotante)."""
    if len(ratios) != 3:
        raise ValueError(
            f"ratios debe tener exactamente 3 valores (train, val, test); "
            f"recibido: {len(ratios)}"
        )

    for r in ratios:
        if not isinstance(r, (int, float)) or isinstance(r, bool):
            raise ValueError(f"ratios debe contener solo numeros; recibido: {r!r}")
        if r < 0:
            raise ValueError(f"ratios no puede contener valores negativos; recibido: {r}")

    total = sum(ratios)
    if abs(total - 1.0) > 1e-6:
        raise ValueError(
            f"ratios debe sumar 1.0; suma actual: {total}"
        )
