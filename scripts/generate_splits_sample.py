"""
Genera una muestra reproducible para SPL-001 (issue #14):
- data/sample/splits_synthetic.csv (splits sobre manifest sintetico,
  NO es el resultado final real)
- outputs/splits_leakage_evidence.json (evidencia de cero cruces)

Usa los valores REALES aprobados por decisión O-002 del coordinador:
seed=42, ratios=(0.70, 0.15, 0.15). No depende del dataset real de
SCR-001 (bloqueado hasta que se resuelva O-001 y Monserrat ejecute el
crawl completo).
"""
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from src.data.make_splits import make_splits

SAMPLE_DIR = "data/sample"
OUTPUT_DIR = "outputs"
SPLITS_CSV_PATH = os.path.join(SAMPLE_DIR, "splits_synthetic.csv")
EVIDENCE_PATH = os.path.join(OUTPUT_DIR, "splits_leakage_evidence.json")

SEED = 42
RATIOS = (0.70, 0.15, 0.15)


def build_synthetic_manifest(n_skus=30):
    """Manifest sintético: n_skus productos, algunos con múltiples
    imágenes (mismo sku_id) y algunos compartiendo duplicate_group_id,
    simulando el patrón esperado del dataset real de Amarket."""
    rows = []
    for i in range(1, n_skus + 1):
        sku = f"SKU{i:03d}"
        n_images = 2 if i % 5 == 0 else 1  # cada 5to SKU tiene 2 imagenes
        dup_group = f"DUP_{i}" if i % 7 != 0 else f"DUP_{i - 1}"  # algunos comparten dup group
        for j in range(1, n_images + 1):
            rows.append((sku, f"A{i:03d}_{j}", dup_group))
    return pd.DataFrame(rows, columns=["sku_id", "source_asset_id", "duplicate_group_id"])


def verify_no_leakage(splits: pd.DataFrame) -> dict:
    """Verifica exclusividad de grupo y devuelve evidencia estructurada."""
    sku_to_splits = splits.groupby("sku_id")["split"].apply(set).to_dict()
    dup_to_splits = splits.groupby("duplicate_group_id")["split"].apply(set).to_dict()
    asset_to_splits = splits.groupby("source_asset_id")["split"].apply(set).to_dict()

    sku_violations = {k: list(v) for k, v in sku_to_splits.items() if len(v) > 1}
    dup_violations = {k: list(v) for k, v in dup_to_splits.items() if len(v) > 1}
    asset_violations = {k: list(v) for k, v in asset_to_splits.items() if len(v) > 1}

    split_counts = splits["split"].value_counts().to_dict()

    return {
        "seed": SEED,
        "ratios": {"train": RATIOS[0], "val": RATIOS[1], "test": RATIOS[2]},
        "total_rows": len(splits),
        "split_counts": split_counts,
        "sku_cross_split_violations": sku_violations,
        "duplicate_group_cross_split_violations": dup_violations,
        "source_asset_id_cross_split_violations": asset_violations,
        "cero_leakage": (
            len(sku_violations) == 0
            and len(dup_violations) == 0
            and len(asset_violations) == 0
        ),
        "all_splits_non_empty": all(
            split_counts.get(name, 0) > 0 for name in ("train", "val", "test")
        ),
    }


def main():
    os.makedirs(SAMPLE_DIR, exist_ok=True)
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    manifest = build_synthetic_manifest()
    splits = make_splits(manifest, ratios=RATIOS, seed=SEED)

    tmp_csv = SPLITS_CSV_PATH + ".tmp"
    splits.to_csv(tmp_csv, index=False)
    os.replace(tmp_csv, SPLITS_CSV_PATH)

    evidence = verify_no_leakage(splits)

    tmp_evidence = EVIDENCE_PATH + ".tmp"
    with open(tmp_evidence, "w") as f:
        json.dump(evidence, f, indent=2, ensure_ascii=False)
    os.replace(tmp_evidence, EVIDENCE_PATH)

    print(f"splits_synthetic.csv escrito en: {SPLITS_CSV_PATH}")
    print(f"Evidencia de leakage escrita en: {EVIDENCE_PATH}")
    print(json.dumps(evidence, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
