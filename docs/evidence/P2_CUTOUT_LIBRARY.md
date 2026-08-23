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
    --enriched-manifest data/manifests/source_assets_enriched.csv \
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

## Correccion P2-005 (cierre de CHANGES_REQUESTED)

**Motivo:** el `CHANGES_REQUESTED` publicado sobre HEAD `7b28554d2734fdf1b44e4bd7e371c144cbc9230d`
senalo que el contrato (`06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md`,
Seccion 2, punto 6) exige registrar "category metadata" por cutout, y el
manifest de esta biblioteca no tenia ningun campo de metadata/categoria.

**Autorizacion:** reasignacion temporal registrada en el comentario
`issuecomment-5386359600` de la PR #40 (`guillermocarvajalvaca-dev` ->
`pablolinares1801`, `AUTHORIZED_SCOPE=MERGE_MAIN_AND_RESOLVE_EXISTING_CHANGES_REQUESTED`,
`ORIGINAL_AUTHOR=andrespoiche`). Ejecutado como implementador temporal — sin
auto-aprobacion, sin merge a `main`, sin tocar documentos de gobernanza
congelados.

**Estado previo -> nuevo:**
- `OLD_HEAD` (PR original): `7b28554d2734fdf1b44e4bd7e371c144cbc9230d`
- `CURRENT_MAIN` (al momento de la correccion): `79ecdfe53ddbe772267957bcc588074622eff14c`
- `NEW_HEAD` (tras `git merge --no-edit origin/main`, previo a este commit): `f6b47ada1beee17a6afb0062fc826e87dd823d4c`
- Merge explicito (no rebase, no force-push): trae `data/manifests/source_assets_enriched.csv`
  (P2-004, ya en `main`) a la rama de P2-005.

**Join deterministico `splits.csv` <-> `source_assets_enriched.csv` (por `source_asset_id`):**

```text
ENRICHED_ROWS=655
SPLITS_ROWS=655
JOIN_MATCHED=655
JOIN_MISSING=0
JOIN_EXTRA=0
SKU_MISMATCHES=0
HASH_MISMATCHES=0
SPLIT_MISMATCHES=0
```

Ningun `source_asset_id` de `splits.csv` quedo sin fila en el manifiesto
enriquecido, ninguno sobro, y `sku_id`/`sha256`/`split` coinciden fila a fila
entre ambos manifiestos — sin excepciones, sin valores inferidos.

**Cambios en el manifest de cutouts (`data/manifests/p2_cutout_library.csv`, 459 filas):**

```text
TRAIN_ROWS=459
CUTOUT_ACCEPTED=459
CATEGORY_NONEMPTY=0
METADATA_STATUS_NONEMPTY=459
METADATA_OK=456
METADATA_FAILED=3
```

Las 3 filas con `metadata_status=FAILED` (scraping de metadata fallido para
ese `sku_id`, sin afectar la aceptacion del cutout) corresponden a los
`sku_id`: `7899620665101`, `309974700139`, `309971879203`. `category` resulto
vacia en las 459 filas (el catalogo no siempre expone categoria; se copia
literalmente, nunca se infiere).

**Los 459 cutouts en si NO se regeneraron** (el dataset/output privados no
estan disponibles en este entorno de correccion) — la correccion es
exclusivamente de lineage/manifest, agregando `category`/`metadata_status`
via el join. Se verifico explicitamente que ningun campo derivado del cutout
cambio:

```text
CUTOUT_HASH_CHANGES=0
CUTOUT_DIMENSION_CHANGES=0
CUTOUT_PATH_CHANGES=0
SOURCE_HASH_CHANGES=0
STATUS_CHANGES=0
```

**Hash del manifest:**

```text
OLD_MANIFEST_SHA256=af8aa89e7b1813e5f64784ff7730f957564509a020bc52041b024c1bd6ec24d4
NEW_MANIFEST_SHA256=1de8ef4176182b92cbc29d64f65e7ac5461a0f9e53b6623fd551cc3b942dcf6b
```

**Tests:** 17 tests nuevos agregados (join exacto, duplicado en manifiesto
enriquecido, fuente faltante, fuente extra, discordancia de sku_id/sha256/split,
`metadata_status` vacio rechazado, `category` no vacia propagada literal,
`category` vacia permitida, `metadata_status=FAILED` propagado, fila FAILED
igual aceptada como cutout, esquema final contiene `category`/`metadata_status`,
campos derivados del cutout no afectados por metadata, `load_enriched_manifest`
rechaza duplicados directamente, `validate_enriched_join` pasa con manifiestos
consistentes, CLI exige `--enriched-manifest`), mas los 11 tests originales
actualizados para pasar `enriched_row`/manifiesto enriquecido.

```text
FOCUSED_TESTS=28/28 PASSED (tests/test_make_cutouts.py)
FULL_SUITE=257/257 PASSED (pytest -q, repo completo)
GIT_DIFF_CHECK=PASS (sin errores de whitespace)
FROZEN_FILES_CHANGED=0 (unico diff propio vs origin/main: src/data/make_cutouts.py,
    tests/test_make_cutouts.py, data/manifests/p2_cutout_library.csv,
    docs/evidence/P2_CUTOUT_LIBRARY.md)
```

**Gobernanza de la correccion:** `SELF_APPROVAL=NO` (no se convirtio el
`CHANGES_REQUESTED` previo en `APPROVED` ni se emitio ninguna review nueva
desde esta cuenta), `MERGE=NO` (no se hizo merge de esta rama a `main`),
`REVIEW_REQUESTED=mbarbacardozo` (re-revision independiente solicitada
explicitamente, conforme a `INDEPENDENT_REREVIEW_REQUIRED` del comentario de
reasignacion).

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

## Tests (ejecucion original, previa a la correccion P2-005)

11 tests focalizados nuevos en `tests/test_make_cutouts.py`:
train aceptado, val rechazado, test rechazado, la biblioteca nunca toca
val/test, metodo alpha, metodo rgb, dimensiones del cutout, alpha del cutout
coincide con la mascara, hash reproducible entre corridas, identidad de
`source_asset_id` preservada, ausencia de rutas absolutas en el manifest.

`pytest tests/test_make_cutouts.py -v`: 11/11 PASSED.
`pytest -q` (suite completa del repo): 108/108 PASSED.

Ver seccion "Correccion P2-005 (cierre de CHANGES_REQUESTED)" arriba para los
resultados de tests actualizados (28/28 focalizados, 257/257 suite completa)
tras agregar el join contra el manifiesto enriquecido.

## Estado

`P2_005=READY_FOR_INDEPENDENT_REREVIEW` (re-revision independiente solicitada
a `mbarbacardozo`; `CHANGES_REQUESTED` original de `pablolinares1801` sobre
HEAD `7b28554d2734fdf1b44e4bd7e371c144cbc9230d` queda resuelto por esta
correccion, sin auto-aprobacion ni merge).
