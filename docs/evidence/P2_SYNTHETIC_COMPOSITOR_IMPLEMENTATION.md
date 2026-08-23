# Evidencia — P2-006 / P2-007: asignación determinista y compositor sintético

- Evidence ID: `EV-P2-006-007-001`
- Gate relacionado: P2-G2 (piloto sintético) — **no cerrado por este documento**
- Tareas: `P2-006` (deterministic usage assignment), `P2-007` (deterministic synthetic compositor)
- Ejecutor: Jose Guilermo Carvajal Vaca (`@guillermocarvajalvaca-dev`)
- Rama: `feat/guillermo/P2-006-007-synthetic-compositor`
- `main` gobernante: `3b4b97d1bd19b2e5625d6432d7b6e57c0b9b4522`
- Commit inicial (auditado y marcado `CHANGES_REQUIRED`): `3ea3488a26438ab2534b04751f73491ea58b1d1c`
- Commit de esta revisión: ver `COMMIT=` en el resultado final del PR #41
- Fecha de ejecución: 2026-08-22

Este documento registra **solo evidencia observada** de implementación y pruebas.
No declara PASS del piloto gobernante ni de la corrida gobernante completa: ambos
exigen los cutouts reales de P2-005 y todavía no se ejecutaron.

## 0. Correcciones de esta revisión (auditoría CHANGES_REQUIRED)

El commit `3ea3488` fue revisado y devuelto con `CHANGES_REQUIRED`. Esta revisión
corrige los 7 puntos señalados, manteniendo el diseño original:

| # | Punto exigido | Corrección aplicada |
|---|---|---|
| 1 | Linaje de categoría | `category` y `metadata_status` son ahora columnas obligatorias del cutout manifest (P2-006), se propagan literalmente a `scene_source_assignments.csv` y al manifiesto final de escenas (P2-007). `metadata_status` no puede ser vacío; `category` puede serlo únicamente cuando `metadata_status` es explícito (siempre lo es, porque es obligatorio). |
| 2 | Procedencia del generador | `generator_commit` es ahora un campo obligatorio del manifiesto de escenas, recibido explícito vía `--generator-commit` (nunca autodetectado ejecutando git). Se valida como SHA hex de 7-40 caracteres. |
| 3 | Integridad de hash de cutout | Antes de cargar cualquier cutout, `generate_scenes()` calcula el sha256 físico del PNG y lo compara contra `cutout_sha256` declarado; cualquier discrepancia aborta con `SceneGenerationError`. Se añadió además `validate_source_lineage_consistency()`, que rechaza apariciones contradictorias (hash/ruta/sku/categoría/estado distintos) del mismo `source_asset_id`. |
| 4 | Gate anti-fuga obligatorio | `--cutout-manifest` y `--generator-commit` son ahora argumentos `required=True` en la CLI de P2-007. `generate_scenes()` y `validate_outputs()` exigen `allowed_source_ids` no-`None`; ya no existe la ruta `LEAKAGE_GATE=OFF`. |
| 5 | Integridad de rutas | `validate_relative_path()` (P2-006) y `resolve_cutout_path()` (P2-007, defensa en profundidad) rechazan rutas absolutas y traversal `..`, y confirman que la ruta resuelta permanece dentro de `cutout_root`. |
| 6 | Consistencia de entrada | `group_assignments()` ahora exige que `difficulty`, `scene_seed` y `planned_n_products` sean idénticos entre todos los placements de una misma escena, en vez de tomar los valores del primer placement leído. |
| 7 | Reporte honesto de tests | Este documento reporta el resultado exacto observado de la suite completa, incluidos los 2 fallos preexistentes y el código de salida real (`1`, FAIL), sin redondear a un PASS agregado. |

## 1. Alcance entregado

| Archivo | Tarea | Contenido |
|---|---|---|
| `src/data/assign_synthetic_sources.py` | P2-006 | Asignación determinista de fuentes train a los 3287 placements, con linaje de categoría e integridad de ruta |
| `src/data/make_synthetic_scenes.py` | P2-007 | Compositor de escenas, geometría de oclusión, verificación de hash de cutout, gates obligatorios, QA automático, modo piloto |
| `tests/test_assign_synthetic_sources.py` | P2-006 | 33 tests |
| `tests/test_make_synthetic_scenes.py` | P2-007 | 71 tests |

Ningún archivo bajo `docs/governance/03_PHASE2/` fue modificado.
`MANIFEST_SHA256.txt` no fue modificado.
No se agregó ninguna dependencia: el compositor usa `numpy` y `pillow`, ya
declaradas en `requirements.txt`.

## 2. Entorno observado

```
Python 3.11.9
numpy 2.4.4
pillow 12.2.0
pytest 9.0.3
```

Nota honesta: el entorno donde se ejecutaron estas pruebas tiene versiones
ligeramente anteriores a los pines de `requirements.txt` (numpy 2.4.6,
pillow 12.3.0, pytest 9.1.1), y **no** tiene `torch`/`ultralytics` instalados.
Esto no afecta a P2-006/P2-007 (que no importan torch) pero sí explica los dos
fallos preexistentes documentados en §7.

## 3. P2-006 — Asignación determinista

### 3.1 Regla de cuotas

La regla del contrato (74 productos con 8 usos, 385 con 7) **no está
hardcodeada**: se deriva de `divmod(total_placements, n_sources)`.

```
divmod(3287, 459) = (7, 74)
=> los primeros 74 source_asset_id del orden lexicográfico reciben 8 usos
=> los 385 restantes reciben 7
```

El orden lexicográfico de `source_asset_id` congela el reparto. La cola de
placements se construye por pasadas completas (pasada *p* incluye toda fuente
con cuota > *p*), lo que separa cada uso de una misma fuente por ~459
posiciones. Las colisiones dentro de escena se resuelven difiriendo el candidato
y reinsertándolo al frente de la cola: rotación determinista, sin aleatoriedad y
sin perder cuota.

### 3.2 Linaje de categoría (corrección punto 1)

El cutout manifest ahora exige `category` y `metadata_status` como columnas
obligatorias (`REQUIRED_CUTOUT_COLUMNS`). Reglas aplicadas en
`load_cutout_library()`:

- `metadata_status` debe ser no vacío para toda fila `accepted`/`train`;
  su ausencia aborta con `AssignmentError`;
- `category` se preserva **literal**, sin normalizar ni inventar; puede quedar
  vacía únicamente porque `metadata_status` (ya obligatorio) documenta el motivo;
- ambos valores se copian sin transformación a cada fila de
  `scene_source_assignments.csv` en `assign_sources()`.

### 3.3 Corrida observada contra el plan congelado

Ejecutada con el plan real `docs/governance/03_PHASE2/10_SCENE_PLAN_655.csv` y
un inventario de cutouts **de fixtures** (459 fuentes sintéticas generadas
programáticamente, ahora con `category`/`metadata_status`), porque la librería
real de P2-005 aún no está mergeada:

```
$ python -m src.data.assign_synthetic_sources \
    --scene-plan docs/governance/03_PHASE2/10_SCENE_PLAN_655.csv \
    --cutout-manifest <ruta privada>/fixture_cutout_library.csv \
    --output <ruta privada>/scene_source_assignments.csv

MODE=GOVERNING
SCENES=655
SOURCES=459
SKIPPED_NOT_ACCEPTED=0
ROWS=3287
USAGE_HISTOGRAM=385x7+74x8
```

Verificación independiente sobre el CSV producido:

```
assignment rows: 3287   scenes: 655   scenes with within-scene duplicates: 0
columns: scene_id, difficulty, scene_seed, planned_n_products, placement_index,
         source_asset_id, sku_id, category, metadata_status,
         cutout_relative_path, cutout_sha256
```

Este ejercicio valida la **forma** gobernante (655/3287/459, el reparto
74×8+385×7, y ahora también la propagación de categoría). La corrida gobernante
definitiva debe repetirse con el manifiesto real de P2-005.

### 3.4 Gate anti-fuga e integridad de rutas

Una fila `status=accepted` con `split` distinto de `train` no se descarta en
silencio: lanza `SplitLeakageError` y aborta la corrida. Las filas
`status != accepted` sí se descartan, contabilizadas en `SKIPPED_NOT_ACCEPTED`.

`validate_relative_path()` rechaza `cutout_relative_path` absoluta (POSIX o con
unidad Windows) o con segmentos `..`, tanto en el cutout manifest (P2-006) como,
por defensa en profundidad, al resolverla contra `cutout_root` en el compositor
(P2-007, `resolve_cutout_path()`).

## 4. P2-007 — Compositor

### 4.1 Geometría de caja visible

La caja YOLO se calcula **exclusivamente sobre `visible_mask`**, nunca sobre el
rectángulo del objeto transformado. La secuencia implementada es:

1. colocar todos los objetos y fijar el z-order (orden de placement, mayor = arriba);
2. `transformed_area` = píxeles foreground (`alpha > 0`) del objeto transformado;
3. `visible_mask` = máscara del objeto menos la unión de todas las máscaras por encima;
4. `occlusion_fraction = 1 - visible_area / transformed_area`;
5. rechazo si `visible_area == 0` o si la oclusión supera el límite del nivel;
6. `compute_yolo_box(visible_mask)` reutilizado de `src/data/make_boxes.py`.

La semántica de píxel se hereda de `make_boxes.py` sin reimplementarse:
`x2 = xmax + 1`, `y2 = ymax + 1`, seis decimales, `class_id = 0`.

### 4.2 Determinismo

Cada escena usa exclusivamente su `scene_seed`. Cada reintento deriva su
sub-seed de forma explícita:

```
derive_attempt_seed(scene_seed, attempt) = (scene_seed * 1_000_003 + attempt * 7_919) mod 2^32
```

No se usa el hash de strings de Python ni el orden de iteración de ningún dict.
La salida es PNG (sin pérdida) para preservar determinismo pixel-perfect.

### 4.3 Integridad de hash de cutout (corrección punto 3)

Antes de cargar cualquier cutout, `generate_scenes()`:

1. resuelve su ruta con `resolve_cutout_path()` (rechaza absolutas/traversal,
   confirma que no escapa de `cutout_root`);
2. calcula el sha256 físico del PNG en disco;
3. lo compara contra `cutout_sha256` declarado en el placement;
4. aborta con `SceneGenerationError` si no coincide.

Además, `validate_source_lineage_consistency()` recorre **todo** el
`assignments.csv` (no solo una escena) y aborta si el mismo `source_asset_id`
aparece con `sku_id`, `category`, `metadata_status`, `cutout_relative_path` o
`cutout_sha256` distintos entre placements.

Verificado end-to-end vía CLI: se sustituyó el PNG físico de un cutout usado en
el piloto (mismo `source_asset_id`, contenido distinto) y se reejecutó
`make_synthetic_scenes` sobre esa misma escena:

```
FAIL: cutout '...\00299a8e....png': sha256 físico 0c384837... !=
cutout_sha256 declarado a218a7f0... (source_asset_id=00299a8e...)
```

### 4.4 Gate anti-fuga y procedencia obligatorios (corrección puntos 2 y 4)

`--cutout-manifest` y `--generator-commit` son `required=True` en la CLI.
Verificado que ambos, si faltan, hacen que `argparse` rechace la invocación
antes de ejecutar nada:

```
$ python -m src.data.make_synthetic_scenes ... (sin --cutout-manifest)
error: the following arguments are required: --cutout-manifest
exit code: 2

$ python -m src.data.make_synthetic_scenes ... (sin --generator-commit)
error: the following arguments are required: --generator-commit
exit code: 2
```

`generate_scenes()` y `validate_outputs()` además rechazan explícitamente
`allowed_source_ids=None` con `ValueError`, así que ningún caller —CLI o
programático— puede generar escenas sin el gate anti-fuga activo. La CLI
siempre imprime `LEAKAGE_GATE=ON` en una corrida exitosa; ya no existe la salida
`LEAKAGE_GATE=OFF`.

### 4.5 Reintentos acotados y conteo de objetos

`MAX_SCENE_ATTEMPTS = 64`, `MAX_PLACEMENT_SAMPLES = 64`. Si una escena no puede
cumplir el contrato, se lanza `SceneGenerationError`: **nunca** se reduce
`n_products` en silencio. Cubierto por
`test_escena_imposible_falla_sin_reducir_objetos`, que fuerza el caso con
cutouts de 900×900 en dificultad `basic`.

### 4.6 Consistencia de entrada dentro de escena (corrección punto 6)

`group_assignments()` exige que todos los placements de una misma escena
declaren el mismo `difficulty`, `scene_seed` y `planned_n_products`; una
discrepancia aborta con `SceneGenerationError` en vez de usar silenciosamente
los valores del primer placement leído.

### 4.7 Piloto de fixtures observado

El piloto **real** (P2-008) no se ejecutó: requiere los cutouts reales de P2-005.
Lo que sí se ejecutó es un piloto de fixtures sintéticos, con el plan de escenas
real, cutouts generados programáticamente (con hash físico verificado) y los
gates obligatorios activos:

```
$ python -m src.data.make_synthetic_scenes \
    --assignments <ruta privada>/scene_source_assignments.csv \
    --cutout-root <ruta privada>/cutouts_root \
    --output-root <ruta privada>/synthetic \
    --manifest <ruta privada>/scene_manifest.csv \
    --cutout-manifest <ruta privada>/fixture_cutout_library.csv \
    --generator-commit 3ea3488a26438ab2534b04751f73491ea58b1d1c \
    --pilot --background-rgb "255,255,255"

GENERATOR_VERSION=p2-synthetic-compositor/1.0.0
GENERATOR_COMMIT=3ea3488a26438ab2534b04751f73491ea58b1d1c
MODE=PILOT
SCENES=30
IMAGES=30
LABELS=30
PLACEMENTS=139
LEAKAGE_GATE=ON
QA=PASS
```

Composición observada del piloto:

```
difficulty: {'basic': 10, 'medium': 10, 'hard': 10}      (extreme: 0)
density:    basic n=2 x5, basic n=3 x5,
            medium n=4 x5, medium n=5 x5,
            hard n=6 x4, hard n=7 x3, hard n=8 x3
```

Linaje observado en el manifiesto de 139 filas:

```
category distinct values: 6 (5 categorías de fixture + vacía)
metadata_status: {'ok': 136, 'missing': 3}
filas con category vacía: 3 -> todas con metadata_status='missing'
filas con generator_commit no vacío: 139/139
```

Rangos observados sobre los 139 placements:

```
scale:    0.5505 .. 1.0950
rotation: -34.582 .. +33.933
max occlusion basic:  0.0000   (límite 0.05)
max occlusion medium: 0.1365   (límite 0.15)
max occlusion hard:   0.2121   (límite 0.30)
label-count mismatches: []
```

Ninguna imagen generada se versiona en el repositorio: la salida vive fuera del
árbol de trabajo, en rutas privadas pasadas por CLI.

### 4.8 Revisión visual de geometría

Se dibujó un overlay de las cajas del manifiesto sobre la escena de mayor
oclusión del piloto (`SYN_0541`, hard, n=8, oclusión máxima 0.2121). Observado:
las cajas ciñen los objetos **rotados**, y el objeto parcialmente tapado
(z-order 3, `visible=16690`, `transformed=21184`) tiene su caja recortada a la
región visible, no al rectángulo transformado completo. (Overlay generado en la
revisión previa a esta corrección; la geometría no cambió en esta revisión.)

Esta revisión la hizo el propio autor y **no sustituye** la revisión visual por
un revisor distinto que exige el gate P2-G2.

## 5. QA automático

`validate_outputs()` falla (con `QAError`) si:

- el número de imágenes o labels no coincide con las escenas solicitadas;
- un label no tiene exactamente `planned_object_count` líneas;
- alguna coordenada YOLO cae fuera de `[0,1]`, o `w`/`h` <= 0;
- una fuente se repite dentro de una escena;
- aparece una fuente fuera de la allowlist train (fuga val/test);
- `visible_area` <= 0, o la oclusión supera el límite del nivel;
- falta el manifiesto, falta un hash, `metadata_status` o `generator_commit`
  vacíos, o el hash de imagen/label no coincide con el archivo en disco;
- una ruta del manifiesto no es relativa;
- se invoca sin `allowed_source_ids` (ahora `ValueError` explícito, no bypass).

## 6. Resultado de pruebas observado

```
$ python -m pytest tests/test_assign_synthetic_sources.py -q
33 passed in 0.46s
(exit code 0)

$ python -m pytest tests/test_make_synthetic_scenes.py -q
71 passed in 12.64s
(exit code 0)

$ python -m pytest -q
2 failed, 198 passed, 1 skipped in 15.32s
(exit code 1)

$ git diff --check
(sin salida)
(exit code 0)
```

**La suite completa del repositorio sigue en estado FAIL (código de salida 1)**
en este entorno. No se declara `FULL_TESTS=155/155 PASS` ni ninguna variante
agregada que oculte los 2 fallos: el resultado exacto es
`2 failed, 198 passed, 1 skipped`.

## 7. Fallos preexistentes (no introducidos por esta rama)

Los dos fallos de la suite completa son de `tests/test_train_evaluate_cli.py` y
existen en `origin/main` sin ninguna de estas modificaciones. Verificado en un
worktree limpio sobre `3b4b97d`:

```
$ python -m pytest -q          # worktree limpio en origin/main
2 failed, 94 passed, 1 skipped in 2.74s
(exit code 1)

FAILED tests/test_train_evaluate_cli.py::...::test_01_smoke_train_produce_artefactos_contractuales
FAILED tests/test_train_evaluate_cli.py::...::test_04_evaluacion_repetida_sobre_mismo_peso_es_identica
```

Causa raíz observada: `ModuleNotFoundError: No module named 'torch'` en
`src/train.py:110`. `test_04` falla en cascada porque `test_01` no produjo los
pesos. Es una carencia del entorno local (torch/ultralytics no instalados), no
una regresión de código; no se instaló ninguna dependencia para ocultar o evitar
este resultado (prohibido por las instrucciones de esta revisión).

Diferencia neta: 94 → 198 tests aprobados, es decir los 104 tests nuevos
(33 de P2-006 + 71 de P2-007). El estado agregado de la suite (`FAIL`, código 1)
es idéntico antes y después de esta rama: los mismos 2 tests preexistentes
fallan por la misma causa, ni uno más ni uno menos.

## 8. Estado y qué falta

| Ítem | Estado observado |
|---|---|
| P2-006 implementado y probado | Sí (33/33 tests) |
| P2-007 implementado y probado | Sí (71/71 tests) |
| Forma gobernante 655/3287/459 verificada | Sí, con cutouts de fixtures |
| Linaje de categoría/metadata_status propagado | Sí (P2-006 → assignments → manifiesto de escenas) |
| generator_commit registrado y obligatorio | Sí |
| Integridad de hash de cutout verificada | Sí (PASS con hash correcto, FAIL demostrado con hash alterado) |
| Gate anti-fuga obligatorio (sin bypass) | Sí |
| Integridad de rutas (absoluta/traversal) | Sí |
| Consistencia de linaje/difficulty/seed/n_products dentro de escena y entre escenas | Sí |
| Piloto de fixtures 30 escenas | Sí (10 basic / 10 medium / 10 hard) |
| Piloto **real** con cutouts de P2-005 | **NO EJECUTADO** |
| Corrida completa de 655 escenas reales | **NO EJECUTADA** (bloqueada por P2-005 y P2-008) |
| Revisión visual por revisor no autor | **PENDIENTE** |
| Gate P2-G2 | **NO CERRADO** |
| Suite completa del repositorio | **FAIL** (2 fallos preexistentes de entorno, ajenos a P2-006/P2-007) |

Secuencia pendiente: P2-005 cutouts READY/PASS → rehacer P2-006 con el
manifiesto real (incluida su columna de categoría real, cuando P2-003/004 la
entregue) → piloto REAL de 30 escenas (P2-008) → revisión visual por un
revisor distinto del autor → recién entonces la corrida gobernante de 655.

`P2-006_IMPLEMENTATION=READY_FOR_REVIEW`, `P2-006_GOVERNING_RUN=NOT_RUN`,
`P2-007_IMPLEMENTATION=READY_FOR_REVIEW`, `PILOT_REAL=NOT_RUN`,
`P2-G2=NOT_CLOSED`. Este PR depende de que P2-003/P2-004 (metadata/categoría) y
P2-005 (cutout library) avancen; no declara PASS gobernante de ningún tipo.
