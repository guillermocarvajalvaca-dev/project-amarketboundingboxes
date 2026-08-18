"""
Tests para src/data/make_splits.py
Según docs/governance/02_CONTRACTS/DATA_AND_SPLIT_CONTRACT.yaml §split_policy

Reglas clave del contrato:
- group_exclusivity: sku_id, source_asset_id, duplicate_group_id no cruzan splits
- class_rule: class_id 0 debe estar representado en todo split no vacío
- fixed_seed y ratios: resuelto por decisión O-002 del coordinador (16/08/2026)
  seed=42, ratios=(0.70, 0.15, 0.15). Se mantienen como parámetros
  (no hardcodeados) por si el coordinador emite una enmienda futura.
"""
import pandas as pd
import pytest

from src.data.make_splits import make_splits


def sample_manifest():
    """Manifest sintético: 6 SKUs, algunos con múltiples imágenes (mismo sku_id)
    y un grupo de duplicados (mismo duplicate_group_id) para probar exclusividad."""
    rows = [
        # sku_id, source_asset_id, duplicate_group_id
        ("SKU001", "A001", "DUP_A"),
        ("SKU001", "A002", "DUP_A"),  # mismo SKU y mismo dup_group que A001
        ("SKU002", "A003", "DUP_B"),
        ("SKU003", "A004", "DUP_C"),
        ("SKU004", "A005", "DUP_D"),
        ("SKU005", "A006", "DUP_E"),
        ("SKU006", "A007", "DUP_F"),
        ("SKU006", "A008", "DUP_F"),  # mismo SKU y dup_group que A007
    ]
    return pd.DataFrame(rows, columns=["sku_id", "source_asset_id", "duplicate_group_id"])


def test_group_exclusivity_sku():
    """Ningún sku_id debe aparecer en más de un split."""
    manifest = sample_manifest()
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    sku_to_splits = {}
    for _, row in splits.iterrows():
        sku_to_splits.setdefault(row["sku_id"], set()).add(row["split"])

    for sku, split_set in sku_to_splits.items():
        assert len(split_set) == 1, f"sku_id {sku} cruza splits: {split_set}"


def test_group_exclusivity_duplicate_group():
    """Ningún duplicate_group_id debe aparecer en más de un split."""
    manifest = sample_manifest()
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    dup_to_splits = {}
    for _, row in splits.iterrows():
        dup_to_splits.setdefault(row["duplicate_group_id"], set()).add(row["split"])

    for dup_group, split_set in dup_to_splits.items():
        assert len(split_set) == 1, f"duplicate_group_id {dup_group} cruza splits: {split_set}"


def test_todas_las_filas_asignadas():
    """Cada source_asset_id del manifest debe quedar en exactamente un split."""
    manifest = sample_manifest()
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    assert set(splits["source_asset_id"]) == set(manifest["source_asset_id"])
    assert len(splits) == len(manifest)


def test_splits_validos():
    """Los valores de split deben ser solo train/val/test."""
    manifest = sample_manifest()
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    assert set(splits["split"]).issubset({"train", "val", "test"})


def test_idempotencia_con_misma_seed():
    """Misma seed y mismo input -> misma asignación de splits."""
    manifest = sample_manifest()
    splits1 = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)
    splits2 = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    merged = splits1.merge(splits2, on="source_asset_id", suffixes=("_1", "_2"))
    assert (merged["split_1"] == merged["split_2"]).all()


def test_grupos_insuficientes_detiene_gate():
    """Si no hay suficientes grupos SKU para los 3 splits, debe fallar (§6 SDD:
    'G3 se detiene; no se crea independencia artificial mediante copias')."""
    manifest = pd.DataFrame(
        [("SKU001", "A001", "DUP_A"), ("SKU002", "A002", "DUP_B")],
        columns=["sku_id", "source_asset_id", "duplicate_group_id"],
    )
    with pytest.raises(ValueError, match="grupos insuficientes"):
        make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)


def test_class_rule_ningun_split_vacio():
    """§split_policy class_rule: con class_id siempre 0, la regla equivale a
    que ningún split quede vacío si hay grupos suficientes para los 3."""
    manifest = sample_manifest()
    manifest["class_id"] = 0  # dataset de una sola clase, por contrato
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    present_splits = set(splits["split"])
    assert present_splits == {"train", "val", "test"}, (
        f"algún split quedó vacío: presentes={present_splits}"
    )

    for split_name in ("train", "val", "test"):
        rows = splits[splits["split"] == split_name]
        assert (rows["class_id"] == 0).all()
        assert len(rows) > 0


def test_ratios_reales_O_002_reparto_proporcional():
    """Verifica el comportamiento con los valores REALES aprobados por
    decisión O-002 del coordinador (16/08/2026): seed=42,
    ratios=(0.70, 0.15, 0.15). Con manifest más grande para que el
    reparto proporcional sea observable (no solo 1 grupo por split)."""
    rows = []
    for i in range(1, 21):
        sku = f"SKU{i:03d}"
        asset = f"A{i:03d}"
        dup = f"DUP_{i}"
        rows.append((sku, asset, dup))
    manifest = pd.DataFrame(rows, columns=["sku_id", "source_asset_id", "duplicate_group_id"])

    splits = make_splits(manifest, ratios=(0.70, 0.15, 0.15), seed=42)

    assert set(splits["source_asset_id"]) == set(manifest["source_asset_id"])
    assert len(splits) == 20

    counts = splits["split"].value_counts()
    assert set(counts.index) == {"train", "val", "test"}

    # Con 20 grupos de 1 imagen cada uno, train debe llevarse la
    # mayoría clara (proporción esperada ~14/3/3, con margen por el
    # algoritmo greedy de asignación por déficit)
    assert counts["train"] >= counts["val"]
    assert counts["train"] >= counts["test"]
    assert counts["train"] >= 10  # al menos la mitad, dado ratio 0.70
