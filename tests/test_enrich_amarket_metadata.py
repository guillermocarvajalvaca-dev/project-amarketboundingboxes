"""Tests para src/data/enrich_amarket_metadata.py (P2-003/P2-004).

No dependen de red real: todas las peticiones HTTP se interceptan
reemplazando ``src.scraper_extraction.request_with_retries``.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

import pytest

from src.data.enrich_amarket_metadata import (
    ENRICHED_MANIFEST_FIELDS,
    build_product_urls,
    enrich_row,
    extract_direct_labels,
    load_input_rows,
    run,
)
from src.scraper_extraction import PoliteHttpClient, atomic_write_csv, read_csv_rows


class _FakeHTTPResponse:
    """Respuesta HTTP mínima compatible con PoliteHttpClient.get."""

    def __init__(self, body, content_type, status=200):
        self.status = status
        self.body = body
        self.headers = {"Content-Type": content_type}

    def getcode(self):
        return self.status

    def read(self, amount=None):
        if amount is None:
            return self.body
        return self.body[:amount]

    def close(self):
        pass


def _patch_network(responses):
    """Reemplaza request_with_retries por un doble fiel a `responses`.

    `responses` mapea url -> (status, content_type, body) o url -> Exception.
    Cualquier URL no declarada hace fallar el test explícitamente, lo que
    sirve también para probar que nunca se pide una imagen (cdn/shop).
    """

    def _side_effect(url, **kwargs):
        if url not in responses:
            raise AssertionError(f"URL inesperada solicitada en el test: {url}")

        outcome = responses[url]

        if isinstance(outcome, Exception):
            raise outcome

        status, content_type, body = outcome
        return _FakeHTTPResponse(body, content_type, status)

    return patch(
        "src.scraper_extraction.request_with_retries",
        side_effect=_side_effect,
    )


def _client():
    return PoliteHttpClient(
        {
            "http": {
                "user_agent": "PROJECT_AMARKETBOUNDINGBOXES/1.0 test",
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            }
        }
    )


def _product_html(extra_span=""):
    return (
        "<html><head>"
        "<title>Producto Test — Amarket</title>"
        '<meta property="og:title" content="Producto Test">'
        '<meta property="og:description" content="Descripcion de prueba">'
        "</head><body>"
        f"{extra_span}"
        "</body></html>"
    ).encode("utf-8")


def _product_js(vendor="MARCA X", tags=None, product_type=""):
    if tags is None:
        tags = ["Lo Nuevo", "Ofertas"]

    payload = {
        "id": 1,
        "title": "Producto Test",
        "vendor": vendor,
        "type": product_type,
        "tags": tags,
        "description": "<p>Descripcion Shopify</p>",
    }
    return json.dumps(payload).encode("utf-8")


def _row(sku_id="1234567890123", source_asset_id="asset-1"):
    return {
        "sku_id": sku_id,
        "source_asset_id": source_asset_id,
        "duplicate_group_id": "dup-1",
        "class_id": "0",
        "split": "train",
        "image_path": f"images/train/{source_asset_id}.jpg",
        "label_path": f"labels/train/{source_asset_id}.txt",
        "source_sha256": "a" * 64,
        "box_algorithm_version": "pixel-extremes-v1",
        "parameters_hash": "b" * 64,
    }


def test_build_product_urls_uses_contractual_pattern():
    html_url, js_url = build_product_urls("7773401007956")

    assert html_url == "https://amarket.com.bo/products/7773401007956"
    assert js_url == "https://amarket.com.bo/products/7773401007956.js"


def test_html_with_direct_category_is_captured():
    span = (
        '<span class="product-stock-level__availability">'
        "Categoría:</span>Alimentos"
    )
    html_text = _product_html(span).decode("utf-8")

    labels = extract_direct_labels(html_text)

    assert labels["category_direct"] == "Alimentos"


def test_html_without_category_leaves_it_empty():
    html_text = _product_html().decode("utf-8")

    labels = extract_direct_labels(html_text)

    assert "category_direct" not in labels


def test_shopify_tags_never_become_category():
    """shopify_tags/product_type promocionales NUNCA deben poblar category_direct."""

    row = _row(sku_id="1111111111111", source_asset_id="asset-tags")
    html_url, js_url = build_product_urls(row["sku_id"])

    responses = {
        html_url: (200, "text/html", _product_html()),
        js_url: (
            200,
            "application/json",
            _product_js(
                vendor="ACME",
                tags=["Lo Nuevo", "Ofertas", "STICKERS1"],
                product_type="Bebidas",
            ),
        ),
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), row)

    assert enriched["shopify_tags"] == "Lo Nuevo; Ofertas; STICKERS1"
    assert enriched["product_type"] == "Bebidas"
    assert enriched["category_direct"] == ""
    assert enriched["category_status"] == "NOT_FOUND"
    assert enriched["vendor"] == "ACME"


def test_html_404_marks_not_found_and_metadata_failed():
    row = _row(sku_id="4040404040404", source_asset_id="asset-404")
    html_url, js_url = build_product_urls(row["sku_id"])

    not_found = HTTPError(html_url, 404, "Not Found", hdrs=None, fp=None)
    js_not_found = HTTPError(js_url, 404, "Not Found", hdrs=None, fp=None)

    responses = {
        html_url: not_found,
        js_url: js_not_found,
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), row)

    assert enriched["html_status"] == "NOT_FOUND"
    assert enriched["html_http_status"] == "404"
    assert enriched["js_status"] == "NOT_FOUND"
    assert enriched["category_status"] == "UNKNOWN"
    assert enriched["metadata_status"] == "FAILED"
    assert "HTML HTTP 404" in enriched["metadata_error"]
    assert "JS HTTP 404" in enriched["metadata_error"]


def test_identity_fields_are_preserved_unchanged():
    row = _row(sku_id="9998887776665", source_asset_id="asset-identity")
    html_url, js_url = build_product_urls(row["sku_id"])

    responses = {
        html_url: (200, "text/html", _product_html()),
        js_url: (200, "application/json", _product_js()),
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), row)

    for field in (
        "sku_id",
        "source_asset_id",
        "split",
        "source_sha256",
        "image_path",
        "label_path",
    ):
        assert enriched[field] == row[field]


def test_enrich_row_never_requests_image_paths():
    """El enriquecedor no debe abrir ninguna URL de imagen (cdn/shop)."""

    row = _row(sku_id="5551112223334", source_asset_id="asset-no-image")
    html_url, js_url = build_product_urls(row["sku_id"])

    html_with_image_link = (
        "<html><head>"
        '<meta property="og:title" content="Producto Test">'
        '<meta property="og:image:secure_url" '
        'content="https://amarket.com.bo/cdn/shop/files/producto.jpg">'
        "</head><body></body></html>"
    ).encode("utf-8")

    responses = {
        html_url: (200, "text/html", html_with_image_link),
        js_url: (200, "application/json", _product_js()),
    }

    with _patch_network(responses):
        # Si el código intentara descargar la imagen, _patch_network
        # lanzaría AssertionError por URL no declarada.
        enrich_row(_client(), row)


def test_run_output_row_count_equals_input_and_no_duplicates(tmp_path=None):
    rows = [
        _row(sku_id="1000000000001", source_asset_id="asset-a"),
        _row(sku_id="1000000000002", source_asset_id="asset-b"),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        splits_path = root / "splits.csv"
        output_path = root / "enriched.csv"
        summary_path = root / "summary.json"

        atomic_write_csv(
            splits_path,
            rows,
            list(rows[0].keys()),
        )

        config = {
            "input": {"splits_manifest": str(splits_path)},
            "http": {
                "user_agent": "PROJECT_AMARKETBOUNDINGBOXES/1.0 test",
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            },
            "outputs": {
                "enriched_manifest": str(output_path),
                "summary": str(summary_path),
            },
        }

        responses = {}
        for row in rows:
            html_url, js_url = build_product_urls(row["sku_id"])
            responses[html_url] = (200, "text/html", _product_html())
            responses[js_url] = (200, "application/json", _product_js())

        with _patch_network(responses):
            summary = run(config, limit=None)

        output_rows = read_csv_rows(output_path)

        assert len(output_rows) == len(rows)
        assert summary["processed"] == len(rows)
        assert summary["source_rows"] == len(rows)

        source_asset_ids = [row["source_asset_id"] for row in output_rows]
        assert len(source_asset_ids) == len(set(source_asset_ids))

        assert list(output_rows[0].keys()) == ENRICHED_MANIFEST_FIELDS


def test_load_input_rows_rejects_duplicate_source_asset_id():
    rows = [
        _row(sku_id="2000000000001", source_asset_id="dup-asset"),
        _row(sku_id="2000000000002", source_asset_id="dup-asset"),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        splits_path = Path(temp_dir) / "splits.csv"

        atomic_write_csv(splits_path, rows, list(rows[0].keys()))

        with pytest.raises(ValueError, match="duplicado"):
            load_input_rows(splits_path)


def test_load_input_rows_rejects_missing_identity_field():
    rows = [_row(sku_id="", source_asset_id="asset-missing-sku")]

    with tempfile.TemporaryDirectory() as temp_dir:
        splits_path = Path(temp_dir) / "splits.csv"

        atomic_write_csv(splits_path, rows, list(rows[0].keys()))

        with pytest.raises(ValueError, match="vac"):
            load_input_rows(splits_path)
