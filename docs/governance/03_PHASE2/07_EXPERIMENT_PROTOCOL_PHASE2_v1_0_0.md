# Experiment Protocol — Phase 2 v1.0.0

## Experiment A

Existing Phase 1 baseline. Do not retrain unless required to reproduce missing evidence.

- train: 459 real AMARKET;
- val: 98 real AMARKET;
- test: 98 real AMARKET.

## Experiment B

- train: 459 real AMARKET + 655 governed synthetic = 1114 images;
- val: same 98 real AMARKET;
- test: same 98 real AMARKET.

Use pre-trained YOLO11n fine-tuning. Keep comparison settings aligned with Experiment A where technically possible; any change must be declared.

## Selection

Use validation only to select/freeze Experiment B.

Before canonical test, freeze:

- model weight hash;
- resolved configuration;
- image size;
- confidence/IoU evaluation thresholds;
- environment/device declaration.

## Canonical evaluation

Evaluate A and B on the same canonical real AMARKET test protocol. Do not use test for tuning.

## External multi-product challenge

Evaluate frozen A and B on the same RPC challenge after model freeze.

Challenge is explicitly out-of-domain/non-governing for AMARKET. It measures multi-product behavior and density sensitivity, not canonical AMARKET accuracy.

## Metrics

For canonical and challenge where valid:

- Precision;
- Recall;
- F1;
- mAP@0.5;
- mAP@0.5:0.95.

For challenge additionally report by density bucket where sample size permits.

## Latency

Record:

- preprocessing ms/image;
- inference ms/image;
- postprocessing ms/image;
- end-to-end ms/image if measured;
- approximate inference FPS = `1000 / mean_inference_ms`;
- device;
- image size;
- batch size.

Do not call performance real-time without stating a target FPS and measured result.

## Interpretation

Phase 2 remains scientifically successful if B does not outperform A, provided the generator is valid, no leakage occurred, comparison is fair and the result is reported without post-test tuning.
