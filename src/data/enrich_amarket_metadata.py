"""Enriquecedor reproducible de metadata AMARKET — Phase 2 (P2-003/P2-004).

Une el manifest canónico de 655 activos (`data/manifests/source_assets_full.csv`,
que trae `product_name`/`description`/`product_page_url`/`image_url`/`sha256`
de la corrida SCR-001 --full-crawl) con `data/manifests/splits.csv` (que trae
`split`) por `source_asset_id`, y reprocesa cada `product_page_url` (+ su
variante Shopify `.js`) para agregar `brand`, `technical_product`, `size`,
`units`, `materials`, `presentation`, `category` y los campos `metadata_*`,
sin volver a descargar imágenes. Esquema de salida exacto según
docs/governance/03_PHASE2/11_ENRICHED_MANIFEST_SCHEMA.csv.

Reglas duras:
- `product_name`, `description`, `product_page_url`, `image_url`, `sha256`
  se preservan literalmente del manifest canónico — NUNCA se reconstruyen,
  infieren ni reemplazan por lo observado en vivo durante el reprocesamiento.
- `category` solo se llena si la página declara un campo etiquetado
  explícito; el vendor/tags/product_type de Shopify NUNCA se copian ahí.
"""

import argparse
import json
import re
import unicodedata

from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit

import yaml

from src.scraper_extraction import (
    PoliteHttpClient,
    ProductParser,
    atomic_write_csv,
    atomic_write_json,
    check_robots,
    read_csv_rows,
)


METADATA_PARSER_VERSION = "2.0.0"

# Columnas preservadas literalmente del manifest canónico
# (data/manifests/source_assets_full.csv), nunca reconstruidas.
CANONICAL_PROVENANCE_FIELDS = [
    "product_name",
    "description",
    "product_page_url",
    "image_url",
    "sha256",
]

# Esquema exacto de docs/governance/03_PHASE2/11_ENRICHED_MANIFEST_SCHEMA.csv
ENRICHED_MANIFEST_FIELDS = [
    "source_asset_id",
    "sku_id",
    "product_name",
    "description",
    "brand",
    "technical_product",
    "size",
    "units",
    "materials",
    "presentation",
    "category",
    "product_page_url",
    "image_url",
    "sha256",
    "split",
    "metadata_retrieved_at",
    "metadata_http_status",
    "metadata_parser_version",
    "metadata_status",
    "metadata_error",
]

# Etiquetas directas observadas en la ficha de producto (span
# "product-stock-level__availability") mapeadas a columnas del contrato.
# La clave está normalizada: minúsculas, sin acentos, sin ":" final.
DIRECT_LABEL_MAP = {
    "categoria": "category",
    "marca": "brand",
    "producto": "technical_product",
    "tamano": "size",
    "unidades": "units",
    "material": "materials",
    "materiales": "materials",
    "presentacion": "presentation",
    "unidad de venta": "presentation",
}

DIRECT_LABEL_PATTERN = re.compile(
    r'<span class="product-stock-level__availability">\s*'
    r"([^<]+?)\s*</span>([^<]*)"
)


def _normalize_label(raw_label):
    """Normaliza una etiqueta observada para hacer match con DIRECT_LABEL_MAP."""

    stripped = raw_label.strip().rstrip(":").strip()
    decomposed = unicodedata.normalize("NFKD", stripped)
    without_accents = "".join(
        ch for ch in decomposed if not unicodedata.combining(ch)
    )
    return without_accents.lower()


def extract_direct_labels(html_text):
    """Extrae pares etiqueta/valor observados directamente en la ficha.

    Nunca infiere: solo captura lo que el HTML declara explícitamente bajo
    una etiqueta reconocida. `category` solo se llena aquí, nunca desde
    shopify_tags/product_type/vendor.
    """

    found = {}

    for raw_label, raw_value in DIRECT_LABEL_PATTERN.findall(html_text):
        field = DIRECT_LABEL_MAP.get(_normalize_label(raw_label))

        if not field:
            continue

        value = " ".join(raw_value.split())

        if value and field not in found:
            found[field] = value

    return found


def js_url_for(product_page_url):
    """Deriva la URL Shopify .js a partir de la product_page_url canónica.

    Válido para cualquier prefijo de colección: Shopify sirve el mismo
    recurso .js sin importar si la ruta viene prefijada por /collections/X/.
    Verificado en vivo antes de implementar (mismo tamaño de respuesta que
    /products/{sku}.js).
    """

    parsed = urlsplit(product_page_url)
    return urlunsplit(
        (parsed.scheme, parsed.netloc, parsed.path + ".js", "", "")
    )


def _strip_html(fragment):
    without_tags = re.sub(r"<[^>]+>", " ", fragment or "")
    return " ".join(unescape(without_tags).split())


def fetch_html_fields(client, product_page_url):
    """Consulta la ficha HTML y extrae los campos directos observables."""

    result = {
        "html_http_status": "",
        "direct_labels": {},
        "error": "",
    }

    try:
        response = client.get(product_page_url)

    except HTTPError as error:
        result["html_http_status"] = str(error.code)
        result["error"] = f"HTML HTTP {error.code}"
        return result

    except URLError as error:
        result["error"] = f"HTML network error: {error.reason}"
        return result

    result["html_http_status"] = str(response["status"])

    if response["status"] != 200:
        result["error"] = f"HTML HTTP {response['status']}"
        return result

    try:
        html_text = response["body"].decode("utf-8", errors="replace")
        result["direct_labels"] = extract_direct_labels(html_text)

    except Exception as error:  # noqa: BLE001 - registrado, no silencioso
        result["error"] = f"HTML parse error: {error}"

    return result


def fetch_js_fields(client, js_url):
    """Consulta el endpoint Shopify .js para vendor (candidato a brand).

    vendor/tags/product_type NUNCA pueblan `category` — solo se usa
    `vendor` como candidato de `brand` cuando la ficha no trae una
    etiqueta "Marca:" explícita.
    """

    result = {"vendor": "", "error": ""}

    try:
        response = client.get(js_url)

    except HTTPError as error:
        result["error"] = f"JS HTTP {error.code}"
        return result

    except URLError as error:
        result["error"] = f"JS network error: {error.reason}"
        return result

    if response["status"] != 200:
        result["error"] = f"JS HTTP {response['status']}"
        return result

    try:
        payload = json.loads(response["body"].decode("utf-8", errors="replace"))
        result["vendor"] = (payload.get("vendor") or "").strip()

    except (ValueError, TypeError, AttributeError) as error:
        result["error"] = f"JS parse error: {error}"

    return result


def enrich_row(client, joined_row):
    """Enriquece una fila ya unida (canónica + split) sin tocar provenance.

    `product_name`/`description`/`product_page_url`/`image_url`/`sha256`
    se copian tal cual de `joined_row` (vienen del manifest canónico) —
    esta función solo agrega brand/technical_product/size/units/materials/
    presentation/category/metadata_*.
    """

    product_page_url = joined_row["product_page_url"]
    js_url = js_url_for(product_page_url)

    html_result = fetch_html_fields(client, product_page_url)
    js_result = fetch_js_fields(client, js_url)

    direct_labels = html_result["direct_labels"]

    brand = direct_labels.get("brand") or js_result["vendor"]

    metadata_status = "OK" if not html_result["error"] else "FAILED"

    errors = [message for message in (html_result["error"], js_result["error"]) if message]
    metadata_error = "; ".join(errors)

    enriched = {field: joined_row[field] for field in ENRICHED_MANIFEST_FIELDS if field in joined_row}

    enriched.update(
        {
            "brand": brand,
            "technical_product": direct_labels.get("technical_product", ""),
            "size": direct_labels.get("size", ""),
            "units": direct_labels.get("units", ""),
            "materials": direct_labels.get("materials", ""),
            "presentation": direct_labels.get("presentation", ""),
            "category": direct_labels.get("category", ""),
            "metadata_retrieved_at": datetime.now(timezone.utc).isoformat(),
            "metadata_http_status": html_result["html_http_status"],
            "metadata_parser_version": METADATA_PARSER_VERSION,
            "metadata_status": metadata_status,
            "metadata_error": metadata_error,
        }
    )

    return {field: enriched.get(field, "") for field in ENRICHED_MANIFEST_FIELDS}


def load_canonical_source(path):
    """Carga el manifest canónico de 655 activos (source_assets_full.csv)."""

    rows = read_csv_rows(path)

    if not rows:
        raise ValueError(f"No se pudieron leer filas del manifest canónico: {path}")

    by_id = {}

    for row in rows:
        asset_id = row.get("source_asset_id")

        if not asset_id:
            raise ValueError(f"Fila sin source_asset_id en el manifest canónico: {row}")

        if asset_id in by_id:
            raise ValueError(
                f"source_asset_id duplicado en el manifest canónico: {asset_id}"
            )

        for field in CANONICAL_PROVENANCE_FIELDS:
            if not row.get(field):
                raise ValueError(
                    f"Fila con '{field}' vacío en el manifest canónico "
                    f"(source_asset_id={asset_id})"
                )

        by_id[asset_id] = row

    return by_id


def join_canonical_with_splits(canonical_by_id, split_rows):
    """Une el manifest canónico con splits.csv por source_asset_id.

    Exige correspondencia EXACTA 655/655: cada fila de splits.csv debe
    tener un match único en el manifest canónico, y viceversa (ninguna
    fila del manifest canónico queda sin usar). sku_id y sha256 se
    cruzan-validan entre ambas fuentes; cualquier discrepancia detiene
    la ejecución en vez de elegir un valor silenciosamente.
    """

    split_ids = {row["source_asset_id"] for row in split_rows}
    canonical_ids = set(canonical_by_id.keys())

    missing_in_canonical = split_ids - canonical_ids
    unused_in_canonical = canonical_ids - split_ids

    if missing_in_canonical:
        raise ValueError(
            "P2-002 join incompleto: "
            f"{len(missing_in_canonical)} source_asset_id de splits.csv "
            f"no están en el manifest canónico: {sorted(missing_in_canonical)[:5]}..."
        )

    if unused_in_canonical:
        raise ValueError(
            "P2-002 join incompleto: "
            f"{len(unused_in_canonical)} source_asset_id del manifest canónico "
            f"no están en splits.csv: {sorted(unused_in_canonical)[:5]}..."
        )

    joined_rows = []

    for split_row in split_rows:
        asset_id = split_row["source_asset_id"]
        canonical_row = canonical_by_id[asset_id]

        if canonical_row["sku_id"] != split_row["sku_id"]:
            raise ValueError(
                f"sku_id no coincide entre manifest canónico y splits.csv "
                f"para source_asset_id={asset_id}: "
                f"{canonical_row['sku_id']!r} != {split_row['sku_id']!r}"
            )

        if canonical_row["sha256"] != split_row["source_sha256"]:
            raise ValueError(
                f"sha256 no coincide entre manifest canónico y splits.csv "
                f"para source_asset_id={asset_id}: "
                f"{canonical_row['sha256']!r} != {split_row['source_sha256']!r}"
            )

        joined_rows.append(
            {
                "source_asset_id": asset_id,
                "sku_id": split_row["sku_id"],
                "product_name": canonical_row["product_name"],
                "description": canonical_row["description"],
                "product_page_url": canonical_row["product_page_url"],
                "image_url": canonical_row["image_url"],
                "sha256": canonical_row["sha256"],
                "split": split_row["split"],
            }
        )

    return joined_rows


def summarize(enriched_rows, source_row_count):
    """Construye el resumen de conteos realmente observados."""

    def count_ok_status():
        return sum(1 for row in enriched_rows if row["metadata_status"] == "OK")

    def count_nonempty(field):
        return sum(1 for row in enriched_rows if row[field])

    failures = [
        {
            "sku_id": row["sku_id"],
            "source_asset_id": row["source_asset_id"],
            "metadata_http_status": row["metadata_http_status"],
            "metadata_status": row["metadata_status"],
            "metadata_error": row["metadata_error"],
        }
        for row in enriched_rows
        if row["metadata_status"] != "OK"
    ]

    return {
        "source_rows": source_row_count,
        "processed": len(enriched_rows),
        "html_ok": count_ok_status(),
        "brand_found": count_nonempty("brand"),
        "category_found": count_nonempty("category"),
        "presentation_found": count_nonempty("presentation"),
        "failures": failures,
        "failure_count": len(failures),
        "metadata_parser_version": METADATA_PARSER_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run(config, limit):
    """Ejecuta el join + enriquecimiento sobre el manifest fuente."""

    canonical_path = Path(config["input"]["canonical_source_manifest"])
    splits_path = Path(config["input"]["splits_manifest"])

    canonical_by_id = load_canonical_source(canonical_path)
    split_rows = read_csv_rows(splits_path)

    if not split_rows:
        raise ValueError(f"No se pudieron leer filas de {splits_path}")

    joined_rows = join_canonical_with_splits(canonical_by_id, split_rows)

    selected_rows = joined_rows[:limit] if limit is not None else joined_rows

    client = PoliteHttpClient({"http": config["http"]})

    robots_parsers = {}
    enriched_rows = []

    for index, joined_row in enumerate(selected_rows, start=1):
        print(f"[{index}/{len(selected_rows)}] SKU={joined_row['sku_id']}")

        parsed = urlsplit(joined_row["product_page_url"])
        robots_base = f"{parsed.scheme}://{parsed.netloc}"

        if robots_base not in robots_parsers:
            robots_parsers[robots_base] = check_robots(client, robots_base, robots_base)

        robots_parser = robots_parsers[robots_base]

        if not robots_parser.can_fetch(client.user_agent, joined_row["product_page_url"]):
            raise PermissionError(
                f"robots.txt no permite acceder a: {joined_row['product_page_url']}"
            )

        enriched = enrich_row(client, joined_row)
        enriched_rows.append(enriched)

        print(
            f"    metadata_status={enriched['metadata_status']}"
            f" brand={'SET' if enriched['brand'] else '-'}"
            f" category={'SET' if enriched['category'] else '-'}"
        )

    output_path = Path(config["outputs"]["enriched_manifest"])
    summary_path = Path(config["outputs"]["summary"])

    atomic_write_csv(output_path, enriched_rows, ENRICHED_MANIFEST_FIELDS)

    summary = summarize(enriched_rows, len(joined_rows))

    atomic_write_json(summary_path, summary)

    print("Resumen:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    return summary


def load_config(config_path):
    path = Path(config_path)

    if not path.is_file():
        raise FileNotFoundError(f"No existe el archivo de configuración: {config_path}")

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    for section in ("input", "http", "outputs"):
        if section not in config:
            raise ValueError(f"Falta la sección obligatoria '{section}' en la configuración.")

    for key in ("canonical_source_manifest", "splits_manifest"):
        if key not in config["input"]:
            raise ValueError(f"Falta 'input.{key}' en la configuración.")

    return config


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Enriquecimiento reproducible de metadata AMARKET (P2-003/P2-004): "
            "une el manifest canónico con splits.csv y reprocesa cada ficha "
            "de producto sin descargar imágenes."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/metadata_enrichment.yaml",
        help="Ruta al archivo YAML de configuración.",
    )

    parser.add_argument(
        "--canonical-source",
        default=None,
        help="Sobrescribe input.canonical_source_manifest del YAML.",
    )

    mode_group = parser.add_mutually_exclusive_group()

    mode_group.add_argument(
        "--smoke-test",
        action="store_true",
        help="Procesa solo limits.smoke_products filas, para validar el pipeline.",
    )

    mode_group.add_argument(
        "--full-run",
        action="store_true",
        help="Procesa las 655 filas del join canónico completo.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Sobrescribe el número de filas a procesar (requiere --smoke-test).",
    )

    return parser.parse_args()


def main():
    args = parse_args()

    if args.limit is not None and not args.smoke_test:
        raise ValueError("--limit solo es válido junto con --smoke-test.")

    config = load_config(args.config)

    if args.canonical_source is not None:
        config["input"]["canonical_source_manifest"] = args.canonical_source

    print("Configuración válida.")
    print("Manifest canónico:", config["input"]["canonical_source_manifest"])
    print("Manifest de splits:", config["input"]["splits_manifest"])
    print("Manifest enriquecido:", config["outputs"]["enriched_manifest"])

    if args.full_run:
        run(config, limit=None)
        return

    if not args.smoke_test:
        print("No se accede a red sin --smoke-test ni --full-run.")
        return

    limit = args.limit if args.limit is not None else int(config["limits"]["smoke_products"])

    if limit < 1:
        raise ValueError("El límite debe ser mayor o igual a 1.")

    run(config, limit=limit)


if __name__ == "__main__":
    main()
