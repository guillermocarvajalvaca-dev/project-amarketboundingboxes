# P2-008 — Piloto REAL de 30 escenas sintéticas (Fase 2)

Ejecutor: guillermocarvajalvaca-dev (GitHub login verificado vía `gh api user --jq .login`)
Rama: `feat/guillermo/P2-008-real-pilot`
BASE_HEAD: `6557ea775942c0b9dc454376613eab7322304f90` (verificado: `git rev-parse HEAD`
antes del commit de código coincidía exactamente)
CODE_COMMIT (compositor P2-007 fix): `4fdc17d6915495f81d71874cbdf58fd54617ecc3`
Intérprete: `C:\Users\guill\AppData\Local\Programs\Python\Python311\python.exe`
(Python 3.11.9, MSC v.1930 64 bit) — el mismo para todas las corridas.

Documentos gobernantes aplicados (NO modificados en esta rama,
`git diff -- docs/governance/03_PHASE2` produce 0 líneas):
- `01_CONTRACT_SDD_PHASE2_v2_0_0_FROZEN.md`
- `06_SYNTHETIC_DATA_GENERATION_CONTRACT_v1_0_0.md`
- `08_QA_GATES_PHASE2_v1_0_0.md`
- `09_TASK_POOL_PHASE2.csv`, `10_SCENE_PLAN_655.csv`

## Alcance del fix de código (CODE_COMMIT)

`src/data/make_synthetic_scenes.py` + `tests/test_make_synthetic_scenes.py`
(2 files changed, 718 insertions(+), 53 deletions(-)):

- Validación incremental de oclusión por objeto (condición necesaria; el
  chequeo final `enforce_occlusion_limits` queda como autoridad).
- Fallback estructurado determinista + backtracking acotado con presupuesto
  total `STRUCTURED_SEARCH_BUDGET=4000`; orden de colocación/z_order por
  tamaño de cutout descendente (placement_index se preserva por fila).
- Rendimiento: fase aleatoria materializada UNA vez por objeto e intento
  (`_draw_random_candidates`, re-iterada en cada recreación por backtracking)
  y chequeo de oclusión optimizado por ROI (pre-filtro de fg-bbox, fast path
  sólida×sólida por aritmética de rectángulos, `count_nonzero` solo sobre el
  ROI solapado) — equivalencia exacta con el brute-force cubierta por test.
- Constantes contractuales intactas: `MAX_SCENE_ATTEMPTS=64`,
  `MAX_PLACEMENT_SAMPLES=64`, `STRUCTURED_SEARCH_BUDGET=4000`; canvas
  1280×1280; escalas/rotaciones/oclusión/conteos sin cambios.
- 5 tests de regresión nuevos (76 total en la suite P2-007):
  `test_roi_overlap_matches_bruteforce`,
  `test_random_candidates_cached_across_backtracking`,
  `test_structured_backtracking_solves_large_basic_scene`,
  `test_structured_backtracking_solves_dense_medium_and_hard`,
  `test_structured_fallback_is_byte_deterministic`.
- `test_escena_imposible_falla_sin_reducir_objetos`: fixture 1100×1100
  (imposibilidad matemática ≈20% ≫ 5%) intacto; `monkeypatch` de
  `MAX_SCENE_ATTEMPTS=1` ÚNICAMENTE dentro de ese test (el valor productivo
  permanece en 64).

## Pruebas

| Comando | Resultado literal | Exit |
|---|---|---|
| `python -m pytest tests/test_make_synthetic_scenes.py -q` | 76 passed in 68.08s | 0 |
| `python -m pytest tests/test_assign_synthetic_sources.py -q` | 33 passed in 0.57s | 0 |
| `python -m pytest tests -q` | **2 failed, 259 passed, 1 skipped in 81.94s** | 1 |

La suite completa NO se declara PASS. Los 2 fallos
(`test_train_evaluate_cli.py::TestSmokeTrainYEvaluate::test_01_smoke_train_produce_artefactos_contractuales`
y `::test_04_evaluacion_repetida_sobre_mismo_peso_es_identica`) son por
`ModuleNotFoundError: No module named 'torch'` (entorno de fase de datos sin
torch; test_04 es cascada: `best.pt` nunca se produjo). No comparten ruta de
código con el diff de P2-008.

## Reproducción en BASE_HEAD (evidence-first)

Worktree desechable detached en
`%TEMP%/P2_008_BASE_REPRO_764` sobre `6557ea775942c0b9dc454376613eab7322304f90`,
mismo intérprete Python, mismos node-ids:

```
python -m pytest "tests/test_train_evaluate_cli.py::TestSmokeTrainYEvaluate::test_01_smoke_train_produce_artefactos_contractuales" "tests/test_train_evaluate_cli.py::TestSmokeTrainYEvaluate::test_04_evaluacion_repetida_sobre_mismo_peso_es_identica" -q
```

Resultado: **2 failed in 0.68s, exit code 1** — mismas causas exactas
(torch ausente; best.pt inexistente por cascada). Worktree base verificado
limpio y eliminado (`git worktree remove`).

- BASE_REPRODUCTION=IDENTICAL
- ENVIRONMENTAL_LIMITATION=torch not installed
- NO_NEW_REGRESSIONS=YES

## Inputs reales y procedencia

- Plan congelado: `docs/governance/03_PHASE2/10_SCENE_PLAN_655.csv`.
- Manifiesto de cutouts: `data/manifests/p2_cutout_library.csv`.
- Cutouts físicos: `P2_TRAIN_CUTOUTS_459/cutouts/*.png` — **459/459
  verificados** independientemente (0 faltantes, 0 discrepancias SHA256
  contra `cutout_sha256` declarado; re-verificados en la corrida de evidencia).
- Asignación P2-006 regenerada DESDE CERO por corrida con el CLI gobernante:

```
python -m src.data.assign_synthetic_sources \
  --scene-plan docs/governance/03_PHASE2/10_SCENE_PLAN_655.csv \
  --cutout-manifest data/manifests/p2_cutout_library.csv \
  --output <RUN>/scene_source_assignments.csv
```

Salida idéntica en ambas corridas: MODE=GOVERNING, SCENES=655, SOURCES=459,
ROWS=3287, USAGE_HISTOGRAM=385x7+74x8, exit 0.
SHA256 assignments (A == B):
`223dc7357e2a6f4cfcd762bda7435423f382412724b0c417ca8de5f0a09cc8a7`

## Piloto oficial (A) y replay determinista (B)

Directorios externos nuevos (nada sobrescrito), dentro de
`PROJECT_AMARKETBOUNDINGBOXES`:

- A: `P2_SYNTHETIC_PILOT_30_OFFICIAL_4fdc17d_A/`
- B: `P2_SYNTHETIC_PILOT_30_OFFICIAL_4fdc17d_B/`

Comando de composición por corrida (generator_commit = CODE_COMMIT completo,
ya NO el 2ad7d58 de las corridas diagnósticas):

```
python -m src.data.make_synthetic_scenes \
  --assignments <RUN>/scene_source_assignments.csv \
  --cutout-root "G:/My Drive/Maestria Ciencia de Datos/VISION_COMP/RPC_PROJECT/PROJECT_AMARKETBOUNDINGBOXES/P2_TRAIN_CUTOUTS_459" \
  --output-root <RUN>/synthetic \
  --manifest <RUN>/scene_manifest.csv \
  --cutout-manifest data/manifests/p2_cutout_library.csv \
  --generator-commit 4fdc17d6915495f81d71874cbdf58fd54617ecc3 \
  --pilot
```

A: exit 0, 3m11s. B: exit 0, 3m19s. Ambas imprimen MODE=PILOT, SCENES=30,
IMAGES=30, LABELS=30, PLACEMENTS=139, LEAKAGE_GATE=ON, QA=PASS,
GENERATOR_COMMIT=4fdc17d6915495f81d71874cbdf58fd54617ecc3.

## Gates verificados (ambas corridas, verificación independiente del CLI)

- 30/30 escenas; basic=10, medium=10, hard=10.
- Buckets exactos del contrato: basic n2=5, n3=5; medium n4=5, n5=5;
  hard n6=4, n7=3, n8=3.
- planned_n_products == actual_object_count == filas en 30/30 (nunca se
  reduce el conteo).
- visible_area > 0 en las 139 filas.
- 0 violaciones de oclusión (≤0.05 basic / ≤0.15 medium / ≤0.30 hard).
  Máximos observados: basic SYN_0004 0.0476; medium SYN_0222 0.1477;
  hard SYN_0492 0.2998.
- Train-only verificado contra allowlist del manifiesto (0 fuentes no
  train/accepted); LEAKAGE_GATE=ON.
- generator_commit único en las 139 filas == CODE_COMMIT exacto.
- Hashes de los 459 cutouts verificados (gate de entrada + re-verificación
  independiente).

## Determinismo (A vs B)

- assignments: byte-idénticos.
- scene_manifest.csv: byte-idénticos. SHA256 (A == B):
  `873b53b9c55cd0e376f54bb418113b0dac562607a78f6255ef0eb0e42290c0c7`
- 30/30 PNG byte-idénticos; 30/30 labels byte-idénticos (comparados uno a
  uno por SHA256; 0 diferencias).
- SHA256 concatenado de imágenes (A == B):
  `9fe6aebd4cea1716405bcbcfb0f569c00a162133429793e470ca7bec14b616f3`
- SHA256 concatenado de labels (A == B):
  `e4b4c3c5acb0d0f28dadd3a4acb466eedc54bf54d9bcdfbed9fb296a46da2864`

DETERMINISM=PASS. Ningún campo no determinista fue excluido: el manifiesto
completo (incluidas rutas relativas y hashes de salida) es idéntico byte a
byte entre A y B.

## Overlays QA (fuera del repositorio)

`P2_SYNTHETIC_PILOT_30_OFFICIAL_4fdc17d_A/overlays/SYN_*.png` — 30 overlays
(caja visible por objeto, color por dificultad, oclusión por caja). Ejemplos
exigidos: Basic `SYN_0001`, Medium `SYN_0221`, Hard `SYN_0441`; escenas de
mayor oclusión observada: `SYN_0004` (basic 0.0476), `SYN_0222` (medium
0.1477), `SYN_0492`/`SYN_0443`/`SYN_0543` (hard 0.2998/0.2989/0.2979).

## Estado declarado

- FULL_655_RUN=NOT_RUN (prohibido en esta etapa; solo plan 655 usado como
  input de asignación, composición limitada a `--pilot`).
- P2_G2=NOT_CLOSED — pendiente de revisión visual independiente de los
  overlays por un revisor que no sea el ejecutor.
- SELF_APPROVAL=NO; MERGE=NO. PR abierto solicitando revisión independiente.
