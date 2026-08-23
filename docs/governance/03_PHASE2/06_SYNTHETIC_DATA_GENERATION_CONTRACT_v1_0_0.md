# Synthetic Multi-Product Generation Contract — Phase 2 v1.0.0

## 1. Governing source library

Only the canonical 459 AMARKET train assets may provide cutouts for the 655 synthetic training scenes.

## 2. Cutout generation

For each source:

1. load canonical image;
2. reuse the existing foreground/background logic where applicable;
3. compute foreground mask;
4. crop to foreground pixel extremes;
5. export RGBA cutout or equivalent mask+RGB representation;
6. record source asset/hash, crop box, cutout dimensions/hash and category metadata.

Do not introduce a new dependency solely for background removal unless explicitly authorized after the existing method is shown insufficient.

## 3. Scene plan

`10_SCENE_PLAN_655.csv` governs the exact number of scenes, difficulty, object count and scene seed.

The generator may not silently change scene counts.

## 4. Product usage

There are 3287 placement slots.

Given 459 eligible source products:

- first 74 source IDs under the frozen deterministic ordering receive 8 slots each;
- remaining 385 receive 7 slots each.

Assignment must avoid repeating a source product within one scene. If deterministic assignment encounters a collision, rotate/advance through the queue deterministically and record the final assignment.

Category is recorded for analysis. Category-aware composition may be added only if it remains deterministic and does not delay the required dataset; initial governing generation may use unrestricted category mixing.

## 5. Canvas and transforms

Initial governed canvas: `1280 x 1280` pixels.

| Level | Scale factor | Rotation | Max occlusion fraction |
|---|---|---|---|
| Basic | 0.75–1.10 | -15°..+15° | 0.05 |
| Medium | 0.65–1.10 | -25°..+25° | 0.15 |
| Hard | 0.55–1.05 | -35°..+35° | 0.30 |
| Extreme | 0.45–1.00 | -45°..+45° | 0.45 |

All transforms are sampled from the scene seed.

## 6. Placement

- place exactly `n_products` distinct cutouts;
- keep transformed objects inside canvas;
- allow overlap only within difficulty rule;
- bounded placement retries;
- if placement fails, regenerate deterministically under a documented retry sub-seed; never reduce object count silently.

## 7. Visible box semantics

After final z-order composition, compute each object's **visible mask**.

`occlusion_fraction = 1 - visible_area / transformed_foreground_area`.

Reject/reposition when the level maximum is exceeded.

YOLO bbox is the axis-aligned pixel-extremes box of that final visible mask.

If visible area is zero, the placement is invalid.

## 8. YOLO conversion

For visible pixel extremes `(xmin, ymin, xmax, ymax)` and canvas `(W,H)`, use inclusive pixel semantics:

- `x1 = xmin`
- `y1 = ymin`
- `x2 = xmax + 1`
- `y2 = ymax + 1`
- `xc = ((x1+x2)/2)/W`
- `yc = ((y1+y2)/2)/H`
- `w = (x2-x1)/W`
- `h = (y2-y1)/H`

Write exactly:

`0 xc yc w h`

with six decimals.

The label file MUST contain exactly the planned number of object lines.

## 9. Scene manifest

Record at minimum:

- `scene_id`;
- `difficulty`;
- `seed`;
- planned/actual object count;
- source asset IDs/SKUs/categories;
- cutout hashes;
- per-object scale/rotation/position/z-order;
- transformed area;
- visible area;
- occlusion fraction;
- pixel box;
- YOLO box;
- output image hash;
- output label hash;
- generator version/commit.

## 10. Pilot gate

Before the full run, generate exactly 30 pilot scenes:

- 10 Basic;
- 10 Medium;
- 10 Hard.

Pilot PASS requires automatic box/count checks and human visual review by a non-author reviewer.

## 11. Full-run acceptance

- exactly 655 images;
- exactly 655 label files;
- exactly 3287 label lines/placements;
- no val/test source product used;
- no scene with repeated source product;
- every coordinate within YOLO bounds;
- no empty visible mask;
- difficulty distribution equals scene plan;
- hashes/lineage manifest complete.
