# Metadata Enrichment Contract — Phase 2 v1.0.0

## Purpose

Enrich existing AMARKET records from their public product pages without redownloading product images.

## Input

Canonical source manifest containing at minimum:

- `source_asset_id`;
- `sku_id`;
- `product_page_url`;
- existing provenance/hash fields.

## Output

Write a **new** enriched manifest. Never overwrite the original in place.

Preserve every original column and add:

- `brand`;
- `technical_product`;
- `size`;
- `units`;
- `materials`;
- `presentation`;
- `category`;
- `metadata_retrieved_at`;
- `metadata_http_status`;
- `metadata_parser_version`;
- `metadata_status`;
- `metadata_error`.

Optional if directly observed:

- `collection_origin`.

## Extraction rule

Values must come from the product page HTML/structured content. Do not infer category from product name, SKU or neighboring products.

The direct POC demonstrated page text fields including:

- SKU;
- Producto;
- Tamaño;
- Unidades;
- Materiales;
- Presentación;
- Categoría.

## Network behavior

- product pages only;
- no image download;
- declared User-Agent;
- polite delay;
- bounded retry/timeout;
- robots/access restrictions respected;
- one page failure does not erase successful rows.

## Missing fields

Missing values remain empty/null and `metadata_status` records the outcome. No invented fallback value.

## Acceptance

- all canonical product URLs attempted exactly once per governed run, except bounded retries;
- row identity preserved;
- output row count equals input row count;
- no duplicate `source_asset_id` introduced;
- category coverage count reported, not guessed;
- failure list emitted;
- no image bytes downloaded by this enrichment path.
