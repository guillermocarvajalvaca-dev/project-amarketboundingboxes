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

## P2-002 = RESOLVED — handoff canónico recibido y verificado independientemente

El coordinador entregó el manifest canónico faltante:
`C:\Users\LENOVO\AppData\Local\Temp\P2_METADATA_SOURCE_86eaa30f39264d6a92041fe195de2686\source_assets_full.csv`.

No se aceptó por confianza — se verificó de forma independiente antes de
usarlo:

- **Hash**: `sha256(source_assets_full.csv)` calculado localmente =
  `01ce89ee9239c5a9ba70ca0bf46f05c1c1a926f81e4110cab6ffff2e1b3b9c38`,
  coincide exactamente con el declarado en el `HANDOFF_METADATA.txt` que
  acompaña el handoff.
- **Consistencia de esquema**: las columnas de `source_assets_full.csv`
  coinciden exactamente con `MANIFEST_FIELDS` de
  `src/scraper_extraction.py` (mismo orden), y su fila de ejemplo para
  SKU `7773401007956` trae `sha256=07ab51fe...`, idéntico al
  `source_sha256`/`duplicate_group_id` ya presentes en
  `data/manifests/splits.csv` para ese mismo SKU — confirmación
  criptográfica cruzada de que es el manifest original del que
  `splits.csv` fue derivado, no un archivo reconstruido.
- **Búsqueda de origen alternativo dentro del repo**: antes de aceptar
  el handoff se buscó si el manifest ya existía versionado en el repo
  (no) — ver sección STOP-THE-LINE anterior.
- Copiado a `data/manifests/source_assets_full.csv` (ruta ya designada
  por `configs/data_sources_full.yaml` para el output de
  `--full-crawl`), con hash verificado idéntico tras la copia. Este
  archivo es un manifest (~518 KB, sin imágenes), consistente con la
  restricción de "no agregar imágenes ni artefactos pesados".

### Join canónico ↔ splits.csv — resultados literales (post-merge de origin/main)

```
JOIN_MATCHED    = 655
JOIN_MISSING    = 0
JOIN_EXTRA      = 0
SKU_MISMATCHES  = 0
HASH_MISMATCHES = 0
SPLITS          = train=459, val=98, test=98
```

Validado programáticamente contra el árbol de trabajo después de
mergear `origin/main` (`a138929741ec8386b0f5382b16252da5e950dd0c`, PR
#41, que solo agregó archivos del compositor sintético — merge limpio,
sin conflictos, ver commit `1f9124e`).

## Reescritura del esquema de salida — conforme a 11_ENRICHED_MANIFEST_SCHEMA.csv

`src/data/enrich_amarket_metadata.py`, `configs/metadata_enrichment.yaml`
y `tests/test_enrich_amarket_metadata.py` fueron reescritos:

- **Input**: `join_canonical_with_splits()` une
  `data/manifests/source_assets_full.csv` (provee `product_name`,
  `description`, `product_page_url`, `image_url`, `sha256`) con
  `data/manifests/splits.csv` (provee `split`) por `source_asset_id`,
  exigiendo correspondencia exacta 655/655 en ambas direcciones y
  cruzando `sku_id` y `sha256`/`source_sha256` — cualquier discrepancia
  detiene la ejecución (`ValueError`) en vez de elegir un valor.
- **Provenance nunca reconstruida**: `product_name`, `description`,
  `product_page_url`, `image_url`, `sha256` se copian literalmente del
  manifest canónico al resultado final, incluso si el fetch en vivo de
  la página observa un `og:title`/`og:image` distinto (verificado por
  `test_canonical_provenance_is_never_overwritten_by_live_fetch`).
- **Columnas de salida**: exactamente las de
  `11_ENRICHED_MANIFEST_SCHEMA.csv` — `source_asset_id`, `sku_id`,
  `product_name`, `description`, `brand`, `technical_product`, `size`,
  `units`, `materials`, `presentation`, `category`, `product_page_url`,
  `image_url`, `sha256`, `split`, `metadata_retrieved_at`,
  `metadata_http_status`, `metadata_parser_version`, `metadata_status`,
  `metadata_error`. Ya NO existen `brand_direct`, `category_direct`,
  `html_http_status`/`js_http_status` ni un `product_url` reconstruido
  desde `sku_id` — verificado por
  `test_output_fields_match_governing_schema_exactly` y
  `test_run_writes_exact_governing_header`.
- **`brand`**: etiqueta directa "Marca:" en la ficha si existe; si no,
  `vendor` del JSON Shopify (campo directamente devuelto por la
  plataforma, no inferido por el código). `category` sigue **sin**
  aceptar `vendor`/`shopify_tags`/`product_type` como sustituto bajo
  ninguna circunstancia (`test_shopify_tags_never_become_category_and_vendor_becomes_brand`).
- **`.js` endpoint**: derivado de `product_page_url` agregando `.js`
  (`js_url_for`), preservando el prefijo real de colección
  (`/collections/lo-nuevo/products/{sku}.js`) en vez de asumir
  `/products/{sku}.js` — verificado en vivo antes de implementar
  (misma respuesta, 2803 bytes, que el endpoint sin prefijo).
- **robots.txt**: se consulta y se respeta por host antes de la
  primera fila (`check_robots`, reutilizado de `src/scraper_extraction.py`),
  y cada `product_page_url` se valida contra el parser resultante antes
  de pedirla.

### Tests — 19/19 focalizados, bajo `.venv` 3.11.9 / pytest 9.1.1 (post-merge)

```
.\.venv\Scripts\python.exe -m pytest tests/test_enrich_amarket_metadata.py -v
```

19 passed, exit code 0. Cubren: esquema exacto de columnas, join
655/655 (y sus 3 formas de fallo: faltante, sobrante, mismatch de
sku_id/sha256), preservación literal de provenance incluso ante fetch
en vivo distinto, derivación de `.js` con prefijo de colección, `brand`
desde etiqueta directa vs. `vendor`, `category` nunca desde tags, 404,
preservación de identidad end-to-end, ninguna URL de imagen solicitada,
conteo de filas de salida == filas fuente sin duplicados.

Suite completa del repositorio, mismo entorno: **219 passed, 1 failed**,
exit code 1. El único fallo
(`test_scraper_extraction.py::TestScraperExtraction::test_s02_incomplete_config_fails`)
es el mismo problema preexistente de encoding de `subprocess` en
Windows ya documentado arriba (pertenece a PR #31, no tocado por esta
rama). El incremento de 106→219 tests pasando corresponde a los ~113
tests nuevos traídos por el merge de `origin/main` (PR #41, compositor
sintético P2-006/P2-007), no a este cambio.

## Corrida completa de los 655 SKU — BLOQUEADA por rate-limit del sitio (Cloudflare 429)

Tras pasar el merge, el join 655/655 y los 19/19 tests focalizados, se
lanzó la corrida canónica real. **No completó**: interrumpida por
instrucción explícita del coordinador en la primera versión (antes del
merge, por disciplina de procedencia — sin datos perdidos), y la
segunda versión (ya post-merge, la única que cuenta como corrida
canónica) llegó a 438/655 filas antes de ser detenida, con 231/437
filas (>50%) en `metadata_status=FAILED`, concentradas desde
aproximadamente la fila 400 en adelante.

Diagnóstico (una sola petición de verificación, no una nueva corrida
completa):

```
HTTPError 429 Too Many Requests
Server: cloudflare
Cf-Mitigated: challenge
Body: página de reto "Verifying your connection..." de Cloudflare
```

Causa más probable: volumen acumulado de peticiones de las varias
corridas completas iniciadas hoy (varias interrumpidas a mitad de
camino por las sucesivas correcciones STOP-THE-LINE), no un problema
del código de reprocesamiento en sí — el mismo código, con delay
cortés de 1.0 s y reintentos acotados, había completado 655/655 sin
este problema en una corrida anterior del día (ver sección superior,
esquema no conforme pero HTTP 200 en 652/655).

**No se intentó eludir el reto de Cloudflare** — sería evasión de
detección, fuera de lo que este agente hace bajo cualquier
circunstancia. **No se relanzó la corrida de inmediato.** Decisión del
coordinador: esperar y reintentar más adelante, sin fijar un tiempo de
espera unilateralmente.

## Estado

P2_002 = RESOLVED (manifest canónico verificado independientemente por
hash + consistencia criptográfica cruzada con `splits.csv`; join
655/655 exacto, 0 discrepancias de sku_id/sha256, splits
train=459/val=98/test=98)

Esquema de salida (`src/data/enrich_amarket_metadata.py` +
`tests/test_enrich_amarket_metadata.py`) = CONFORME a
`11_ENRICHED_MANIFEST_SCHEMA.csv`, verificado por 19/19 tests
focalizados bajo `.venv` 3.11.9 / pytest 9.1.1 post-merge.

P2_METADATA (estado en este punto, superado por la sección siguiente) =
NOT_READY — bloqueada por rate-limit del sitio (HTTP 429 / Cloudflare),
no por el esquema ni por el join.
`LIVE_POST_MERGE_RUN=BLOCKED_AT_438_BY_HTTP_429` — este registro
histórico se conserva íntegro; la sección siguiente NO lo reemplaza,
lo complementa con una vía offline.

No autoaprobado. No mergeado. `docs/governance/03_PHASE2/*` no fue
modificado en ningún commit de esta rama.

## Normalización OFFLINE, DETERMINISTA y TRAZABLE (sin red) — instrucción final del coordinador

Instrucción explícita: cancelar cualquier reintento a AMARKET, no hacer
ninguna petición nueva al sitio, no intentar eludir Cloudflare. Producir
el CSV final del esquema gobernante reetiquetando observaciones de red
**ya reales**, tomadas de la corrida completa 655/655 previa a la
corrección de esquema (commit `d455aef`, presente sin cambios hasta
`afdfed1`), en vez de volver a contactar el sitio.

`NETWORK_OBSERVATIONS_SOURCE = PRIOR_SUCCESSFUL_655_ROW_RUN`
`SCHEMA_NORMALIZATION = OFFLINE_DETERMINISTIC`
`CLOUDFLARE_BYPASS = NO`
`DATA_INVENTED = NO`

### Fuentes usadas

1. **CSV legacy** (esquema no conforme, pero con 655/655 observaciones de
   red reales): materializado con
   `git show afdfed13d6f32e89762b51b95c7182e9673458e3:data/manifests/source_assets_enriched.csv`
   a una ruta temporal **fuera del repositorio** (no se sobrescribió
   nada del repo hasta validar).
2. `data/manifests/source_assets_full.csv` (manifest canónico, ya
   verificado por hash en la sección P2-002 anterior).
3. `data/manifests/splits.csv` (split por `source_asset_id`).

### Gates previos a transformar cualquier dato (calculados, no supuestos)

```
LEGACY_ROWS      = 655
CANONICAL_ROWS   = 655
SPLITS_ROWS      = 655
UNIQUE_SOURCE_IDS = 655 (idénticos en las tres fuentes: legacy_ids == canonical_ids == splits_ids)
JOIN_MATCHED     = 655
JOIN_MISSING     = 0
JOIN_EXTRA       = 0
SKU_MISMATCHES   = 0
HASH_MISMATCHES  = 0
SPLITS           = train=459, val=98, test=98
```

Todos los gates pasaron; no fue necesario un Stop-the-Line en este
paso.

### Implementación (código, no edición manual del CSV)

`src/data/enrich_amarket_metadata.py` gana:

- `load_legacy_enrichment(path)`: carga el CSV legacy, exige columnas
  requeridas y ausencia de `source_asset_id` duplicado.
- `normalize_legacy_row(joined_row, legacy_row)`: mapeo exacto —
  - `source_asset_id`/`sku_id`/`product_name`/`description`/
    `product_page_url`/`image_url`/`sha256`/`split` ← `joined_row`
    (join canónico + splits, NUNCA del CSV legacy);
  - `brand` ← `legacy.brand_direct` si no está vacío, si no
    `legacy.vendor`;
  - `category` ← `legacy.category_direct` (nunca `vendor`/`shopify_tags`/
    `product_type`);
  - `technical_product`/`size`/`units`/`materials`/`presentation`/
    `metadata_retrieved_at`/`metadata_status`/`metadata_error` ←
    mismo campo del legacy, sin transformar;
  - `metadata_http_status` ← `legacy.html_http_status`;
  - `metadata_parser_version` ← `legacy.metadata_parser_version`
    (preserva literalmente el valor histórico `1.0.0`, no la constante
    actual del módulo).
  - `product_url`, `page_title`, `description_detail` del legacy
    **nunca** se usan como sustitutos de columnas canónicas.
- `normalize_legacy_offline(joined_rows, legacy_by_id)`: aplica el
  mapeo a las 655 filas, deteniéndose si a alguna fila del join le
  falta contraparte legacy (nunca inventa la fila).
- `run_offline_normalize(config, legacy_source_path)`: orquesta join +
  normalización + escritura atómica del CSV final y su resumen JSON.
  Cero llamadas de red — reutiliza únicamente `read_csv_rows`/
  `atomic_write_csv`/`atomic_write_json` de `src/scraper_extraction.py`.
- CLI: `--offline-normalize --legacy-source <ruta>` (mutuamente
  exclusivo con `--smoke-test`/`--full-run`).

### Tests focalizados — 28/28, `.venv` 3.11.9 / pytest 9.1.1

```
.\.venv\Scripts\python.exe -m pytest tests/test_enrich_amarket_metadata.py -v
```

28 passed, exit code 0 (19 anteriores del join/schema en vivo + 9
nuevos de la normalización offline: mapeo `brand`/`category`,
preservación de provenance canónica, cobertura completa legacy
obligatoria, esquema de salida exacto, y un test que hace fallar la
red si `run_offline_normalize` la tocara).

### Ejecución real (sin red) sobre los 655 activos

```
.\.venv\Scripts\python.exe -m src.data.enrich_amarket_metadata --offline-normalize --legacy-source <ruta temporal del CSV legacy>
```

Resumen — **calculado, no hardcodeado**, y coincide exactamente con lo
esperado:

```
OUTPUT_ROWS        = 655
UNIQUE_SOURCE_IDS   = 655
METADATA_OK         = 652
METADATA_FAILED     = 3
HTTP_200            = 652
HTTP_404            = 3
BRAND_FOUND         = 652
CATEGORY_FOUND      = 0
PRESENTATION_FOUND  = 650
FAILED_SKUS         = 309971879203, 309974700139, 7899620665101
                      (exactamente el conjunto esperado — sin SKU
                      adicionales ni faltantes)
```

Validación adicional sobre el CSV final:
- Encabezado == exactamente las 20 columnas de
  `11_ENRICHED_MANIFEST_SCHEMA.csv`.
- `product_name`/`description`/`product_page_url`/`image_url`/`sha256`
  de las 655 filas coinciden byte a byte con
  `data/manifests/source_assets_full.csv` (0 discrepancias) — provenance
  nunca reconstruida, siempre del manifest canónico.
- `data/manifests/source_assets_enriched.csv` (repo) reemplazado por
  este resultado — 655 filas, esquema conforme, `metadata_parser_version=1.0.0`
  reflejando honestamente que la observación de red original se hizo
  bajo esa versión del parser, no bajo la actual.

### Suite completa, mismo entorno

```
.\.venv\Scripts\python.exe -m pytest tests/ -q
```

**228 passed, 1 failed**, exit code 1 — no se declara PASS con código
de salida distinto de 0. El único fallo sigue siendo
`test_scraper_extraction.py::TestScraperExtraction::test_s02_incomplete_config_fails`,
preexistente y no relacionado (encoding de `subprocess` en Windows,
PR #31). El incremento 219→228 corresponde a los 9 tests nuevos de
normalización offline de esta sección.

### `git diff --check`

Exit code 0 — sin errores de espacio en blanco en el diff.

### `FROZEN_FILES_CHANGED`

`git diff -- docs/governance/` contra `origin/main` → sin salida.
**FROZEN_FILES_CHANGED = 0** en todos los commits de esta rama.

## Estado final

```
P2_002 = RESOLVED
SCHEMA_NORMALIZATION = OFFLINE_DETERMINISTIC
NETWORK_OBSERVATIONS_SOURCE = PRIOR_SUCCESSFUL_655_ROW_RUN
LIVE_POST_MERGE_RUN = BLOCKED_AT_438_BY_HTTP_429 (registro histórico conservado, no reintentado)
CLOUDFLARE_BYPASS = NO
DATA_INVENTED = NO
P2_METADATA = READY_FOR_CONDITIONAL_INDEPENDENT_REVIEW
```

"Condicional" porque el reprocesamiento de red real bajo el esquema
corregido no llegó a completarse en vivo (bloqueado por rate-limit);
los valores de `brand`/`technical_product`/`size`/`units`/`materials`/
`presentation`/`category`/`metadata_*` provienen de una corrida real
completa pero hecha bajo el esquema anterior, reetiquetados aquí sin
recalcular ni volver a observar nada. Identidad, provenance
(`product_name`/`description`/`product_page_url`/`image_url`/`sha256`)
y split están verificados contra el manifest canónico independiente,
no contra el CSV legacy.

No autoaprobado. No mergeado. `docs/governance/03_PHASE2/*` no fue
modificado en ningún commit de esta rama.
