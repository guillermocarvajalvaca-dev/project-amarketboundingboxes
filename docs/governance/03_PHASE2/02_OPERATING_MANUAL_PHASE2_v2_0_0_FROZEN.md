# Operating Manual — Phase 2 v2.0.0 — FROZEN

## 1. Operating principle

Deadline pressure does not authorize untraceable changes. Phase 2 minimizes process while retaining the controls that protect correctness.

The work model is a **shared critical-path queue**.

There are no fixed module owners in Phase 2.

## 2. Claim → Execute → Review → Close

1. Pick the highest-priority unclaimed task whose inputs exist.
2. Record `CLAIMED_BY` and timestamp in the task pool.
3. Execute only the task scope.
4. Run the task acceptance command/check.
5. Record evidence path/hash/count/output.
6. Set `READY_FOR_REVIEW`.
7. Any other available non-author teammate reproduces the minimum acceptance check.
8. Reviewer sets `PASSED` or `CHANGES_REQUIRED`.
9. Coordinator verifies traceability and merges approved repository work.

No fixed reviewer pairs apply.

## 3. Task states

- `PENDING`
- `CLAIMED`
- `IN_PROGRESS`
- `BLOCKED`
- `READY_FOR_REVIEW`
- `CHANGES_REQUIRED`
- `PASSED`

A task is not complete because a file exists. It is complete when its declared acceptance evidence passes.

## 4. Critical-path priority

P0 — blocks everything:
- locate canonical manifests/splits/images;
- metadata enrichment;
- train-only source inventory;
- cutout generation;
- compositor pilot.

P1 — required for technical result:
- full 655 synthetic generation;
- dataset QA/leakage audit;
- Experiment B training;
- evaluation and latency.

P2 — required for delivery:
- external RPC challenge;
- report/README/site/demo update;
- final run-through.

No optional documentation, refactoring or architectural cleanup enters the critical path unless a failing gate requires it.

## 5. Parallel work

Parallel execution is encouraged only when tasks do not mutate the same files/artifacts.

Examples that may proceed in parallel after inputs exist:

- metadata enrichment implementation and RPC challenge inventory;
- cutout QA and scene-plan verification;
- report wording and site section after metrics schema is frozen.

Two people MUST NOT edit the same substantive file independently without an explicit handoff.

## 6. Metadata enrichment workflow

Input: canonical AMARKET manifest with `product_page_url`.

Output: a new enriched manifest. The original manifest is not modified in place.

The enrichment script:

- fetches product HTML only;
- does not redownload product images;
- applies polite delay/retry;
- extracts only observed fields;
- records missing fields explicitly;
- emits summary counts and failures.

Pilot first on a small sample. Then full 655-page enrichment.

## 7. Synthetic workflow

1. Filter canonical split to 459 train assets.
2. Produce foreground masks/cutouts.
3. Verify cutout inventory and exclusions.
4. Resolve deterministic product usage plan for 3287 slots.
5. Generate 30-scene pilot: 10 Basic, 10 Medium, 10 Hard.
6. Draw QA overlays and inspect geometry/occlusion.
7. Freeze transform rules after pilot PASS.
8. Generate the governed 655 scenes.
9. Run automatic global QA.
10. Build Experiment B training dataset.

Full 655 generation is blocked until the 30-scene pilot passes.

## 8. Model workflow

Experiment A is not retrained merely to recreate existing evidence unless technically required.

Experiment B starts from the declared pre-trained YOLO11n baseline family and uses the same canonical validation/test protocol as Experiment A wherever comparison requires fairness.

Freeze model/config/thresholds before canonical test.

## 9. External RPC challenge

Build a small challenge directly from RPC validation scenes and official COCO annotations.

Target: 30 scenes if time permits:
- 10 Medium: 4–5 objects;
- 10 Hard: 6–10 objects;
- 10 Extreme: 11–15 objects.

If fewer are materialized before deadline, report the exact observed count; do not fabricate balance.

All original RPC object boxes are retained; for detector localization scoring they are mapped to class 0 `product` while source category IDs remain metadata.

## 10. Latency

Record preprocessing, inference and postprocessing when available.

Report pure inference separately from end-to-end latency.

`FPS_inference = 1000 / mean_inference_ms`.

Always report device and image size. Do not call a result `real-time` without defining the target FPS and showing measured evidence.

## 11. Repository rules

- `main` protected.
- branch/PR for substantive change.
- no force push to protected main.
- no self-approval.
- no secrets or `.env` inspection.
- no large AMARKET/RPC image datasets or weights committed publicly.
- no destructive cleanup of unrelated local work.

## 12. Stop-the-Line conditions

Stop only for a material issue:

- leakage;
- wrong source split;
- box/count mismatch;
- missing required source provenance;
- rights/safety issue;
- model evaluated on canonical test before freeze;
- critical command/test failure;
- output not reproducible enough to defend.

Non-critical style/documentation issues do not stop technical execution before the deadline.
