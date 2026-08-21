# Project AmarketBoundingBoxes

Proyecto final de **MCI-509 — Procesamiento de Imágenes y Visión Computacional** de la Universidad Católica Boliviana "San Pablo", Sede Santa Cruz.

## Objetivo

Construir un dataset propio de productos públicos de AMARKET, generar bounding boxes YOLO y entrenar un detector monoclase:

```yaml
names:
  0: product
```

SKU y descripción son metadatos de procedencia, no clases.

## Estado

G0–G5: **PASS**. G6: **en cierre**.

Dataset canónico AMARKET: 655 imágenes aceptadas, con splits reproducibles `459/98/98` para train/val/test, seed `42`, sin cruces de SKU, source asset ni duplicate group.

Las imágenes y los pesos no se versionan en GitHub. El dataset congelado permanece en Drive privado:
https://drive.google.com/drive/folders/1o4U-ehe1_WbZpye-W5J44YLLEUnAhAS9

La ubicación local esperada coincide con `configs/dataset.yaml`:

```text
data/processed/amarket_yolo/
  images/train
  images/val
  images/test
  labels/train
  labels/val
  labels/test
```

## Entorno

Versión gobernante: Python 3.11.9. Las dependencias directas están fijadas en `requirements.txt`.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
```

## Modelo final

Modelo gobernante: **Experimento A — AMARKET-only, YOLO11n**.

Peso:
`amarket_yolo11n_g4_A_best.pt`

SHA-256:
`9149dfef3093ca12a80fbb85b860822ae52d6ca5d8e2f1a6224211f92acd6712`

Drive privado:
https://drive.google.com/file/d/1-laF__DIdTW8Geq8Xc57ni6NdMsCvV52/view?usp=drivesdk

Guardar el peso localmente en:

```text
outputs/demo_model/amarket_yolo11n_g4_A_best.pt
```

## Resultados finales sobre test AMARKET

| Métrica | Valor |
|---|---:|
| Precision | 1.000000 |
| Recall | 1.000000 |
| F1 | 1.000000 |
| mAP@0.5 | 0.995000 |
| mAP@0.75 | 0.995000 |
| mAP@0.5:0.95 | 0.992875 |

El test congelado contiene 98 imágenes y 98 ground truths. Dos evaluaciones del mismo peso produjeron métricas idénticas. No hubo tuning posterior sobre test.

El protocolo produjo 15 casos correctos seleccionados y 0 errores naturales a `conf=0.25` e `IoU=0.5`; no se modificaron umbrales para fabricar errores.

## Inferencia CPU

```powershell
.\.venv\Scripts\python.exe src\predict.py --model outputs\demo_model\amarket_yolo11n_g4_A_best.pt --input data\processed\amarket_yolo\images\test --device cpu --output-dir outputs\predictions\demo --conf 0.25 --limit 5
```

Outputs: `predictions.json`, `timing_summary.json` y `annotated/`.

## Notebook obligatorio

Abrir `notebooks/inferencia_cpu.ipynb` y ejecutar **Restart Kernel / Run All**.

El notebook verifica el SHA-256, carga explícitamente con `torch.load(..., map_location="cpu")`, fuerza `device="cpu"`, procesa cinco imágenes determinísticas y muestra las detecciones dentro del notebook.

## Evaluación reproducible

```powershell
.\.venv\Scripts\python.exe src\evaluate.py --model outputs\demo_model\amarket_yolo11n_g4_A_best.pt --data configs\dataset.yaml --split test --output-dir outputs\evaluation\reproduction --conf 0.25 --iou-umbral 0.5 --device cpu --allow-test
```

## Entrenamiento reproducible

```powershell
.\.venv\Scripts\python.exe src\train.py --config configs\baseline.yaml --data configs\dataset.yaml --output-dir outputs\runs\reproduction --seed 42
```

El flujo contractual es train → selección con val → congelación de peso/config → test.

## Pipeline

`src/scraper_extraction.py` → `src/data/make_boxes.py` → `src/data/make_splits.py` → `src/train.py` → `src/evaluate.py` → `src/predict.py` → `notebooks/inferencia_cpu.ipynb`

`src/common/reproducibility.py` concentra semillas, fingerprint canónico de configuración y SHA-256 de artefactos.

## Equipo

- Monserrat Barba: adquisición y validación.
- Andrés Poiche: bounding boxes, dataset y splits.
- Pablo Linares: entrenamiento y evaluación.
- Guillermo Carvajal Vaca: coordinación, integración, reproducibilidad, inferencia CPU, informe y defensa.

Los artefactos se integran mediante Pull Request con revisión independiente.
