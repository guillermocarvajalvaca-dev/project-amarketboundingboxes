# Phase 2 Delivery Update Checklist

## README

- Phase 1 baseline preserved.
- Phase 2 synthetic dataset described as synthetic.
- metadata/category enrichment documented.
- train-only synthetic lineage stated.
- Experiment A/B table added.
- RPC challenge labelled external/out-of-domain.
- latency/device/image-size reported.
- rights/redistribution limitations updated.

## Report

Update only what Phase 2 changes:

- data: synthetic scene construction and counts;
- methodology: visible-mask boxes, difficulty, Experiment B;
- results: A/B canonical comparison + RPC challenge + latency;
- limitations: synthetic domain gap, RPC domain shift;
- conclusions/future work.

Keep report length requirement in mind; move implementation detail to appendix/repo if necessary.

## Site / HTML

Add one compact Phase 2 section:

- why multi-product;
- Basic/Medium/Hard/Extreme;
- 655 synthetic scenes / 3287 placements;
- A vs B metrics;
- RPC challenge;
- CPU latency/FPS;
- limitation statement.

## Demo

1. show Phase 1 baseline briefly;
2. show generated multi-product scene with boxes;
3. run frozen model on multi-product example;
4. show latency;
5. state what is canonical vs external challenge.

## Final gate

No fabricated results. If a planned artifact is not completed by delivery, state the exact achieved scope and evidence.
