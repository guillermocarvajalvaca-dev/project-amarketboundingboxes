# Brief — Andrés Poiche

## Misión

Transformar las imágenes aceptadas en un dataset YOLO monoclase mediante extremos de
píxeles y crear splits sin fuga por SKU/linaje.

## Artefactos propios

- `src/data/make_boxes.py`
- `outputs/box_audit.csv` y grilla visual
- `src/data/make_splits.py`
- `configs/dataset.yaml`
- `notebooks/eda.ipynb`

## Ejecución

1. Validar el handoff de Monserrat sin editarlo.
2. Convertir T01–T10 en pruebas.
3. Implementar máscara RGBA/RGB y obtener los cuatro extremos.
4. Usar bordes semiabiertos `x_max+1`, `y_max+1`.
5. Escribir siempre `class_id=0` con seis decimales.
6. Auditar imagen, máscara, extremos, caja y rechazo.
7. Agrupar por SKU, hash, duplicado y derivados antes del split.
8. Ejecutar EDA, QA visual y prueba anti-fuga.
9. Entregar dataset/splits congelados a Pablo.

## Done when

T01–T10 pasan; una etiqueta por aceptada; cero clases distintas de 0, huérfanos,
cajas inválidas o fugas; Pablo carga el dataset sin modificarlo.

## No debes

Cambiar scraper, usar SKU como clase, crear escenas multiproducto, usar `rembg` sin
cambio contractual, ajustar el modelo o regenerar splits después de mirar test.
