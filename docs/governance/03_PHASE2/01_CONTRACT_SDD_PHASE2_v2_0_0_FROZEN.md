# Contract SDD — Phase 2 Multi-Product Extension v2.0.0 — FROZEN

This is an academic-operational agreement, not a legal contract.

## 1. Relationship to Phase 1

Phase 1 remains valid, frozen evidence. Nothing in Phase 2 rewrites its canonical dataset, splits, model, metrics, weight hash, test protocol or conclusions.

Where Phase 1 v1.0.0 prohibited multi-product scenes or RPC without contractual change, this v2.0.0 Phase 2 contract is the approved change for this extension only.

## 2. Phase 2 objective

Extend the validated AMARKET single-product detector toward checkout-like multi-product detection through controlled synthetic scene composition, while preserving reproducibility, exact YOLO geometry, split independence and honest evaluation.

Primary question:

> Does controlled multi-product synthetic augmentation improve multi-product localization while preserving performance on the canonical real AMARKET domain?

Secondary question:

> How do detection quality and measured latency change as scene density increases?

## 3. Canonical Phase 1 baseline

- Real AMARKET canonical images: 655.
- Train: 459.
- Validation: 98.
- Test: 98.
- YOLO class remains exactly `0: product`.
- SKU and category remain metadata, not YOLO classes.
- Existing Phase 1 model remains Experiment A.

## 4. Phase 2 dataset architecture

### Experiment A — baseline

- train: 459 real AMARKET train images;
- validation: 98 real AMARKET validation images;
- test: 98 real AMARKET test images.

### Experiment B — synthetic augmentation

- train: 459 real AMARKET train images + exactly 655 synthetic multi-product scenes = 1114 training images;
- synthetic object sources: canonical AMARKET **train-only** assets;
- validation: same 98 canonical real validation images;
- test: same 98 canonical real test images.

Canonical validation/test products MUST NOT be used as source cutouts for synthetic training scenes.

## 5. Metadata enrichment

Existing AMARKET product pages SHALL be reprocessed without redownloading the product images.

The enrichment attempts to capture, without invention:

- `brand`;
- `technical_product`;
- `size`;
- `units`;
- `materials`;
- `presentation`;
- `category`;
- retrieval status/provenance.

The existing product URL and original manifest values remain authoritative for source identity. Missing metadata is recorded as missing/unknown; it is never inferred silently.

## 6. Synthetic scene counts

| Difficulty | Objects per scene | Scenes |
|---|---:|---:|
| Basic | 2 | 110 |
| Basic | 3 | 110 |
| Medium | 4 | 110 |
| Medium | 5 | 110 |
| Hard | 6 | 50 |
| Hard | 7 | 50 |
| Hard | 8 | 50 |
| Extreme | 9 | 20 |
| Extreme | 10 | 15 |
| Extreme | 11 | 10 |
| Extreme | 12 | 10 |
| Extreme | 13 | 5 |
| Extreme | 14 | 3 |
| Extreme | 15 | 2 |
| **TOTAL** | — | **655** |

Total planned product placements: **3287**.

With 459 canonical train products, the deterministic target usage is:

- 74 source products used 8 times;
- 385 source products used 7 times;
- no source product repeated within a scene.

## 7. Synthetic generation MUST

- use programmatic composition of known AMARKET cutouts;
- preserve exact source lineage for every placement;
- generate YOLO labels from placement/mask geometry;
- produce exactly the planned object count per scene;
- use fixed scene seeds;
- store per-object transforms and hashes;
- validate boxes and object counts automatically;
- reject/regenerate scenes that violate difficulty constraints;
- label synthetic scenes explicitly as synthetic.

AI image-generation prototypes may be used for design ideation only; they are not governed auto-labelled training examples.

## 8. Occlusion semantics

Phase 2 uses the bounding box of the **visible foreground mask after final compositing/z-order**, consistent with the Phase 1 principle of bounding the visible product foreground by pixel extremes.

Maximum occlusion fraction by level:

- Basic: 5%;
- Medium: 15%;
- Hard: 30%;
- Extreme: 45%.

An object whose visible fraction violates the level rule is repositioned or the scene fails/regenerates. Box semantics MUST NOT be mixed inside the governed dataset.

## 9. RPC use

RPC may be used for:

- observed composition/density reference;
- a separately identified external multi-product challenge;
- optional non-governing comparative analysis.

RPC is not presented as AMARKET and is not silently mixed into AMARKET provenance.

For the external challenge, all RPC retail object categories may be collapsed to Phase 2 detector class `0: product` strictly for localization evaluation, while original RPC category IDs remain in challenge metadata.

## 10. Work allocation

Phase 2 has no rigid technical owners.

Any available teammate may claim an unclaimed task when inputs exist. The claimant becomes the temporary executor for that task only.

Any other available teammate who did not author the substantive work may review/approve it.

Self-approval is forbidden.

The coordinator prioritizes the shared task pool, freezes decisions, resolves conflicts and merges approved work.

## 11. Evaluation

Model selection uses validation only.

Canonical test remains locked until the Experiment B model/config/thresholds are frozen.

Report at minimum:

- Precision;
- Recall;
- F1;
- mAP@0.5;
- mAP@0.5:0.95;
- latency in ms/image;
- approximate FPS computed from measured latency;
- device and image size.

External RPC challenge results are labelled out-of-domain/non-governing and reported separately from canonical AMARKET test.

## 12. Rights and publication

Synthetic derivation does not erase source-image rights. Large AMARKET images, derived cutouts and derived synthetic image datasets remain outside public GitHub unless rights explicitly permit publication. Code, small non-image manifests and generator logic may be versioned normally.

## 13. MUST NOT

- modify or overwrite Phase 1 evidence;
- use canonical val/test assets as synthetic training sources;
- fabricate boxes, metrics, failures or categories;
- tune thresholds after observing canonical test;
- describe synthetic scenes as natural photographs;
- claim real-time performance solely because the model is YOLO;
- let an executor approve their own substantive work;
- create process/documentation that is not required for execution, reproducibility, evidence or delivery.

## 14. Activation

Status: `FROZEN / AUTHORIZED` on 2026-08-22 by coordinator instruction.
