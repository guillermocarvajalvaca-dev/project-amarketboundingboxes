# Phase 2 QA Gates — Minimal Critical Path

Only these gates block Phase 2.

## P2-G0 — Governance Activation

PASS when:
- Phase 2 contract frozen/authorized;
- flexible execution + independent review frozen;
- Phase 1 preservation explicit.

Status on authorization: `PASSED`.

## P2-G1 — Metadata Enrichment

PASS when:
- all canonical product URLs attempted;
- enriched output row count equals input;
- no duplicate source identity;
- category coverage/failures reported;
- no image redownload performed by enrichment script.

## P2-G2 — Synthetic Pilot

PASS when:
- 30 pilot scenes generated: 10 Basic, 10 Medium, 10 Hard;
- planned counts equal label counts;
- visible boxes visually align;
- occlusion constraints pass;
- no val/test source used;
- reviewer distinct from generator author approves.

## P2-G3 — Full Synthetic Dataset

PASS when:
- 655 images + 655 labels;
- 3287 placements/label lines;
- exact difficulty distribution;
- train-only lineage;
- no repeated source inside a scene;
- coordinate/hash/manifest checks pass.

## P2-G4 — Experiment B

PASS when:
- augmented train = 1114 images;
- fine-tuning completes;
- validation evidence captured;
- final weight/config frozen before canonical test.

## P2-G5 — Evaluation / Delivery

PASS when:
- canonical A/B comparison completed without post-test tuning;
- external RPC challenge executed on both frozen models to the achieved sample count;
- latency measured and device/imgsz disclosed;
- report/README/site/demo updated with Phase 2 scope, synthetic limitation and measured evidence;
- final reproducibility smoke check passes.
