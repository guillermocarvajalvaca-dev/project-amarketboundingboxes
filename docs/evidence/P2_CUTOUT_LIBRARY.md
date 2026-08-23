# P2-005 — Train-only Cutout Library

Evidencia de ejecucion de P2-005 (Phase 2, biblioteca de cutouts).

## Alcance

Genera un cutout RGBA (producto recortado, fondo transparente) por cada una
de las 459 imagenes canonicas de `split=train` del dataset
`AMARKET_YOLO_DATASET_655_SEED42`, para uso exclusivo como fuente de
composicion sintetica en Phase 2 (`06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md`).

`val=98` y `test=98` estan absolutamente prohibidos como fuente. El programa
falla explicitamente (`NotTrainSplitError`) si intenta procesar una fila
cuyo split no sea `train` — verificado por test, no solo por el filtro de
lectura del CSV.

## Implementacion

- `src/data/make_cutouts.py`
- Reutiliza sin reimplementar: `load_and_validate_image`, `make_mask_from_alpha`,
  `make_mask_from_rgb` de `src/data/make_boxes.py`.
- Parametros canonicos desde `configs/dataset.yaml`: `alpha_threshold=127`,
  `background_uniformity_tolerance=5.0`, `foreground_delta=30.0`,
  `min_foreground_pixels=10`.
- No se introdujo ninguna dependencia nueva.
- No se genero contenido con IA generativa; el fondo fuera de la mascara de
  foreground queda transparente (alpha=0), nunca inventado/rellenado.

## Ejecucion real

```text
python src/data/make_cutouts.py \
    --dataset-root <AMARKET_YOLO_DATASET_655_SEED42, Drive privado> \
    --splits data/manifests/splits.csv \
    --output-root <P2_TRAIN_CUTOUTS_459, Drive privado> \
    --manifest data/manifests/p2_cutout_library.csv
```

Exit code: `0`.

## Resultado

```text
TRAIN_EXPECTED=459
TRAIN_ATTEMPTED=459
CUTOUT_ACCEPTED=459
CUTOUT_REJECTED=0
VAL_USED=0
TEST_USED=0
DUPLICATE_SOURCE_IDS=0
MANIFEST_SHA256=af8aa89e7b1813e5f64784ff7730f957564509a020bc52041b024c1bd6ec24d4
```

`CUTOUT_REJECTED=0` — no hubo rechazos que registrar en esta corrida (no se
ajusto ningun parametro para llegar a este resultado; son los mismos
parametros congelados ya usados en BOX-001).

Nota sobre metodo de mascara: las 459 imagenes cayeron por el metodo `rgb`
(fondo uniforme), consistente con lo observado en BOX-001 sobre el corpus
completo de Amarket — ninguna imagen del catalogo tiene canal alfa real
utilizable.

## Verificacion fisica

- 459 archivos `.png` generados en `cutouts/` bajo el `--output-root` privado
  (verificado por conteo directo, no solo por el reporte del programa).
- El manifest (`data/manifests/p2_cutout_library.csv`, committeado, liviano)
  no contiene ninguna ruta absoluta de ninguna maquina — solo
  `source_image_relative_path` (relativo a `--dataset-root`) y
  `cutout_relative_path` (relativo a `--output-root`). Verificado por test
  automatizado (`test_manifest_never_contains_absolute_paths`) y por
  inspeccion manual del CSV real generado.

## Salida NO versionada

Los 459 `.png` de cutouts (contienen contenido de imagenes AMARKET) quedan
exclusivamente en Drive privado (`P2_TRAIN_CUTOUTS_459/cutouts/`), fuera del
repositorio publico — conforme a la regla de no commitear imagenes AMARKET
ni artefactos pesados.

## Tests

11 tests focalizados nuevos en `tests/test_make_cutouts.py`:
train aceptado, val rechazado, test rechazado, la biblioteca nunca toca
val/test, metodo alpha, metodo rgb, dimensiones del cutout, alpha del cutout
coincide con la mascara, hash reproducible entre corridas, identidad de
`source_asset_id` preservada, ausencia de rutas absolutas en el manifest.

`pytest tests/test_make_cutouts.py -v`: 11/11 PASSED.
`pytest -q` (suite completa del repo): 108/108 PASSED.

## Estado

`P2_CUTOUTS=READY_FOR_REVIEW`
