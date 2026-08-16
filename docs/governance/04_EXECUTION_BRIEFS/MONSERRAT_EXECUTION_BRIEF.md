# Brief — Monserrat Barba

## Misión

Construir la adquisición ética, trazable e idempotente de imágenes de productos de
Amarket. Tu módulo entrega datos; no genera cajas ni clases.

## Artefactos propios

- `configs/data_sources.yaml`
- `src/scraper_extraction.py`
- `src/data/validate_downloads.py`
- `data/manifests/source_assets.csv`
- rechazos, resumen, mini-datasheet y sección Datos

## Ejecución

1. Convertir S01–S10 en pruebas antes de ampliar el piloto.
2. Confirmar robots, términos, UA, delay, timeout y límite.
3. Ejecutar `--limit 3`; extraer imagen principal, SKU, nombre, descripción y URLs.
4. Validar MIME, decodificación, dimensiones, hash y duplicados.
5. Aceptar solo producto aislado con fondo uniforme/transparente.
6. Registrar todo rechazo; no borrar ni corregir silenciosamente.
7. Entregar manifest congelado a Andrés mediante PR/handoff.

## Done when

S01–S10 y piloto pasan; archivos/manifest/resumen reconcilian; Andrés reproduce el
caso mínimo. El crawl completo sigue bloqueado hasta O-001/O-007.

## No debes

Extraer precios, stock, datos personales o checkout; publicar imágenes por defecto;
inventar licencia; crear bounding boxes, splits o modelo.
