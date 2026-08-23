# ADR-005 — Phase 2 Synthetic Multi-Product + Flexible Execution

Status: `APPROVED`
Date: `2026-08-22`

## Context

Phase 1 validated an end-to-end AMARKET single-product detector. Instructor feedback requires multi-product behavior closer to checkout. Phase 1's rigid allocation also created availability bottlenecks.

The frozen Phase 1 contract prohibited multi-product/RPC use without an approved change.

## Decision

1. Preserve Phase 1 unchanged as Experiment A baseline.
2. Authorize Phase 2 controlled synthetic multi-product augmentation.
3. Generate exactly 655 governed synthetic training scenes from canonical AMARKET train-only source products.
4. Enrich existing AMARKET product pages with observed category/technical metadata without redownloading images.
5. Use RPC as composition reference and external multi-product stress/challenge source.
6. Replace fixed Phase 2 task ownership and fixed reviewer pairs with availability-based claiming/review.
7. Preserve independent review, no-self-approval, protected main, evidence and reproducibility.
8. Use visible-mask post-composition bounding boxes to retain pixel-extremes semantics under occlusion.

## Consequences

Positive:
- directly addresses multi-product requirement;
- removes availability as a fixed-role bottleneck;
- preserves Phase 1 evidence;
- provides exact synthetic label geometry and lineage;
- creates measurable difficulty buckets and latency analysis.

Trade-offs:
- synthetic-to-real domain gap remains a limitation;
- generator QA becomes critical;
- training cost increases;
- RPC challenge is out-of-domain and must be reported separately.

## Rejected

- rebuild project from scratch;
- use all 655 AMARKET products as synthetic train sources;
- auto-label generated AI images without exact geometry;
- use fixed reviewer pairs;
- infer missing AMARKET categories from names when page metadata is absent.
