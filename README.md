# Project AmarketBoundingBoxes

Proyecto final de **MCI-509 — Procesamiento de Imágenes y Visión Computacional** de la Universidad Católica Boliviana "San Pablo", Sede Santa Cruz.

## Objetivo

Pipeline único de dos etapas sobre el catálogo público de AMARKET:

1. **Localización (YOLO, monoclase).** Detector `0: product` — SKU, nombre y descripción son metadatos de procedencia, nunca clases YOLO.
2. **Identificación (SIFT, retrieval).** Sobre cada caja ya localizada, un segundo componente identifica el producto por comparación visual contra un catálogo de referencia (no por clasificación supervisada: el catálogo aporta ~1 muestra por SKU, insuficiente para eso).

La arquitectura de dos etapas responde a un replanteo docente comunicado durante el desarrollo (simular una caja de supermercado: localizar *y* identificar cada artículo) sin reabrir el contrato monoclase congelado de Fase 1. Ver `docs/governance/03_PHASE2/14_ADR-006_TWO_STAGE_DETECTION_IDENTIFICATION_SCOPE.md`.

```yaml
names:
  0: product
```

## Dataset

- **Real (Experimento A/B, base):** 655 imágenes AMARKET aceptadas, splits reproducibles `459/98/98` train/val/test, seed `42`, sin cruces de SKU, source asset ni duplicate group.
- **Sintético (Experimento B, aumentación):** 197 escenas multiproducto train-only (`SYN_0001`–`SYN_0197`, todas dificultad `basic`), de una meta contractual de 655 — la corrida completa se detuvo en `SYN_0198` por agotamiento del presupuesto de búsqueda estructurado, respetando el límite de oclusión en vez de violarlo. Train efectivo de Experimento B: 459 reales + 197 sintéticas = 656 imágenes. Validation/test permanecen 100% reales (98/98), sin sintético.
- **Catálogo de identidad:** 655 referencias (`catalog_identity.csv`), cutout de entrenamiento cuando existe o foto real en caso contrario; cobertura 655/655, 0 SKU duplicados.

Las imágenes, pesos, escenas sintéticas y el catálogo no se versionan en GitHub por tamaño; permanecen en Drive privado del proyecto (carpeta `PROJECT_AMARKETBOUNDINGBOXES`). Dataset real congelado:
https://drive.google.com/drive/folders/1o4U-ehe1_WbZpye-W5J44YLLEUnAhAS9

Los artefactos de Experimento B (`EXPERIMENT_B_REAL459_SYN197_SEED42/`: pesos B0/T1, `catalog_identity.csv`, `ground_truth_197.json`, evaluaciones) viven en la misma carpeta privada del proyecto; no se generó un enlace público independiente para ellos en esta entrega.

## Entorno

- **Experimento A (detector base, CPU):** Python 3.11.9, dependencias fijadas en `requirements.txt`.
- **Experimento B (GPU) + identificación (SIFT):** entorno `ComputerVision` (WSL2 Ubuntu), Python 3.12.13, PyTorch 2.13.0+cu126, Ultralytics 8.4.120, CUDA 12.6, NVIDIA GeForce RTX 4050 Laptop (6 GB). OpenCV 5.0.0 (`SIFT_create`, `BFMatcher`) para identificación, sin instalación adicional.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

## Modelo final — Experimento B / T1

Detector ganador: **T1** (Experimento B, `imgsz=512`, seleccionado sobre B0 por mayor `mAP@50-95` en validación: 0.991 vs 0.987).

Peso: `run_t1/weights/best.pt`
SHA-256: `6635a3efa75da83cd53544281243359a68038966eede4f962ba60d1fa2de910b`

Catálogo de identidad: `catalog_identity.csv`
SHA-256: `68b3c3b0a096fe39966320a050aa2e1135cefa7e90736a2ca9ef708122b44651`

Ambos en la carpeta privada `EXPERIMENT_B_REAL459_SYN197_SEED42/` del Drive del proyecto (ver arriba). Para reproducir localmente:

```text
outputs/demo_model_b/experiment_b_t1_best.pt
outputs/demo_model_b/catalog_identity.csv
outputs/demo_model_b/demo_scenes/   # carpeta de escenas de ejemplo
```

## Resultados finales

### Detección (test AMARKET real, 98 imágenes, una sola evaluación, sin tuning posterior)

| Métrica | Valor |
|---|---:|
| Precision | 0.985658 |
| Recall | 1.000000 |
| F1 | 0.992777 |
| mAP@0.5 | 0.994091 |
| mAP@0.5:0.95 | 0.971511 |

### Identificación de producto (evaluación end-to-end, 197 escenas sintéticas / 481 placements)

| Métrica | Valor |
|---|---:|
| Detector recall (IoU≥0.5) | 1.000000 |
| Detector precision (IoU≥0.5) | 0.997925 |
| **Identidad top-1** | **407/481 = 84.6 %** |
| **Identidad top-5** | **444/481 = 92.3 %** |
| **Exactitud end-to-end** (IoU ∧ SKU top-1) | **407/481 = 84.6 %** |
| Tasa UNKNOWN | 0.000000 |

**Advertencia de dominio cerrado:** las escenas sintéticas de evaluación derivan de los mismos cutouts que forman el catálogo de referencia. Esta cifra mide si el retrieval encuentra su propia fuente, no generalización a fotografías nuevas de una caja real. Detalle completo, 10 aciertos y 10 errores con hipótesis de causa, en `informe/main.pdf` (Apéndice A).

## Inferencia CPU + identificación

```powershell
.\.venv\Scripts\python.exe src\predict.py --model outputs\demo_model_b\experiment_b_t1_best.pt --input outputs\demo_model_b\demo_scenes --catalog outputs\demo_model_b\catalog_identity.csv --device cpu --output-dir outputs\predictions\demo_b --conf 0.25 --limit 5
```

Outputs: `predictions.json`, `predictions.csv` (una fila por producto: bbox, confianza YOLO, SKU, nombre, similitud de identidad, top-5), `timing_summary.json` y `annotated/` (boxes con nombre + confianza).

`--catalog` es opcional: sin él, `src/predict.py` se comporta exactamente igual que antes (solo detección, sin cv2 requerido).

## Notebook obligatorio

Abrir `notebooks/inferencia_cpu.ipynb` y ejecutar **Restart Kernel / Run All**. Rutas configurables por variable de entorno (`AMARKET_MODEL_PATH`, `AMARKET_CATALOG_PATH`, `AMARKET_DEMO_INPUT`, `AMARKET_GROUND_TRUTH`), sin rutas absolutas embebidas en el archivo.

El notebook verifica el SHA-256 del peso T1, fuerza `device="cpu"`, detecta e identifica productos en escenas multiproducto de ejemplo, y muestra boxes + nombre/SKU + confianza + similitud, con tabla de resultados y marca de acierto/error contra el ground truth de composición (por IoU, no por índice de detección).

## Evaluación reproducible

```powershell
.\.venv\Scripts\python.exe src\evaluate.py --model outputs\demo_model_b\experiment_b_t1_best.pt --data <dataset.yaml> --split test --allow-test --output-dir outputs\evaluation\experiment_b --conf 0.25 --iou-umbral 0.5 --device cpu
```

## Entrenamiento reproducible

```powershell
.\.venv\Scripts\python.exe src\train.py --config configs\experiment_b_gpu_t1.yaml --data <dataset.yaml> --output-dir outputs\runs\experiment_b_t1 --seed 42
```

`configs/experiment_b_gpu_{b0,t1,t2}.yaml` son copias de `configs/baseline.yaml` con `device: 0` (GPU) y, respectivamente, `imgsz=416`, `imgsz=512` (ganador) y `batch=16` (T2 diferido — no ejecutado en esta entrega). `baseline.yaml` no fue modificado.

El flujo contractual es train → selección con val (`mAP@50-95`) → congelación de peso/config → test una sola vez.

## Pipeline

`src/scraper_extraction.py` → `src/data/make_boxes.py` → `src/data/make_splits.py` → (`src/data/assign_synthetic_sources.py` → `src/data/make_synthetic_scenes.py`, Experimento B) → `src/train.py` → `src/evaluate.py` → `src/predict.py` (+ `src/recognition.py` para identificación) → `notebooks/inferencia_cpu.ipynb`

## Limitaciones

- Dataset sintético congelado en 197/655 escenas (todas dificultad `basic`); el detector no vio densidades `medium/hard/extreme` en entrenamiento.
- Identificación evaluada en dominio cerrado (ver advertencia arriba); no es prueba de generalización.
- SIFT confunde sistemáticamente (a) variantes de una misma línea de producto y (b) envases lisos de baja textura — ver `informe/main.pdf` §5–6.
- Dataset de origen único (AMARKET); diversidad visual acotada por ese catálogo.

## Licencia

Sin licencia de código abierto declarada. Uso académico exclusivo (MCI-509, UCB). Redistribución de imágenes/datos del catálogo AMARKET prohibida (decisión LD-003 del proyecto).

## Equipo

- Monserrat Barba: adquisición y validación.
- Andrés Poiche: bounding boxes, dataset y splits.
- Pablo Linares: entrenamiento y evaluación.
- Guillermo Carvajal Vaca: coordinación, integración, reproducibilidad, Experimento B, identificación, inferencia CPU, informe y defensa.

Los artefactos se integran mediante Pull Request con revisión independiente.
