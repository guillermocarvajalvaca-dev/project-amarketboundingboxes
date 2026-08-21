# Estado G5 — Evaluación final sobre `test` (Modelo gobernante A)

Evidencia de ejecución de G5 (Evaluation & CPU Inference), tras solicitud expresa
del coordinador (@guillermocarvajalvaca-dev) de correr el script de evaluación
final sobre el modelo gobernante seleccionado en el cierre de G4: Experimento A
(`EV-G4-001`, AMARKET-only). Esta es la primera vez que el split `test` se
consulta en todo el proyecto.

## Autorización de referencia

- Script de evaluación final entregado y solicitado directamente por
  @guillermocarvajalvaca-dev (mensaje al owner, 2026-08-21), con guardas
  explícitas (`STOP=`) que fijan el `main` esperado, el peso gobernante por
  SHA-256 y el tamaño del split `test`.
- El script exige `EXPECTED_MAIN=0c705c9c2b23aa1d1b666894c3f6ae3c710f2dca` y
  `EXPECTED_WEIGHT_SHA=9149dfef3093ca12a80fbb85b860822ae52d6ca5d8e2f1a6224211f92acd6712`
  (peso de `EV-G4-001`) — ambos verificados exactos antes de tocar `test`.

## Entorno gobernante

Idéntico al usado para entrenar el modelo gobernante (Experimento A):

- Python 3.11.9 exacto (`.venv-g4-3119`, mismo venv reutilizado).
- Ultralytics 8.4.120, PyTorch 2.13.0+cpu.
- Dispositivo: **CPU** (Apple M5, sin MPS, conforme GOV-002).
- Commit base: `0c705c9c2b23aa1d1b666894c3f6ae3c710f2dca` (`origin/main`,
  fast-forward limpio antes de crear la rama `chore/pablo/G5-final-evaluation`).

## Peso gobernante evaluado

- `outputs/runs/g4_amarket_only_20260821_100653/weights/best.pt`
  (Experimento A, `EV-G4-001`).
- `BEST_WEIGHT_SHA256`: `9149dfef3093ca12a80fbb85b860822ae52d6ca5d8e2f1a6224211f92acd6712`
  — coincide exacto con el registrado al cerrar el entrenamiento.
- Experimento B (`EV-G4-002`, AMARKET+RPC) queda fuera de esta evaluación:
  es evidencia no gobernante desde el cierre de G4.

## Dataset — `test` canónico

- `data/manifests/splits.csv` (canónico en `main`), resuelto vía
  `configs/dataset.yaml`.
- `test`: 98 imágenes / 98 labels, 0 missing, preflight `TEST_CANONICAL_PREFLIGHT=PASS`.
- `TEST_USED_FOR_TUNING=NO`: el peso evaluado fue congelado en G4 sin haber
  consultado `test` en ningún momento previo; esta es la primera y única
  consulta de `test`, y ocurre después del cierre de G4, no antes.

## Ejecución

```text
python src/evaluate.py --model outputs/runs/g4_amarket_only_20260821_100653/weights/best.pt \
    --data configs/dataset.yaml --split test \
    --output-dir outputs/evaluation/g5_amarket_test_A_run1_20260821_124539 \
    --conf 0.25 --iou-umbral 0.5 --device cpu --allow-test

python src/evaluate.py --model outputs/runs/g4_amarket_only_20260821_100653/weights/best.pt \
    --data configs/dataset.yaml --split test \
    --output-dir outputs/evaluation/g5_amarket_test_A_run2_20260821_124539 \
    --conf 0.25 --iou-umbral 0.5 --device cpu --allow-test
```

- Exit code: 0 en ambas corridas.
- Dos corridas idénticas (mismo peso, mismo split, mismos hiperparámetros de
  evaluación) exigidas por reproducibilidad contractual (Guía §2, G4/G5).

## Resultado — métricas sobre `test` (98 imágenes, 98 ground truths)

| Métrica | Run 1 | Run 2 |
|---|---|---|
| Precision | 1.000000 | 1.000000 |
| Recall | 1.000000 | 1.000000 |
| F1 | 1.000000 | 1.000000 |
| mAP50 | 0.995000 | 0.995000 |
| mAP75 | 0.995000 | 0.995000 |
| mAP50-95 | 0.992875 | 0.992875 |

`G5_REPEAT_EVALUATION=PASS`: las dos corridas producen métricas idénticas
(`map50`, `map50_95`, `map75`, `precision`, `recall`, `f1`), y ambos
`weight_manifest.json` confirman el mismo SHA-256 del peso gobernante. Esto
satisface el requisito contractual de reproducibilidad (misma evaluación
repetida coincide), no determinismo byte a byte de artefactos auxiliares
(`predictions.json`, `error_examples.csv`) entre corridas en hardware
distinto — aclarado explícitamente en `metrics.json` (`nota` `determinismo`).

Artefactos generados en cada directorio de run: `metrics.json`,
`weight_manifest.json`, `predictions/predictions.json`, `error_examples.csv`,
`error_categories_README.txt`, curvas (`BoxPR_curve.png`, `BoxF1_curve.png`,
`BoxP_curve.png`, `BoxR_curve.png`, `confusion_matrix.png`,
`confusion_matrix_normalized.png`), muestras `val_batch*_labels.jpg` /
`val_batch*_pred.jpg`. No versionados (`outputs/*` en `.gitignore`);
reproducibles con los comandos de arriba sobre el mismo peso y split
congelados.

## Análisis de error — 15 ejemplos muestreados (Run 1)

`error_examples.csv` categoriza automáticamente cada instancia como
`correcto` (IoU ≥ 0.5 y misma clase), `omision` (ground truth sin predicción
que la cubra) o `falso_positivo` (predicción sin ground truth que la cubra),
según `error_categories_README.txt`.

- Ejemplos categorizados: 15 de 15 = **`correcto`**.
- `omision` = 0, `falso_positivo` = 0.

### Brecha frente a la rúbrica (Guía §1; `RUBRIC_TRACEABILITY_AND_QUALITY_GATES.md`, G5/G6)

La rúbrica exige explícitamente **10–15 aciertos y 10–15 errores**. Con
P=R=1.0 sobre las 98 instancias de `test` a `conf=0.25`/`iou=0.5`, el modelo
gobernante A no comete ningún error clasificable en este split bajo estos
umbrales — no hay `omision` ni `falso_positivo` que muestrear. No se fuerzan
ni se inventan errores para completar la cuota.

Esto se registra como una **brecha real y honesta**, no como incumplimiento
oculto: la evaluación en sí (`G5_EVALUATION=PASS`) es correcta y
reproducible; lo que falta es la sección de 10–15 incorrectos que exige la
rúbrica para G5/G6. Queda pendiente de decisión del coordinador cómo
completarla — opciones no ejecutadas aquí, solo señaladas: (a) reducir el
umbral de confianza para exponer falsos positivos marginales y documentar
que son inducidos por el umbral, no errores naturales del modelo en
`conf=0.25`; (b) usar ejemplos de `val` (no gobernantes para el score de
`test`) para ilustrar categorías de error; (c) aceptar explícitamente en el
informe (G6) que el modelo gobernante no produjo errores naturales sobre
este `test` de 98 imágenes y documentar el resultado como tal, con la
limitación de tamaño de muestra que eso implica.

## Alcance y prohibiciones respetadas

- `test` se consultó por primera y única vez en este gate, sobre el peso ya
  congelado y seleccionado como gobernante en G4 — no hubo tuning posterior
  a esta consulta (`NO_FURTHER_TUNING=TRUE`).
- No se modificó `configs/dataset.yaml`, `configs/baseline.yaml` ni
  `requirements.txt`.
- No se usó Apple MPS para la ejecución gobernante.
- Sin datos/pesos grandes versionados en el repo.
- Rama nueva `chore/pablo/G5-final-evaluation`, creada desde `main`
  sincronizado por fast-forward (`0c705c9`), tal como exigía el script.

## Estado

`G5_EVALUATION=PASS` para métricas, reproducibilidad e inferencia CPU sobre
el peso gobernante A. `G5_ERROR_ANALYSIS_RUBRIC_10_15=GAP` — ejecutado y
documentado (15 aciertos, 0 errores naturales), pendiente de decisión del
coordinador sobre cómo cerrar el requisito de 10–15 incorrectos antes de dar
G5 por cerrado formalmente (`NEXT=GUILLERMO_REVIEW_AND_DECIDE_ERROR_QUOTA`).
