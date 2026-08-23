# Phase 2 Governance Package — v2.0.0 FROZEN

Status: `FROZEN / AUTHORIZED`
Authorization date: `2026-08-22` (America/La_Paz)
Deadline: delivery on `2026-08-23`.

This package governs the Phase 2 extension of Project AmarketBoundingBoxes.

## Governing intent

Phase 1 remains preserved as the validated single-product baseline. Phase 2 adds a reproducible multi-product synthetic augmentation experiment and an external RPC multi-product challenge, without rewriting Phase 1 evidence.

## Non-negotiable operating model

- Execution is availability-based: any available teammate may claim any unclaimed task for which inputs exist.
- Review is also availability-based: any other available teammate may review/approve.
- No one may approve their own substantive work.
- `main` remains protected; substantive changes enter through PR + independent review.
- The coordinator may prioritize, freeze decisions and merge approved work.
- No fixed module ownership applies to Phase 2 execution.

## Critical path

1. Enrich existing AMARKET product pages with category and technical metadata; do not redownload images.
2. Identify the 459 canonical train assets.
3. Create train-only cutouts/masks.
4. Implement deterministic multi-product compositor.
5. Generate and QA a 30-scene pilot.
6. Generate exactly 655 governed synthetic training scenes.
7. Train Experiment B: 459 real train + 655 synthetic.
8. Compare against Phase 1 Experiment A on unchanged real validation/test.
9. Evaluate both frozen models on an external RPC multi-product challenge.
10. Record latency, update report/README/site/demo and close delivery.

See the numbered governing documents in this package.
