# Contrato de CLI, outputs y evaluación v1.0.0 — FROZEN

## 1. Convenciones

Todos los CLIs funcionan desde la raíz, implementan `--help`, aceptan rutas
explícitas, fallan con código no cero, registran config/entorno/commit y no
sobrescriben outputs silenciosamente. Ninguna ruta obligatoria depende de Jupyter.

## 2. Interfaces

### Monserrat — adquisición

```text
python src/scraper_extraction.py \
  --config configs/data_sources.yaml \
  --output-dir data/raw/amarket \
  --manifest data/manifests/source_assets.csv \
  --limit 3
```

```text
python src/data/validate_downloads.py \
  --manifest data/manifests/source_assets.csv \
  --output outputs/data_quality_report.json
```

### Andrés — cajas y splits

```text
python src/data/make_boxes.py \
  --config configs/dataset.yaml \
  --manifest data/manifests/source_assets.csv \
  --images-dir data/raw/amarket \
  --labels-dir data/labels \
  --audit outputs/box_audit.csv \
  --visualization-dir outputs/box_qa
```

```text
python src/data/make_splits.py \
  --manifest data/manifests/source_assets.csv \
  --box-audit outputs/box_audit.csv \
  --output data/manifests/splits.csv \
  --seed SEED
```

### Pablo — entrenamiento y evaluación

```text
python src/train.py \
  --config configs/baseline.yaml \
  --data configs/dataset.yaml \
  --output-dir outputs/runs/baseline \
  --seed SEED
```

```text
python src/evaluate.py \
  --model outputs/runs/baseline/best.pt \
  --data configs/dataset.yaml \
  --split test \
  --output-dir outputs/evaluation/baseline
```

### Guillermo — inferencia

```text
python src/predict.py \
  --model outputs/runs/baseline/best.pt \
  --input data/sample \
  --device cpu \
  --output-dir outputs/predictions
```

## 3. Outputs mínimos

- Train: pesos, `resolved_config.yaml`, `environment.json`, curvas y `train_log.csv`.
- Evaluate: `metrics.json`, predicciones, manifest de peso y ejemplos de error.
- Predict: visualizaciones, JSON de detecciones y tiempos.
- Notebook CPU: mismo peso, dispositivo CPU explícito y muestra reproducible.

## 4. Protocolo

- Métricas: `mAP@0.5`, `mAP@0.5:0.95`, precision, recall y F1 con umbrales
  declarados.
- No hay métricas por SKU porque SKU no es clase; sí puede haber cortes diagnósticos
  por tamaño, fondo o producto sin interpretarlos como clases.
- Entrenar con train, seleccionar con val, congelar peso/config y evaluar test una vez.
- “Accuracy” aislada queda prohibida sin unidad y fórmula.
- RPC/cAcc no se compara numéricamente con el resultado monoclase propio.

## 5. Determinismo

Registrar Python, framework, hardware, CUDA/cuDNN, `PYTHONHASHSEED`, seeds de
Python/NumPy/framework/DataLoader/aumentación y operaciones no deterministas. Dos
evaluaciones del mismo peso y split producen métricas idénticas. La repetibilidad del
entrenamiento usa tolerancia aprobada y se reporta por separado.

## 6. Análisis de errores

Seleccionar reproduciblemente 10–15 correctos y 10–15 incorrectos. Registrar
`source_asset_id`, confianza, IoU, tipo de error e hipótesis. Categorías mínimas:
omisión, falso positivo, fondo/iluminación, producto recortado, caja automática
deficiente y dominio no representado.
