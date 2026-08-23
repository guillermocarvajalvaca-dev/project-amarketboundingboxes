# RPC External Challenge Protocol — Phase 2 v1.0.0

## Purpose

Provide a real multi-product, out-of-domain stress test for the frozen AMARKET detectors.

## Source

Use RPC validation images and their official COCO annotations. Preserve RPC provenance and original category IDs in metadata.

## Target sample

If time permits, materialize 30 scenes:

- Medium: 10 scenes with 4–5 annotated objects;
- Hard: 10 scenes with 6–10 objects;
- Extreme: 10 scenes with 11–15 objects.

If the achieved count differs, report the exact count; do not backfill with fabricated scenes.

## Localization mapping

For localization evaluation against the AMARKET monoclasse detector, convert every RPC retail product annotation to YOLO class `0: product`, while retaining original RPC category ID/name separately.

## Isolation

RPC challenge scenes MUST NOT be used to tune Experiment B after model freeze. They are external evaluation/stress-test evidence.

## Reporting

Report separately from canonical AMARKET test:

- sample count by density;
- object count;
- detection metrics where conversion/evaluator supports them;
- qualitative examples;
- latency by scene/density when measured;
- explicit domain-shift limitation.
