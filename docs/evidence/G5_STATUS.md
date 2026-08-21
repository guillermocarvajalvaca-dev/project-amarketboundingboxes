# G5 — Evaluación final del modelo gobernante

## Modelo

Experimento A — AMARKET-only.

- Weight SHA-256: `9149dfef3093ca12a80fbb85b860822ae52d6ca5d8e2f1a6224211f92acd6712`
- Dataset de evaluación: AMARKET test congelado
- Test images: 98
- Ground truths: 98
- Tuning posterior a G4: NO

## Protocolo

Evaluación ejecutada mediante `src/evaluate.py` sobre `split=test`, CPU,
`conf=0.25`, `IoU=0.5`, con test desbloqueado únicamente después del cierre
formal de G4.

Se ejecutaron dos evaluaciones independientes del mismo peso/split y las métricas
resultaron idénticas.

## Métricas finales

- Precision: 1.000000
- Recall: 1.000000
- F1: 1.000000
- mAP50: 0.995000
- mAP75: 0.995000
- mAP50-95: 0.992875

## Análisis de errores

El protocolo automático encontró:

- correctos seleccionados: 15
- incorrectos observados: 0

No se modificaron `conf`, IoU, datos, modelo ni pesos después de observar test para
forzar errores artificiales.

Como análisis complementario se extrajeron reproduciblemente los 15 casos correctos
más difíciles del test:

- lowest IoU: 0.896037
- highest IoU del grupo: 0.978347
- todos permanecen por encima del umbral contractual IoU=0.5

La ausencia de 10–15 ejemplos incorrectos no se oculta ni se sustituye por casos
fabricados. El evaluador selecciona todos los errores disponibles cuando existen menos
del rango objetivo; en esta ejecución el número disponible fue cero.

## Reproducibilidad

- RUN1: `outputs/evaluation/g5_amarket_test_A_run1_20260821_124539`
- RUN2: `outputs/evaluation/g5_amarket_test_A_run2_20260821_124539`
- métricas RUN1 == RUN2: PASS
- weight SHA RUN1 == RUN2 == peso congelado: PASS

## Estado

`G5_STATUS=PASSED`

La evaluación final del peso gobernante fue reproducible y no hubo tuning sobre test.
