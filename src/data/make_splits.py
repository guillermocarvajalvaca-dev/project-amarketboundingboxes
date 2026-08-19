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
