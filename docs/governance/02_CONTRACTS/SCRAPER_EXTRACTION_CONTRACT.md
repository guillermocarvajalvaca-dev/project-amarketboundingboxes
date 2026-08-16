# Contrato de scraping y extracción de Amarket v1.0.0 — FROZEN

## 1. Propiedad y frontera

Monserrat Barba implementa `src/scraper_extraction.py`; Andrés Poiche verifica. El
script descarga fotografías candidatas y produce un manifest. No crea máscaras,
bounding boxes, etiquetas YOLO ni splits.

## 2. Fuente y política

- Colección inicial: `https://amarket.com.bo/collections/lo-nuevo`
- Dominio de producto: `https://amarket.com.bo/.../products/...`
- Dominio de imagen permitido: `https://amarket.com.bo/cdn/shop/files/...`
- Fuente constante: `AMARKET`
- `robots.txt` observado el 2026-08-15: catálogo público permitido; rutas privadas y
  transaccionales quedan fuera.
- No se automatiza login, carrito, checkout, pago, órdenes ni cuenta.
- El piloto privado no equivale a permiso de redistribución.

## 3. Configuración explícita

```yaml
source:
  name: AMARKET
  collection_url: https://amarket.com.bo/collections/lo-nuevo
http:
  user_agent: PROJECT_AMARKETBOUNDINGBOXES/1.0 academic-smoke-test
  delay_seconds: 1.0
  timeout_seconds: 20
  max_retries: 3
  backoff_seconds: 2.0
limits:
  max_products: 3
  max_images_per_product: 1
outputs:
  images_dir: data/raw/amarket
  manifest: data/manifests/source_assets.csv
  rejects: data/manifests/scrape_rejections.csv
  summary: outputs/scrape_summary.json
```

Los valores anteriores gobiernan el smoke test. El crawl completo exige una nueva
configuración aprobada con O-001/O-007 cerradas. No hay defaults ocultos.

## 4. Flujo normativo

1. Validar configuración antes de red.
2. Consultar `robots.txt` y detenerse si las rutas objetivo dejan de estar permitidas.
3. Obtener colección, validar HTTP y `Content-Type`.
4. Extraer URLs de producto, canonicalizarlas, ordenarlas y eliminar duplicados.
5. Para cada producto dentro del límite extraer SKU, nombre, descripción, URL de
   ficha y URL de imagen principal.
6. Descargar una imagen con delay, timeout, retry y backoff acotados.
7. Validar HTTP, MIME, tamaño máximo, extensión real y decodificación.
8. Registrar `W`, `H`, modo, SHA-256 y duplicados.
9. Guardar de forma idempotente; nunca sobreescribir bytes distintos en silencio.
10. Emitir manifest, rechazos y resumen con conteos reconciliados.

No se extraen precios, stock, opiniones, datos personales ni información del carrito.

## 5. Manifest mínimo

```text
source_asset_id,sku_id,product_name,description,source_name,
product_page_url,image_url,retrieved_at,retrieval_run_id,http_status,
content_type,scraper_version,sha256,duplicate_group_id,width_px,height_px,
image_mode,background_mode,rights_status,acceptance_status,rejection_reason,
local_path
```

`source_asset_id` deriva de una cadena canónica que incluya fuente, ficha, imagen y
hash de bytes. `description` puede ser nula si no existe, pero la ausencia se registra;
no se inventa texto. `sku_id` identifica el producto para trazabilidad y agrupación,
no determina la clase YOLO.

## 6. Criterios de aceptación de imagen

Pasa a Andrés solo si:

- decodifica;
- contiene exactamente un producto principal;
- el fondo es `TRANSPARENT_ALPHA` o `UNIFORM_RGB`;
- dimensiones son positivas;
- hash y fuente están registrados;
- no es un duplicado no resuelto;
- su uso previsto está registrado en `rights_status`.

Una imagen compleja, multiproducto, corrupta o sin procedencia se rechaza con razón.

## 7. Idempotencia y reanudación

- Mismos URL y bytes no crean otra fila/archivo.
- Mismos bytes desde URLs distintas comparten `duplicate_group_id`.
- Bytes cambiados crean nueva versión; no destruyen evidencia previa.
- Reanudar conserva éxitos cuyo archivo y hash aún coinciden.
- Manifest y resumen se escriben de forma atómica o quedan como fallo explícito.

## 8. Pruebas S01–S10

| ID | Caso | Esperado |
|---|---|---|
| S01 | `--help` | código 0 y argumentos |
| S02 | config incompleta | falla antes de red |
| S03 | URLs duplicadas/desordenadas | únicas, canónicas y ordenadas |
| S04 | 404/429/500 | retry/rechazo acotado |
| S05 | MIME no imagen | rechazo |
| S06 | bytes corruptos | rechazo |
| S07 | misma URL/bytes dos veces | idempotente |
| S08 | mismos bytes/URLs distintas | mismo grupo duplicado |
| S09 | interrupción/reanudación | conserva éxitos |
| S10 | fin de piloto | archivos, filas y conteos reconcilian |

S01–S10 usan fixtures/mocks. Después se ejecuta un piloto real de hasta tres productos.

## 9. Evidencia previa disponible

Smoke test diagnóstico del 2026-08-15, sin constituir implementación de Monserrat:

- colección: HTTP 200, HTML, 24 enlaces únicos observados;
- JSON de colección con límite 1: HTTP 200;
- ficha: HTTP 200, SKU extraíble y candidatos de imagen;
- imagen: HTTP 200, JPEG 700×700 decodificable;
- `robots.txt`: HTTP 200 y catálogo público permitido.

Esto demuestra viabilidad técnica inicial, no S01–S10 ni el scraper final.

## 10. Done when

S01–S10 pasan, el piloto real respeta el límite, produce outputs contractuales y el
revisor reproduce el caso mínimo. El crawl completo sigue bloqueado hasta aprobar
tamaño y derechos.
