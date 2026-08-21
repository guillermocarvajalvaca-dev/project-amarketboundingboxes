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


def test_group_exclusivity_source_asset_id():
    """Hallazgo Monserrat (PR #23): verificar explícitamente que un mismo
    source_asset_id no cruce splits, según group_exclusivity del contrato
    (sku_id, source_asset_id, duplicate_group_id)."""
    manifest = sample_manifest()
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    asset_to_splits = {}
    for _, row in splits.iterrows():
        asset_to_splits.setdefault(row["source_asset_id"], set()).add(row["split"])

    for asset, split_set in asset_to_splits.items():
        assert len(split_set) == 1, f"source_asset_id {asset} cruza splits: {split_set}"


def test_group_exclusivity_source_asset_id_independiente_de_sku():
    """Caso borde: dos source_asset_id distintos con el mismo sku_id pero
    SIN compartir duplicate_group_id deben seguir en el mismo split
    (porque comparten sku_id), confirmando que la unión por
    source_asset_id no rompe la lógica existente de sku_id."""
    manifest = pd.DataFrame(
        [
            ("SKU100", "A100_1", "DUP_X"),
            ("SKU100", "A100_2", "DUP_Y"),  # mismo sku, distinto dup_group
            ("SKU200", "A200_1", "DUP_Z"),
            ("SKU300", "A300_1", "DUP_W"),
        ],
        columns=["sku_id", "source_asset_id", "duplicate_group_id"],
    )
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    sku100_rows = splits[splits["sku_id"] == "SKU100"]
    assert sku100_rows["split"].nunique() == 1, (
        "Filas del mismo sku_id deben quedar en el mismo split, "
        "incluso con distinto duplicate_group_id"
    )


def test_group_exclusivity_source_asset_id_aislado():
    """Hallazgo Guillermo (PR #23, code owner review): caso aislado
    donde el mismo source_asset_id aparece en filas con sku_id Y
    duplicate_group_id DISTINTOS (a diferencia del test anterior, que
    solo aislaba sku_id). Verifica que la exclusividad de
    source_asset_id se cumpla incluso en este caso adversarial."""
    manifest = pd.DataFrame(
        [
            ("SKU_A", "SHARED_ASSET", "DUP_1"),
            ("SKU_B", "SHARED_ASSET", "DUP_2"),  # mismo asset, sku Y dup distintos
            ("SKU_C", "A_OTHER_1", "DUP_3"),
            ("SKU_D", "A_OTHER_2", "DUP_4"),
        ],
        columns=["sku_id", "source_asset_id", "duplicate_group_id"],
    )
    splits = make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)

    shared_rows = splits[splits["source_asset_id"] == "SHARED_ASSET"]
    assert shared_rows["split"].nunique() == 1, (
        "SHARED_ASSET aparece en mas de un split pese a compartir "
        "source_asset_id, aunque sku_id y duplicate_group_id difieran"
    )


def test_columnas_obligatorias_faltantes_da_error_claro():
    """Hallazgo Guillermo: falta de columnas obligatorias debe dar
    ValueError claro, no un KeyError críptico de pandas."""
    manifest = pd.DataFrame(
        [("SKU001", "A001")],
        columns=["sku_id", "source_asset_id"],  # falta duplicate_group_id
    )
    with pytest.raises(ValueError, match="columnas obligatorias faltantes"):
        make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)


def test_valores_nulos_en_identificadores_de_grupo_da_error():
    """Hallazgo Guillermo: nulos en sku_id/source_asset_id/duplicate_group_id
    deben rechazarse explícitamente."""
    manifest = pd.DataFrame(
        [
            ("SKU001", "A001", "DUP_A"),
            (None, "A002", "DUP_B"),
            ("SKU003", "A003", "DUP_C"),
        ],
        columns=["sku_id", "source_asset_id", "duplicate_group_id"],
    )
    with pytest.raises(ValueError, match="valores nulos"):
        make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)


def test_class_id_distinto_de_cero_da_error():
    """Hallazgo Guillermo: si class_id está presente, debe ser 0 en
    todas las filas (dataset monoclase)."""
    manifest = sample_manifest()
    manifest["class_id"] = 0
    manifest.loc[0, "class_id"] = 1  # una fila con clase incorrecta

    with pytest.raises(ValueError, match="class_id debe ser 0"):
        make_splits(manifest, ratios=(0.5, 0.25, 0.25), seed=42)


def test_ratios_con_numero_incorrecto_de_valores_da_error():
    """Hallazgo Guillermo: ratios debe tener exactamente 3 valores."""
    manifest = sample_manifest()
    with pytest.raises(ValueError, match="exactamente 3 valores"):
        make_splits(manifest, ratios=(0.5, 0.5), seed=42)


def test_ratios_negativos_da_error():
    """Hallazgo Guillermo: ratios no puede contener valores negativos."""
    manifest = sample_manifest()
    with pytest.raises(ValueError, match="valores negativos"):
        make_splits(manifest, ratios=(0.8, 0.3, -0.1), seed=42)


def test_ratios_no_numericos_da_error():
    """Hallazgo Guillermo: ratios debe contener solo números."""
    manifest = sample_manifest()
    with pytest.raises(ValueError, match="solo numeros"):
        make_splits(manifest, ratios=(0.5, 0.25, "resto"), seed=42)


def test_ratios_que_no_suman_uno_da_error():
    """Hallazgo Guillermo: ratios debe sumar 1.0."""
    manifest = sample_manifest()
    with pytest.raises(ValueError, match="debe sumar 1.0"):
        make_splits(manifest, ratios=(0.5, 0.3, 0.3), seed=42)
