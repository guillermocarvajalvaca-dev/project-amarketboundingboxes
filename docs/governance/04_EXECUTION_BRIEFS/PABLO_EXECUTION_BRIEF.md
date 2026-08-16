# Brief — Pablo Linares

## Misión

Implementar un detector preentrenado y una evaluación honesta sobre el dataset YOLO
monoclase congelado.

## Artefactos propios

- `configs/baseline.yaml`
- `src/train.py`
- `src/evaluate.py`
- `notebooks/analisis_errores.ipynb`
- Metodología y Resultados del informe

## Ejecución

1. Validar hashes de dataset/split; no corregir datos por tu cuenta.
2. Cerrar baseline/versiones/hardware antes del entrenamiento final.
3. Implementar `--help` y smoke train en `src/train.py`.
4. Entrenar con train y seleccionar con val; registrar cada experimento.
5. Guardar pesos, configuración resuelta, entorno, curvas y logs.
6. Desbloquear test únicamente después de G4.
7. Emitir métricas con fórmulas y repetir evaluación del mismo peso.
8. Crear 10–15 aciertos y 10–15 errores reproducibles.
9. Entregar interfaz y hash de peso a Guillermo.

## Done when

Entrenamiento CLI finaliza; test no fue usado para tuning; evaluación repetida
coincide; métricas/curvas/errores son trazables y Guillermo carga el peso.

## No debes

Cambiar datos/splits, usar SKU como clase, comparar cAcc con mAP, afirmar SOTA,
ocultar fallos o dejar entrenamiento/evaluación solo en notebook.
