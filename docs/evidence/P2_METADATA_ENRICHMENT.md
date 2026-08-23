# P2-003 / P2-004 — AMARKET Metadata Enrichment (Phase 2)

Ejecutor: mbarbacardozo (GitHub login verificado vía `gh api user --jq .login`)
Rama: `feat/mbarbacardozo/P2-003-metadata-enrichment`
Main gobernante verificado antes de modificar: `3b4b97d1bd19b2e5625d6432d7b6e57c0b9b4522`
(`git fetch origin && git rev-parse origin/main` — coincide con el commit
esperado; `docs/governance/03_PHASE2/` confirmado presente antes de tocar código)

Documentos gobernantes leídos antes de implementar (ninguno modificado):
- `01_CONTRACT_SDD_PHASE2_v2_0_0_FROZEN.md`
- `02_OPERATING_MANUAL_PHASE2_v2_0_0_FROZEN.md`
- `05_METADATA_ENRICHMENT_CONTRACT_v1_0_0.md`
- `08_QA_GATES_PHASE2_v1_0_0.md`

`docs/governance/03_PHASE2/*` (incluido `09_TASK_POOL_PHASE2.csv`, protegido
por `MANIFEST_SHA256.txt`) no fue modificado en esta rama.

## Alcance

- **P2-003**: `src/data/enrich_amarket_metadata.py` + `configs/metadata_enrichment.yaml`
  + `tests/test_enrich_amarket_metadata.py` (10 tests, sin red real).
- **P2-004**: ejecución real sobre los 655 SKU canónicos de
  `data/manifests/splits.csv` → `data/manifests/source_assets_enriched.csv`
  + `outputs/metadata_enrichment_summary.json` (no versionado, `outputs/`
  está en `.gitignore`; conteos reproducidos aquí).

## Comando ejecutado (P2-004, corrida real completa)

```
python -m src.data.enrich_amarket_metadata --full-run
```

- User-Agent declarado: `PROJECT_AMARKETBOUNDINGBOXES/1.0 academic-metadata-enrichment`
- `timeout_seconds=20`, `max_retries=3`, `backoff_seconds=2.0`, `delay_seconds=1.0`
  (mismos valores que `configs/data_sources.yaml`/`data_sources_full.yaml`, ya
  aceptados en el proyecto para tráfico cortés hacia amarket.com.bo)
- Reintentos acotados solo sobre códigos retryables (429/500/502/503/504),
  reutilizando `RETRYABLE_STATUS_CODES`/`request_with_retries` de
  `src/scraper_extraction.py` — un 404 no reintenta.
- Endpoints consultados por SKU: `https://amarket.com.bo/products/{sku}` y
  `https://amarket.com.bo/products/{sku}.js`. Ninguna URL de imagen
  (`cdn/shop/...`) fue solicitada — verificado por diseño (el código nunca
  construye esa URL) y por test (`test_enrich_row_never_requests_image_paths`,
  que hace fallar el doble de red ante cualquier URL no declarada).
- Inicio: 2026-08-22 22:36:39 (local). Fin: 2026-08-23T03:09:49.930120+00:00 (UTC,
  `generated_at` del summary). Duración ≈ 33 min para 655 SKU × 2 endpoints
  (1310 peticiones) con 1.0 s de delay cortés entre peticiones.

## Conteos REALMENTE observados (corrida real, no forzados)

```
SOURCE_ROWS            = 655
PROCESSED              = 655
HTML_OK                = 652 / 655
JS_OK                  = 652 / 655
VENDOR_FOUND           = 652 / 655
TAGS_FOUND             = 652 / 655
DIRECT_CATEGORY_FOUND  = 0 / 655
FAILURES               = 3
```

Estos valores coinciden exactamente con la referencia de corrida previa del
coordinador (655/652/652/652/652/0, mismos 3 SKU en 404). Se reportan porque
la corrida real de esta ejecución los reprodujo de forma independiente —no
porque se hayan forzado. Si una corrida futura del sitio arrojara cifras
distintas, deben registrarse esas nuevas cifras y no estas.

### Los 3 SKU en 404 (idénticos a los conocidos previamente)

| sku_id | html_http_status | js_http_status | metadata_status |
|---|---|---|---|
| 7899620665101 | 404 | 404 | FAILED |
| 309974700139 | 404 | 404 | FAILED |
| 309971879203 | 404 | 404 | FAILED |

Los 652 SKU restantes: `html_status=OK`, `js_status=OK`, `html_http_status=200`,
`js_http_status=200`, `metadata_status=OK`.

## Validación de aceptación (P2-G1, contrato 05)

Verificado programáticamente sobre el CSV real de salida
(`data/manifests/source_assets_enriched.csv`):

- **Todas las URL de producto canónicas fueron consultadas exactamente una
  vez** (655 filas procesadas, una petición HTML + una JS por fila, salvo
  reintentos acotados internos ante códigos retryables).
- **`output row count == input row count`**: 655 == 655.
- **Sin `source_asset_id` duplicado**: `len(ids) == len(set(ids))` → OK.
- **Identidad preservada sin alteración**: `sku_id`, `split`, `source_sha256`,
  `image_path`, `label_path` de cada fila de salida coinciden byte a byte con
  `data/manifests/splits.csv` (0 discrepancias sobre 655 filas comparadas).
- **Cobertura de categoría reportada, no adivinada**: `category_direct` se
  llenó 0/655 veces porque ninguna ficha de producto real declara un campo
  "Categoría:" propio (solo existe un menú de navegación genérico "Categorías"
  en el layout del sitio, verificado manualmente en varias fichas de muestra
  antes de programar la extracción — nunca se usó ese texto de navegación
  como fuente). `category_status=UNKNOWN` en los 3 SKU con 404 (no se pudo
  determinar), `category_status=NOT_FOUND` en los 652 restantes.
- **Lista de fallos emitida**: `outputs/metadata_enrichment_summary.json` →
  `failures` (3 entradas, ver tabla arriba).
- **Sin descarga de imágenes**: el código nunca construye ni solicita una URL
  `cdn/shop/...`; confirmado también por test dedicado.

## Regla dura verificada: tags/product_type nunca se vuelven categoría

652/655 fichas trajeron `shopify_tags` no vacío (ejemplos reales observados:
`"Lo Nuevo; STICKERS1"`, `"Lo Nuevo; Ofertas de la Semana"`,
`"Lo Nuevo; VENTAPORPESO"`, `"Lo Nuevo; STICKERS2"`). Se verificó
programáticamente que **ninguna** de las 652 filas con tags de tipo
promocional (`Lo Nuevo`, `Ofertas`, `STICKERS*`, etc.) tiene `category_direct`
poblado — 0/652. El código nunca copia `shopify_tags` ni `product_type` al
campo `category_direct`; ese campo solo se llena si la ficha HTML declara una
etiqueta reconocida y explícita (`DIRECT_LABEL_MAP` en
`src/data/enrich_amarket_metadata.py`), lo cual no ocurrió en ningún SKU real.

## Campos extraídos cuando existían

- `page_title`, `description_detail`: desde meta `og:title`/`og:description`
  de la ficha HTML (fallback a la descripción Shopify truncada a 600
  caracteres solo si el HTML no trae meta description).
- `vendor`, `shopify_tags`, `product_type`: desde el endpoint Shopify
  `/products/{sku}.js` (campos `vendor`, `tags`, `type`).
- `presentation`: desde la etiqueta directa "Unidad de venta:" presente en
  las fichas reales (verificado en muestra manual antes de programar; no es
  el mismo texto literal "Presentación" del POC original, pero es el campo
  estructurado equivalente que el sitio real expone hoy). Poblado en 650/652
  fichas OK; distribución observada: Unidad=329, Bolsa=156, Frasco=62,
  Pack=23, Paquete=21, Lata=20, Caja=14, Set=10, Pieza=8, Sobres=4, Par=2,
  Blister=1.
- `brand_direct`, `technical_product`, `size`, `units`, `materials`,
  `category_direct`: reconocidos por el mismo mecanismo de etiqueta directa
  (`DIRECT_LABEL_MAP`), pero **no observados en ninguna ficha real de los 655
  SKU** durante esta corrida — quedan vacíos, no inferidos. Si una ficha
  futura los declarara explícitamente, el extractor los capturaría sin
  cambios de código.

## Columnas del manifest enriquecido

`data/manifests/source_assets_enriched.csv` conserva las 10 columnas
originales de `splits.csv` (`sku_id`, `source_asset_id`, `duplicate_group_id`,
`class_id`, `split`, `image_path`, `label_path`, `source_sha256`,
`box_algorithm_version`, `parameters_hash`) y agrega 22 columnas de
enriquecimiento: `product_url`, `html_status`, `html_http_status`,
`js_status`, `js_http_status`, `page_title`, `vendor`, `shopify_tags`,
`product_type`, `brand_direct`, `technical_product`, `size`, `units`,
`materials`, `presentation`, `category_direct`, `category_status`,
`description_detail`, `metadata_status`, `metadata_error`,
`metadata_retrieved_at`, `metadata_parser_version`.

`metadata_status`/`metadata_http_status`(=`html_http_status`)/`category`
(=`category_direct`)/`brand`(=`brand_direct`) del contrato 05 quedan
satisfechos bajo estos nombres más específicos, documentado aquí para
trazabilidad; no se duplicó la columna con dos nombres distintos para el
mismo valor.

## Tests

Focalizados (sin red real, `src.scraper_extraction.request_with_retries`
interceptado):

```
python -m pytest tests/test_enrich_amarket_metadata.py -v
```

10/10 PASSED:
- `test_build_product_urls_uses_contractual_pattern`
- `test_html_with_direct_category_is_captured`
- `test_html_without_category_leaves_it_empty`
- `test_shopify_tags_never_become_category`
- `test_html_404_marks_not_found_and_metadata_failed`
- `test_identity_fields_are_preserved_unchanged`
- `test_enrich_row_never_requests_image_paths`
- `test_run_output_row_count_equals_input_and_no_duplicates`
- `test_load_input_rows_rejects_duplicate_source_asset_id`
- `test_load_input_rows_rejects_missing_identity_field`

Suite completa del repositorio:

```
python -m pytest tests/ -q
```

**Primera corrida**, con Python 3.13.9 del sistema (sin `.venv`,
`ultralytics`/`torch` no instalados): 104 passed, 1 skipped, 2 failed. Los 2
fallos (`test_train_evaluate_cli.py::test_01_smoke_train_produce_artefactos_contractuales`
y `::test_04_evaluacion_repetida_sobre_mismo_peso_es_identica`) eran por
`ModuleNotFoundError: No module named 'torch'`.

**Segunda corrida**, ya con `.venv` creado con el Python pinneado del
proyecto (`py -3.11`, `python --version` → `Python 3.11.9`) y
`requirements.txt` instalado íntegro (`pillow==12.3.0`, `numpy==2.4.6`,
`ultralytics==8.4.120`, `PyYAML==6.0.3`, `pandas==3.0.5`, `pytest==9.1.1`):
106 passed, 1 failed. Con `torch` presente, los 2 fallos anteriores y el
test antes `skipped` ahora corren y pasan. Aparece 1 fallo distinto:
`test_scraper_extraction.py::TestScraperExtraction::test_s02_incomplete_config_fails`,
por un problema de encoding de `subprocess` en Windows (el mensaje de error
`"Falta la sección obligatoria"` llega a `stderr` como
`"Falta la secciÃ³n obligatoria"`, con tilde/ñ mal decodificados, y el
`assertIn` literal no matchea). Es **preexistente y no relacionado con esta
tarea**: pertenece a `tests/test_scraper_extraction.py` sobre
`src/scraper_extraction.py`, ninguno de los dos tocado por este cambio
(`git log -1` sobre ambos apunta a `d24bd800`, PR #31, ajeno a esta rama).
No aparecía en la primera corrida porque bajo Python 3.13.9 del sistema esa
combinación específica de locale/`subprocess`/encoding se comportaba
distinto; es un hallazgo de entorno Windows, no una regresión introducida
aquí.

Ninguna de las dos corridas de la suite completa registra un fallo dentro de
`src/data/enrich_amarket_metadata.py`, `configs/metadata_enrichment.yaml` ni
`tests/test_enrich_amarket_metadata.py`: los 10/10 tests focalizados de esta
tarea pasan de forma idéntica en ambos entornos.

## No agregado sin necesidad

Ninguna dependencia nueva: el enriquecedor reutiliza `PoliteHttpClient`,
`ProductParser`, `atomic_write_csv`, `atomic_write_json` y `read_csv_rows` ya
existentes en `src/scraper_extraction.py`. Solo usa librería estándar +
`PyYAML` (ya en `requirements.txt`).

## Archivos de esta tarea

- `src/data/enrich_amarket_metadata.py`
- `configs/metadata_enrichment.yaml`
- `tests/test_enrich_amarket_metadata.py`
- `data/manifests/source_assets_enriched.csv` (655 filas + encabezado)
- `docs/evidence/P2_METADATA_ENRICHMENT.md` (este archivo)

`outputs/metadata_enrichment_summary.json` se generó localmente y no se
versiona (`outputs/*` en `.gitignore`); sus conteos quedan reproducidos
íntegramente en este documento para evidencia.

## STOP-THE-LINE (2026-08-23) — esquema de salida incompatible con el contrato

Corrección de alcance recibida del coordinador después del commit
`6542a8f`: el esquema de salida usado hasta ese commit **no** es el
contractual. `docs/governance/03_PHASE2/11_ENRICHED_MANIFEST_SCHEMA.csv`
exige literalmente estas columnas:

```
source_asset_id,sku_id,product_name,description,brand,technical_product,
size,units,materials,presentation,category,product_page_url,image_url,
sha256,split,metadata_retrieved_at,metadata_http_status,
metadata_parser_version,metadata_status,metadata_error
```

`05_METADATA_ENRICHMENT_CONTRACT_v1_0_0.md` (§Input/§Output) confirma que
ese esquema asume un **manifest fuente canónico ya existente** que trae
`product_name`, `description`, `product_page_url`, `image_url` y `sha256`
como columnas originales a preservar — el enriquecedor solo debe *agregar*
`brand`, `technical_product`, `size`, `units`, `materials`, `presentation`,
`category`, `metadata_retrieved_at`, `metadata_http_status`,
`metadata_parser_version`, `metadata_status`, `metadata_error`.

Las columnas usadas hasta `6542a8f` (`brand_direct`, `category_direct`,
`html_http_status`, `js_http_status`, `page_title`, `description_detail`,
`product_url` reconstruido desde `sku_id`) **no son sustitutos válidos**
de las columnas contractuales — instrucción explícita del coordinador.

### P2-002 = BLOCKED

`data/manifests/splits.csv` (la entrada usada hasta ahora) **no** trae
`product_page_url`, `image_url`, `product_name` ni `description` — esas
columnas solo existen en un manifest fuente tipo `source_assets.csv` con
655 filas, que debe unirse a `splits.csv` por `source_asset_id`. Búsqueda
realizada antes de continuar:

1. **Historial completo de git, todas las ramas**
   (`git log --all -- "data/manifests/source_assets*.csv"`): solo 2
   commits tocaron `data/manifests/source_assets.csv` en toda la historia
   del repo, ambos de la rama original SCR-001 — sigue siendo la muestra
   de 3 filas del smoke test, nunca una corrida completa de 655.
   `data/manifests/source_assets_full.csv` (ruta de salida configurada en
   `configs/data_sources_full.yaml` para `--full-crawl`) tiene **cero
   commits** en cualquier rama del repositorio.
2. **Convención del proyecto**: la rama sin mergear
   `docs/andres/drive-paths-local` documenta que los artefactos grandes de
   una corrida completa (imágenes, y por la misma lógica el manifest
   fuente completo) viven en una carpeta compartida de Google Drive
   montada localmente por cada integrante, no en git.
3. **Google Drive local de esta máquina** (`G:\`, Google Drive for
   Desktop montado): no existe ninguna carpeta llamada
   `PROJECT_AMARKETBOUNDINGBOXES` ni `AMARKET` en su raíz — es el Drive
   personal de esta cuenta, sin relación con el proyecto compartido del
   equipo.

**Conclusión: el manifest canónico de 655 activos no está disponible en
este entorno de ejecución.** Siguiendo la instrucción explícita del
coordinador ("no reconstruir ni inventar valores silenciosamente"), se
reporta el bloqueo en vez de sustituir esas columnas con valores
reconstruidos o re-obtenidos por scraping en vivo.

### Corrida completa NO repetida

Por el mismo motivo, no se repitió la corrida real de los 655 SKU: el
punto 6 de la instrucción del coordinador condiciona esa repetición a que
los tests focalizados pasen sobre el esquema contractual corregido, lo
cual no es alcanzable mientras P2-002 siga bloqueado. La corrida en
background que estaba en curso al recibir el STOP-THE-LINE fue
interrumpida limpiamente (`TaskStop`, equivalente a Ctrl+C) sin borrar
ningún archivo; `data/manifests/source_assets_enriched.csv` sigue siendo
la última salida completa válida (655 filas), generada con el esquema
`brand_direct`/`category_direct`/... anterior a esta corrección, que
queda documentado aquí como **no conforme al esquema contractual
11_ENRICHED_MANIFEST_SCHEMA.csv**.

### Sin cambios de código en esta pausa

No se modificó `src/data/enrich_amarket_metadata.py`,
`tests/test_enrich_amarket_metadata.py` ni `data/manifests/source_assets_enriched.csv`
en esta corrección de alcance: renombrar columnas sin poder poblar
`product_name`/`description`/`product_page_url`/`image_url` con
procedencia real no resuelve el bloqueo de fondo, y el coordinador
indicó explícitamente detenerse aquí en vez de autorizar sustitutos
en vivo o reconstrucción.

## Estado

P2_002 = BLOCKED (manifest canónico de 655 activos con
`product_page_url`/`image_url`/`product_name`/`description` no localizado
en este entorno)

P2_METADATA = BLOCKED (esquema de salida no conforme a
`11_ENRICHED_MANIFEST_SCHEMA.csv` mientras P2-002 siga bloqueado; el
commit `6542a8f` NO debe considerarse `READY_FOR_REVIEW` bajo el esquema
contractual)

No autoaprobado. No mergeado. `docs/governance/03_PHASE2/*` no fue
modificado. Sin cambios de código adicionales en esta corrección; en
espera de que el coordinador resuelva la dependencia de P2-002 (aportar
el manifest canónico o autorizar explícitamente una estrategia
alternativa) antes de continuar.
