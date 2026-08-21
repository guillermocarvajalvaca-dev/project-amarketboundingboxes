# Estado G4 — Experimento B, AMARKET+RPC (Pablo Linares)

Evidencia de ejecución del Experimento B de G4 (issue #6, TRN-001), segundo
entrenamiento real de G4, tras la autorización expresa del coordinador que
congeló el Experimento A (AMARKET-only) y habilitó el Experimento B.

Este documento complementa a `docs/evidence/G4_STATUS.md` (Experimento A).
No lo reemplaza: ambos experimentos quedan registrados de forma independiente
para permitir la comparación A vs. B que cierra G4.

## Autorización de referencia

- Comentario de @guillermocarvajalvaca-dev en issue #6
  (2026-08-21T14:39:05Z, "G4 — Freeze Experimento A: AMARKET-only"):
  congela el Experimento A (SHA-256 confirmado coincidente con
  `EV-G4-001`) y autoriza explícitamente el Experimento B
  (AMARKET+RPC en train, AMARKET-only en val/test), `NEXT=PABLO_G4_RPC_RUN`.
- La prohibición de usar RPC como dataset central no aplica a este
  Experimento B: RPC se utilizó únicamente como corpus auxiliar de
  entrenamiento; el dataset canónico del proyecto, `val` y `test` permanecen
  AMARKET. No se modifica el contrato FROZEN.
- `test` permanece bloqueado; no se desbloquea hasta que el coordinador
  cierre G4 formalmente comparando A vs. B (según su propia instrucción).

## Entorno gobernante

Idéntico al Experimento A (mismo venv, mismas versiones exactas):

- Python 3.11.9 exacto (`.venv-g4-3119`, mismo venv reutilizado, no se tocó
  el `.venv` existente).
- Ultralytics 8.4.120, PyTorch 2.13.0+cpu.
- Dispositivo: **CPU** (sin Apple MPS, conforme GOV-002).
- `configs/baseline.yaml` sin modificar: `yolo11n.pt`, epochs=40, imgsz=416,
  batch=8, device=cpu, seed=42.
- Commit base: `19fff77f1cca9012bafa886e5195d5ebc2230cfa` (`origin/main`).

## Dataset

Dos datasets congelados (Google Drive privado, no redistribuidos — LD-003),
montados localmente sin copiar ni modificar:

- `AMARKET_YOLO_DATASET_655_SEED42`: mismo dataset del Experimento A y de
  SPL-001 (655 filas, train=459/val=98/test=98).
- `AMARKET_RPC_YOLO_DATASET_1000_SEED42`: dataset auxiliar combinado
  AMARKET+RPC, usado **solo para el conjunto de train** de este experimento.

Descriptor de dataset **local, no versionado**, específico de este
experimento (`configs/dataset.yaml` NO se modificó — sigue siendo el
canónico AMARKET-only para G3/SPL-001):

- Archivo: `outputs/runs/g4_amarket_rpc_20260821_110741_dataset.yaml`
  (gitignored, referenciado aquí solo por nombre).
- `train`: `AMARKET_RPC_YOLO_DATASET_1000_SEED42/images/train` — 804
  imágenes (459 AMARKET + 345 RPC auxiliar).
- `val`: `AMARKET_YOLO_DATASET_655_SEED42/images/val` — 98 imágenes
  (AMARKET-only, mismo split congelado de SPL-001).
- `test`: no incluido en el YAML (`check_det_dataset` confirmó
  `test=None`); no se consultó.
- Validación previa: 0 missing images/labels, 0 clases inválidas en ambos
  conjuntos.

## Ejecución

```text
python src/train.py --config configs/baseline.yaml --data outputs/runs/g4_amarket_rpc_20260821_110741_dataset.yaml \
    --output-dir outputs/runs/g4_rpc_smoke_20260821_110741 --seed 42 --smoke

python src/train.py --config configs/baseline.yaml --data outputs/runs/g4_amarket_rpc_20260821_110741_dataset.yaml \
    --output-dir outputs/runs/g4_amarket_rpc_20260821_110741 --seed 42
```

- Exit code: 0 en ambas corridas.
- Smoke: PASS, generó `weights/best.pt` antes de lanzar el entrenamiento final.
- Entrenamiento final: 40/40 epochs completados en 0.504 horas (~30 min) en CPU.

## Resultado

Métricas finales sobre `val` (AMARKET-only, 98 imágenes, 98 instancias):

| Métrica | Experimento B (AMARKET+RPC) |
|---|---|
| Precision | 0.999 |
| Recall | 0.99 |
| mAP50 | 0.994 |
| mAP50-95 | 0.982 |

- `BEST_WEIGHT_SHA256`: `bba3ceca6366c376a39745ddc166cbc5cc9fa67f25fe4f6c719f64499ac10988`
- Output dir local: `outputs/runs/g4_amarket_rpc_20260821_110741/` (no
  versionado, `outputs/*` está en `.gitignore` — pesos, curvas y logs
  quedan solo en disco local y son reproducibles con los comandos de arriba
  sobre los mismos datasets congelados).
- Artefactos generados en ese directorio: `weights/best.pt`,
  `weights/last.pt`, `resolved_config.yaml`, `environment.json`,
  `train_log.csv`, `args.yaml`, `results.png`, `BoxPR_curve.png`,
  `BoxF1_curve.png`, `confusion_matrix.png`,
  `confusion_matrix_normalized.png`, muestras
  `train_batch*.jpg`/`val_batch*.jpg`.

## Comparación A vs. B

Ambos experimentos evaluados sobre el mismo `val` AMARKET-only (98
imágenes):

| Experimento | Train | Precision | Recall | mAP50 | mAP50-95 |
|---|---|---|---|---|---|
| A (`EV-G4-001`) | AMARKET-only (459) | 0.999 | 0.99 | 0.995 | 0.986 |
| B (`EV-G4-002`, este documento) | AMARKET+RPC (804) | 0.999 | 0.99 | 0.994 | 0.982 |

El corpus auxiliar RPC en train no mejora el desempeño sobre el val
AMARKET-only (leve caída de 0.001 en mAP50 y 0.004 en mAP50-95 frente a A);
tampoco lo degrada de forma relevante. Queda a criterio del coordinador la
decisión de cierre de G4 con base en esta comparación.

## Alcance y prohibiciones respetadas

- No se consultó ni se usó `test` en ningún momento (selección con `val`
  AMARKET-only únicamente).
- No se modificó `requirements.txt` ni los pines declarados.
- No se usó Apple MPS para la ejecución gobernante.
- No se modificó `configs/dataset.yaml` (sigue siendo el canónico
  AMARKET-only); el descriptor combinado es un YAML local, no versionado,
  exclusivo de este experimento.
- No se copiaron ni redistribuyeron las imágenes de ningún dataset (montaje
  vía symlink/acceso directo únicamente).
- Sin datos/pesos grandes versionados en el repo.

## Estado

`G4_RPC_TRAINING=PASS`. Queda pendiente de revisión independiente del
coordinador. Con Experimento A (`EV-G4-001`) y Experimento B (`EV-G4-002`)
registrados, corresponde al coordinador comparar A vs. B y cerrar G4
formalmente (`NEXT=FREEZE_G4_AND_PREPARE_RPC_RUN` original, ahora con ambos
experimentos disponibles), antes de desbloquear `test` para G5.
