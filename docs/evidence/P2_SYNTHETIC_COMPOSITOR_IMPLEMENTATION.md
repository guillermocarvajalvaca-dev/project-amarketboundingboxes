# Evidencia — P2-006 / P2-007: asignación determinista y compositor sintético

- Evidence ID: `EV-P2-006-007-001`
- Gate relacionado: P2-G2 (piloto sintético) — **no cerrado por este documento**
- Tareas: `P2-006` (deterministic usage assignment), `P2-007` (deterministic synthetic compositor)
- Ejecutor: Jose Guilermo Carvajal Vaca (`@guillermocarvajalvaca-dev`)
- Rama: `feat/guillermo/P2-006-007-synthetic-compositor`
- `main` gobernante: `3b4b97d1bd19b2e5625d6432d7b6e57c0b9b4522`
- Fecha de ejecución: 2026-08-22

Este documento registra **solo evidencia observada** de implementación y pruebas.
No declara PASS del piloto gobernante: ese piloto exige los cutouts reales de
P2-005 y todavía no se ejecutó.

## 1. Alcance entregado

| Archivo | Tarea | Contenido |
|---|---|---|
| `src/data/assign_synthetic_sources.py` | P2-006 | Asignación determinista de fuentes train a los 3287 placements |
| `src/data/make_synthetic_scenes.py` | P2-007 | Compositor de escenas, geometría de oclusión, QA automático, modo piloto |
| `tests/test_assign_synthetic_sources.py` | P2-006 | 19 tests |
| `tests/test_make_synthetic_scenes.py` | P2-007 | 42 tests |

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

### 3.2 Corrida observada contra el plan congelado

Ejecutada con el plan real `docs/governance/03_PHASE2/10_SCENE_PLAN_655.csv` y
un inventario de cutouts **de fixtures** (459 fuentes sintéticas generadas
programáticamente), porque la librería real de P2-005 aún no está mergeada:

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
```

Reejecución byte a byte: dos corridas consecutivas produjeron el mismo
`sha256` de archivo (`c093058574387b2e...`, verificado con `sha256sum` sobre
salidas independientes).

Este ejercicio valida la **forma** gobernante (655/3287/459 y el reparto
74×8+385×7). La corrida gobernante definitiva debe repetirse con el manifiesto
real de P2-005.

### 3.3 Gate anti-fuga

Una fila `status=accepted` con `split` distinto de `train` no se descarta en
silencio: lanza `SplitLeakageError` y aborta la corrida. Las filas
`status != accepted` sí se descartan, contabilizadas en `SKIPPED_NOT_ACCEPTED`.

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

### 4.3 Reintentos acotados y conteo de objetos

`MAX_SCENE_ATTEMPTS = 64`, `MAX_PLACEMENT_SAMPLES = 64`. Si una escena no puede
cumplir el contrato, se lanza `SceneGenerationError`: **nunca** se reduce
`n_products` en silencio. Cubierto por
`test_escena_imposible_falla_sin_reducir_objetos`, que fuerza el caso con
cutouts de 900×900 en dificultad `basic`.

### 4.4 Piloto de fixtures observado

El piloto **real** (P2-008) no se ejecutó: requiere los cutouts reales de P2-005.
Lo que sí se ejecutó es un piloto de fixtures sintéticos, con el plan de escenas
real y cutouts generados programáticamente:

```
$ python -m src.data.make_synthetic_scenes \
    --assignments <ruta privada>/scene_source_assignments.csv \
    --cutout-root <ruta privada>/cutouts_root \
    --output-root <ruta privada>/synthetic \
    --manifest <ruta privada>/scene_manifest.csv \
    --cutout-manifest <ruta privada>/fixture_cutout_library.csv \
    --pilot --background-rgb "255,255,255"

GENERATOR_VERSION=p2-synthetic-compositor/1.0.0
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

Rangos observados sobre los 139 placements:

```
scale:    0.5505 .. 1.0950
rotation: -34.582 .. +33.933
max occlusion basic:  0.0000   (límite 0.05)
max occlusion medium: 0.1365   (límite 0.15)
max occlusion hard:   0.2121   (límite 0.30)
label-count mismatches: []
```

Reejecución del piloto en otro directorio de salida: los 139
`output_image_sha256`, los 139 `output_label_sha256` y toda la geometría
(`x`, `y`, `scale`, `rotation_deg`) resultaron idénticos.

Ninguna imagen generada se versiona en el repositorio: la salida vive fuera del
árbol de trabajo, en rutas privadas pasadas por CLI.

### 4.5 Revisión visual de geometría

Se dibujó un overlay de las cajas del manifiesto sobre la escena de mayor
oclusión del piloto (`SYN_0541`, hard, n=8, oclusión máxima 0.2121). Observado:
las cajas ciñen los objetos **rotados**, y el objeto parcialmente tapado
(z-order 3, `visible=16690`, `transformed=21184`) tiene su caja recortada a la
región visible, no al rectángulo transformado completo.

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
- falta el manifiesto, falta un hash, o el hash no coincide con el archivo en disco;
- una ruta del manifiesto no es relativa.

El gate anti-fuga se activa pasando `--cutout-manifest` (salida `LEAKAGE_GATE=ON`).

## 6. Resultado de pruebas observado

```
$ python -m pytest tests/test_assign_synthetic_sources.py -q
19 passed in 0.44s

$ python -m pytest tests/test_make_synthetic_scenes.py -q
42 passed in 11.31s

$ python -m pytest -q
2 failed, 155 passed, 1 skipped in 16.03s
```

## 7. Fallos preexistentes (no introducidos por esta rama)

Los dos fallos de la suite completa son de `tests/test_train_evaluate_cli.py` y
existen en `origin/main` sin ninguna de estas modificaciones. Verificado en un
worktree limpio sobre `3b4b97d`:

```
$ python -m pytest -q          # worktree limpio en origin/main
2 failed, 94 passed, 1 skipped in 2.74s

FAILED tests/test_train_evaluate_cli.py::...::test_01_smoke_train_produce_artefactos_contractuales
FAILED tests/test_train_evaluate_cli.py::...::test_04_evaluacion_repetida_sobre_mismo_peso_es_identica
```

Causa raíz observada: `ModuleNotFoundError: No module named 'torch'` en
`src/train.py:110`. `test_04` falla en cascada porque `test_01` no produjo los
pesos. Es una carencia del entorno local (torch/ultralytics no instalados), no
una regresión de código.

Diferencia neta: 94 → 155 tests aprobados, es decir los 61 tests nuevos
(19 de P2-006 + 42 de P2-007).

## 8. Estado y qué falta

| Ítem | Estado observado |
|---|---|
| P2-006 implementado y probado | Sí |
| P2-007 implementado y probado | Sí |
| Forma gobernante 655/3287/459 verificada | Sí, con cutouts de fixtures |
| Piloto de fixtures 30 escenas | Sí (10 basic / 10 medium / 10 hard) |
| Piloto **real** con cutouts de P2-005 | **NO EJECUTADO** |
| Corrida completa de 655 escenas reales | **NO EJECUTADA** (bloqueada por P2-005 y P2-008) |
| Revisión visual por revisor no autor | **PENDIENTE** |
| Gate P2-G2 | **NO CERRADO** |

Secuencia pendiente: P2-005 cutouts READY/PASS → rehacer P2-006 con el
manifiesto real → piloto REAL de 30 escenas (P2-008) → revisión visual por un
revisor distinto del autor → recién entonces la corrida gobernante de 655.
