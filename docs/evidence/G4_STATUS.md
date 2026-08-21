# Estado G4 — Entrenamiento final AMARKET (Pablo Linares)

Evidencia de ejecución de G4 (issue #6, TRN-001), tras autorización expresa del
coordinador. LD-006 quedó levantada exclusivamente para G4 mediante los comentarios
de @guillermocarvajalvaca-dev en el issue #6 (2026-08-21T13:20:33Z y corrección
2026-08-21T13:40:13Z), que resuelven O-003 y O-004 como `APPROVED`.

## Autorización de referencia

- O-003 (baseline y versiones): `APPROVED` — `yolo11n.pt`, transfer learning desde
  COCO, Ultralytics 8.4.120, PyTorch 2.13.0, Python 3.11.9.
- O-004 (hardware y presupuesto): `APPROVED` — hardware gobernante: Apple M5, 24 GB
  RAM, GPU integrada, CUDA=False, dispositivo oficial CPU-only. Presupuesto:
  epochs=40, imgsz=416, batch=8, optimizer=auto, lr0=0.01, sin augmentación.
- `G4_STATUS=AUTHORIZED` (comentario del coordinador en issue #6).

## Entorno gobernante

- Python 3.11.9 exacto (instalado vía `uv`, venv nuevo `.venv-g4-3119`, no se tocó
  el `.venv` existente).
- Ultralytics 8.4.120, PyTorch 2.13.0+cpu.
- Dispositivo: **CPU** (MPS disponible en el hardware pero no usado para la
  ejecución gobernante, conforme a `docs/ENVIRONMENT.md` / GOV-002).
- Pines de `requirements.txt` verificados exactos: Pillow 12.3.0, numpy 2.4.6,
  PyYAML 6.0.3, pandas 3.0.5, pytest 9.1.1.
- Commit base: `19fff77f1cca9012bafa886e5195d5ebc2230cfa` (`origin/main`).

## Dataset

Dataset congelado `AMARKET_YOLO_DATASET_655_SEED42` (Google Drive privado, no
redistribuido — LD-003), montado localmente vía symlink, sin copiar ni modificar:

- `data/manifests/splits.csv` (canónico en `main`): 655 filas.
- train=459, val=98, test=98.
- missing_images=0, missing_labels=0, invalid_class=0.
- `ultralytics.data.utils.check_det_dataset` resuelve `train`/`val` dentro de la
  raíz del dataset congelado. `test` no se consultó (`TEST_USED_FOR_TUNING=NO`).

## Ejecución

```text
python src/train.py --config configs/baseline.yaml --data configs/dataset.yaml \
    --output-dir outputs/runs/g4_smoke_amarket_20260821_100653 --seed 42 --smoke

python src/train.py --config configs/baseline.yaml --data configs/dataset.yaml \
    --output-dir outputs/runs/g4_amarket_only_20260821_100653 --seed 42
```

- Exit code: 0 en ambas corridas.
- Smoke: PASS, generó `weights/best.pt` antes de lanzar el entrenamiento final.
- Entrenamiento final: 40/40 epochs completados en 0.318 horas (~19 min) en CPU.

## Resultado

Métricas finales sobre `val` (98 imágenes, 98 instancias):

| Métrica | Valor |
|---|---|
| Precision | 0.999 |
| Recall | 0.99 |
| mAP50 | 0.995 |
| mAP50-95 | 0.986 |

- `BEST_WEIGHT_SHA256`: `9149dfef3093ca12a80fbb85b860822ae52d6ca5d8e2f1a6224211f92acd6712`
- Output dir local: `outputs/runs/g4_amarket_only_20260821_100653/` (no versionado,
  `outputs/*` está en `.gitignore` — pesos, curvas y logs quedan solo en disco local
  y son reproducibles con los comandos de arriba sobre el mismo dataset congelado).
- Artefactos generados en ese directorio: `weights/best.pt`, `weights/last.pt`,
  `resolved_config.yaml`, `environment.json`, `train_log.csv`, `args.yaml`,
  `results.png`, `BoxPR_curve.png`, `BoxF1_curve.png`, `confusion_matrix.png`,
  `confusion_matrix_normalized.png`, muestras `train_batch*.jpg`/`val_batch*.jpg`.

## Alcance y prohibiciones respetadas

- No se consultó ni se usó `test` en ningún momento (selección con `val` únicamente).
- No se modificó `requirements.txt` ni los pines declarados.
- No se usó Apple MPS para la ejecución gobernante.
- No se copiaron ni redistribuyeron las imágenes del dataset (symlink únicamente).
- Sin datos/pesos grandes versionados en el repo.

## Estado

`G4_AMARKET_TRAINING=PASS`. Queda pendiente de revisión independiente del
coordinador antes de considerar G4 formalmente cerrado (`NEXT=FREEZE_G4_AND_PREPARE_RPC_RUN`,
según su propia autorización).
