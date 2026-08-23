"""Enriquecedor reproducible de metadata AMARKET — Phase 2 (P2-003/P2-004).

Reprocesa los 655 SKU canónicos consultando su ficha pública
(``/products/{sku}``) y el endpoint Shopify (``/products/{sku}.js``),
sin volver a descargar imágenes. Implementación conforme a
docs/governance/03_PHASE2/05_METADATA_ENRICHMENT_CONTRACT_v1_0_0.md.

Regla dura: ``shopify_tags``/``product_type`` NUNCA se copian a
``category_direct``. La categoría solo se registra si aparece en un
campo etiquetado explícitamente en la página del producto.
"""

import argparse
import json
import re
import time
import unicodedata

from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote

import yaml

from src.scraper_extraction import (
    PoliteHttpClient,
    ProductParser,
    atomic_write_csv,
    atomic_write_json,
    read_csv_rows,
)


METADATA_PARSER_VERSION = "1.0.0"

BASE_URL = "https://amarket.com.bo"

PRESERVED_SPLIT_FIELDS = [
    "sku_id",
    "source_asset_id",
    "duplicate_group_id",
    "class_id",
    "split",
    "image_path",
    "label_path",
    "source_sha256",
    "box_algorithm_version",
    "parameters_hash",
]

ENRICHMENT_FIELDS = [
    "product_url",
    "html_status",
    "html_http_status",
    "js_status",
    "js_http_status",
    "page_title",
    "vendor",
    "shopify_tags",
    "product_type",
    "brand_direct",
    "technical_product",
    "size",
    "units",
    "materials",
    "presentation",
    "category_direct",
    "category_status",
    "description_detail",
    "metadata_status",
    "metadata_error",
    "metadata_retrieved_at",
    "metadata_parser_version",
]

ENRICHED_MANIFEST_FIELDS = PRESERVED_SPLIT_FIELDS + ENRICHMENT_FIELDS

# Etiquetas directas observadas en la ficha de producto (span
# "product-stock-level__availability") mapeadas a columnas del
# contrato. La clave está normalizada: minúsculas, sin acentos, sin
# los dos puntos finales.
DIRECT_LABEL_MAP = {
    "categoria": "category_direct",
    "marca": "brand_direct",
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

DESCRIPTION_TRUNCATE_LENGTH = 600


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

    Nunca infiere: solo captura lo que el HTML declara explícitamente
    bajo una etiqueta reconocida. Etiquetas no reconocidas se ignoran.
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


def build_product_urls(sku_id):
    """Construye las URLs HTML y Shopify JSON contractuales para un SKU."""

    slug = quote(str(sku_id).strip(), safe="")

    return (
        f"{BASE_URL}/products/{slug}",
        f"{BASE_URL}/products/{slug}.js",
    )


def _truncate_description(text, limit=DESCRIPTION_TRUNCATE_LENGTH):
    if len(text) <= limit:
        return text

    return text[:limit].rstrip() + "…"


def _strip_html(fragment):
    without_tags = re.sub(r"<[^>]+>", " ", fragment or "")
    return " ".join(unescape(without_tags).split())


def fetch_html_metadata(client, html_url):
    """Consulta la ficha HTML y extrae los campos observables.

    Devuelve un dict con status/http_status/error y los campos
    extraídos (vacíos si la página no los declara).
    """

    result = {
        "html_status": "",
        "html_http_status": "",
        "page_title": "",
        "description_meta": "",
        "direct_labels": {},
        "error": "",
    }

    try:
        response = client.get(html_url)

    except HTTPError as error:
        result["html_http_status"] = str(error.code)
        result["html_status"] = (
            "NOT_FOUND" if error.code == 404 else "HTTP_ERROR"
        )
        result["error"] = f"HTML HTTP {error.code}"
        return result

    except URLError as error:
        result["html_status"] = "NETWORK_ERROR"
        result["error"] = f"HTML network error: {error.reason}"
        return result

    result["html_http_status"] = str(response["status"])

    if response["status"] != 200:
        result["html_status"] = "HTTP_ERROR"
        result["error"] = f"HTML HTTP {response['status']}"
        return result

    try:
        html_text = response["body"].decode("utf-8", errors="replace")

        parser = ProductParser()
        parser.feed(html_text)

        page_title = (
            parser.meta.get("og:title") or parser.title or ""
        ).strip()

        description_meta = (
            parser.meta.get("og:description")
            or parser.meta.get("description")
            or ""
        ).strip()

        result["page_title"] = page_title
        result["description_meta"] = description_meta
        result["direct_labels"] = extract_direct_labels(html_text)
        result["html_status"] = "OK"

    except Exception as error:  # noqa: BLE001 - registrado, no silencioso
        result["html_status"] = "PARSE_ERROR"
        result["error"] = f"HTML parse error: {error}"

    return result


def fetch_js_metadata(client, js_url):
    """Consulta el endpoint Shopify .js y extrae vendor/tags/type/description."""

    result = {
        "js_status": "",
        "js_http_status": "",
        "vendor": "",
        "shopify_tags": "",
        "product_type": "",
        "description_js": "",
        "error": "",
    }

    try:
        response = client.get(js_url)

    except HTTPError as error:
        result["js_http_status"] = str(error.code)
        result["js_status"] = (
            "NOT_FOUND" if error.code == 404 else "HTTP_ERROR"
        )
        result["error"] = f"JS HTTP {error.code}"
        return result

    except URLError as error:
        result["js_status"] = "NETWORK_ERROR"
        result["error"] = f"JS network error: {error.reason}"
        return result

    result["js_http_status"] = str(response["status"])

    if response["status"] != 200:
        result["js_status"] = "HTTP_ERROR"
        result["error"] = f"JS HTTP {response['status']}"
        return result

    try:
        payload = json.loads(response["body"].decode("utf-8", errors="replace"))

        tags = payload.get("tags") or []

        if isinstance(tags, str):
            tags = [tag.strip() for tag in tags.split(",") if tag.strip()]

        result["vendor"] = (payload.get("vendor") or "").strip()
        result["shopify_tags"] = "; ".join(tags)
        result["product_type"] = (payload.get("type") or "").strip()
        result["description_js"] = _strip_html(payload.get("description", ""))
        result["js_status"] = "OK"

    except (ValueError, TypeError, AttributeError) as error:
        result["js_status"] = "PARSE_ERROR"
        result["error"] = f"JS parse error: {error}"

    return result


def enrich_row(client, row):
    """Enriquece una fila de splits.csv sin alterar su identidad original.

    shopify_tags/product_type jamás se copian a category_direct: la
    categoría solo se llena si la ficha HTML la declara explícitamente
    bajo una etiqueta reconocida (ver DIRECT_LABEL_MAP).
    """

    sku_id = row["sku_id"]
    html_url, js_url = build_product_urls(sku_id)

    html_result = fetch_html_metadata(client, html_url)
    js_result = fetch_js_metadata(client, js_url)

    direct_labels = html_result["direct_labels"]

    description_detail = html_result["description_meta"]

    if not description_detail and js_result["description_js"]:
        description_detail = _truncate_description(js_result["description_js"])

    if html_result["html_status"] == "OK":
        if direct_labels.get("category_direct"):
            category_status = "FOUND"
        else:
            category_status = "NOT_FOUND"
    else:
        category_status = "UNKNOWN"

    metadata_status = "OK" if html_result["html_status"] == "OK" else "FAILED"

    errors = [message for message in (html_result["error"], js_result["error"]) if message]
    metadata_error = "; ".join(errors)

    enriched = {field: row.get(field, "") for field in PRESERVED_SPLIT_FIELDS}

    enriched.update(
        {
            "product_url": html_url,
            "html_status": html_result["html_status"],
            "html_http_status": html_result["html_http_status"],
            "js_status": js_result["js_status"],
            "js_http_status": js_result["js_http_status"],
            "page_title": html_result["page_title"],
            "vendor": js_result["vendor"],
            "shopify_tags": js_result["shopify_tags"],
            "product_type": js_result["product_type"],
            "brand_direct": direct_labels.get("brand_direct", ""),
            "technical_product": direct_labels.get("technical_product", ""),
            "size": direct_labels.get("size", ""),
            "units": direct_labels.get("units", ""),
            "materials": direct_labels.get("materials", ""),
            "presentation": direct_labels.get("presentation", ""),
            "category_direct": direct_labels.get("category_direct", ""),
            "category_status": category_status,
            "description_detail": description_detail,
            "metadata_status": metadata_status,
            "metadata_error": metadata_error,
            "metadata_retrieved_at": datetime.now(timezone.utc).isoformat(),
            "metadata_parser_version": METADATA_PARSER_VERSION,
        }
    )

    return enriched


def load_input_rows(splits_path):
    """Carga y valida el manifest fuente de 655 SKU canónicos."""

    rows = read_csv_rows(splits_path)

    if not rows:
        raise ValueError(f"No se pudieron leer filas de {splits_path}")

    seen_asset_ids = set()

    for row in rows:
        for field in ("sku_id", "source_asset_id", "split", "source_sha256", "image_path", "label_path"):
            if not row.get(field):
                raise ValueError(
                    f"Fila con '{field}' vacío en {splits_path}: {row}"
                )

        asset_id = row["source_asset_id"]

        if asset_id in seen_asset_ids:
            raise ValueError(
                f"source_asset_id duplicado en el manifest fuente: {asset_id}"
            )

        seen_asset_ids.add(asset_id)

    return rows


def summarize(enriched_rows, source_row_count):
    """Construye el resumen de conteos realmente observados."""

    def count_ok(field):
        return sum(1 for row in enriched_rows if row[field] == "OK")

    def count_nonempty(field):
        return sum(1 for row in enriched_rows if row[field])

    failures = [
        {
            "sku_id": row["sku_id"],
            "source_asset_id": row["source_asset_id"],
            "html_status": row["html_status"],
            "html_http_status": row["html_http_status"],
            "js_status": row["js_status"],
            "js_http_status": row["js_http_status"],
            "metadata_error": row["metadata_error"],
        }
        for row in enriched_rows
        if row["metadata_status"] != "OK"
    ]

    return {
        "source_rows": source_row_count,
        "processed": len(enriched_rows),
        "html_ok": count_ok("html_status"),
        "js_ok": count_ok("js_status"),
        "vendor_found": count_nonempty("vendor"),
        "tags_found": count_nonempty("shopify_tags"),
        "direct_category_found": count_nonempty("category_direct"),
        "failures": failures,
        "failure_count": len(failures),
        "metadata_parser_version": METADATA_PARSER_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


def run(config, limit):
    """Ejecuta el enriquecimiento sobre el manifest fuente."""

    splits_path = Path(config["input"]["splits_manifest"])

    rows = load_input_rows(splits_path)

    selected_rows = rows[:limit] if limit is not None else rows

    client = PoliteHttpClient({"http": config["http"]})

    enriched_rows = []

    for index, row in enumerate(selected_rows, start=1):
        print(f"[{index}/{len(selected_rows)}] SKU={row['sku_id']}")

        enriched = enrich_row(client, row)
        enriched_rows.append(enriched)

        print(
            f"    html={enriched['html_status']}"
            f" js={enriched['js_status']}"
            f" category={enriched['category_status']}"
        )

    output_path = Path(config["outputs"]["enriched_manifest"])
    summary_path = Path(config["outputs"]["summary"])

    atomic_write_csv(output_path, enriched_rows, ENRICHED_MANIFEST_FIELDS)

    summary = summarize(enriched_rows, len(rows))

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

    return config


def parse_args():
    parser = argparse.ArgumentParser(
        description=(
            "Enriquecimiento reproducible de metadata AMARKET (P2-003/P2-004): "
            "reprocesa las fichas de producto sin descargar imágenes."
        )
    )

    parser.add_argument(
        "--config",
        default="configs/metadata_enrichment.yaml",
        help="Ruta al archivo YAML de configuración.",
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
        help="Procesa las 655 filas del manifest fuente completo.",
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

    print("Configuración válida.")
    print("Manifest fuente:", config["input"]["splits_manifest"])
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
