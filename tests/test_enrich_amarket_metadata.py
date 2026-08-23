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
    enrich_row,
    extract_direct_labels,
    js_url_for,
    join_canonical_with_splits,
    load_canonical_source,
    run,
)
from src.scraper_extraction import PoliteHttpClient, atomic_write_csv, read_csv_rows

GOVERNING_SCHEMA_COLUMNS = [
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


ROBOTS_ALLOW_ALL = b"User-agent: *\nAllow: /\n"


def _patch_network(responses, robots_url="https://amarket.com.bo/robots.txt"):
    """Reemplaza request_with_retries por un doble fiel a `responses`.

    Agrega automáticamente una respuesta permisiva de robots.txt salvo que
    ya venga declarada explícitamente en `responses`.
    """

    full_responses = dict(responses)
    full_responses.setdefault(robots_url, (200, "text/plain", ROBOTS_ALLOW_ALL))

    def _side_effect(url, **kwargs):
        if url not in full_responses:
            raise AssertionError(f"URL inesperada solicitada en el test: {url}")

        outcome = full_responses[url]

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


def _canonical_row(sku_id="1234567890123", source_asset_id="asset-1", sha256="a" * 64):
    return {
        "source_asset_id": source_asset_id,
        "sku_id": sku_id,
        "product_name": f"Producto {sku_id}",
        "description": f"Descripcion original {sku_id}",
        "source_name": "AMARKET",
        "product_page_url": f"https://amarket.com.bo/collections/lo-nuevo/products/{sku_id}",
        "image_url": f"https://amarket.com.bo/cdn/shop/files/{sku_id}_1200x1200.jpg?v=123",
        "retrieved_at": "2026-08-21T02:04:01+00:00",
        "retrieval_run_id": "run-1",
        "http_status": "200",
        "content_type": "image/jpeg",
        "scraper_version": "1.0.0",
        "sha256": sha256,
        "duplicate_group_id": sha256,
        "width_px": "1200",
        "height_px": "1200",
        "image_mode": "RGB",
        "background_mode": "UNIFORM_RGB",
        "rights_status": "REDISTRIBUTION_PROHIBITED",
        "acceptance_status": "ACCEPTED",
        "rejection_reason": "",
        "local_path": f"data\\raw\\amarket_full\\{sku_id}.jpg",
    }


def _split_row(sku_id="1234567890123", source_asset_id="asset-1", sha256="a" * 64, split="train"):
    return {
        "sku_id": sku_id,
        "source_asset_id": source_asset_id,
        "duplicate_group_id": sha256,
        "class_id": "0",
        "split": split,
        "image_path": f"images/{split}/{source_asset_id}.jpg",
        "label_path": f"labels/{split}/{source_asset_id}.txt",
        "source_sha256": sha256,
        "box_algorithm_version": "pixel-extremes-v1",
        "parameters_hash": "b" * 64,
    }


def _joined_row(sku_id="1234567890123", source_asset_id="asset-1", sha256="a" * 64, split="train"):
    canonical = _canonical_row(sku_id, source_asset_id, sha256)
    return {
        "source_asset_id": source_asset_id,
        "sku_id": sku_id,
        "product_name": canonical["product_name"],
        "description": canonical["description"],
        "product_page_url": canonical["product_page_url"],
        "image_url": canonical["image_url"],
        "sha256": sha256,
        "split": split,
    }


# --- Esquema gobernante ---


def test_output_fields_match_governing_schema_exactly():
    assert ENRICHED_MANIFEST_FIELDS == GOVERNING_SCHEMA_COLUMNS


def test_run_writes_exact_governing_header(tmp_path=None):
    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        canonical_row = _canonical_row()
        split_row = _split_row()

        canonical_path = root / "source_assets_full.csv"
        splits_path = root / "splits.csv"
        output_path = root / "enriched.csv"
        summary_path = root / "summary.json"

        atomic_write_csv(canonical_path, [canonical_row], list(canonical_row.keys()))
        atomic_write_csv(splits_path, [split_row], list(split_row.keys()))

        config = {
            "input": {
                "canonical_source_manifest": str(canonical_path),
                "splits_manifest": str(splits_path),
            },
            "http": {
                "user_agent": "PROJECT_AMARKETBOUNDINGBOXES/1.0 test",
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            },
            "outputs": {"enriched_manifest": str(output_path), "summary": str(summary_path)},
        }

        responses = {
            canonical_row["product_page_url"]: (200, "text/html", _product_html()),
            js_url_for(canonical_row["product_page_url"]): (200, "application/json", _product_js()),
        }

        with _patch_network(responses):
            run(config, limit=None)

        with output_path.open("r", encoding="utf-8", newline="") as file:
            header = file.readline().strip().split(",")

        assert header == GOVERNING_SCHEMA_COLUMNS


# --- Join canónico + splits ---


def test_join_requires_exact_655_style_correspondence():
    canonical_by_id = {"asset-1": _canonical_row(source_asset_id="asset-1")}
    split_rows = [_split_row(source_asset_id="asset-1"), _split_row(source_asset_id="asset-2", sku_id="999")]

    with pytest.raises(ValueError, match="join incompleto"):
        join_canonical_with_splits(canonical_by_id, split_rows)


def test_join_fails_if_canonical_has_unused_row():
    canonical_by_id = {
        "asset-1": _canonical_row(source_asset_id="asset-1"),
        "asset-2": _canonical_row(source_asset_id="asset-2", sku_id="999"),
    }
    split_rows = [_split_row(source_asset_id="asset-1")]

    with pytest.raises(ValueError, match="join incompleto"):
        join_canonical_with_splits(canonical_by_id, split_rows)


def test_join_fails_on_sku_id_mismatch():
    canonical_by_id = {"asset-1": _canonical_row(source_asset_id="asset-1", sku_id="111")}
    split_rows = [_split_row(source_asset_id="asset-1", sku_id="222")]

    with pytest.raises(ValueError, match="sku_id no coincide"):
        join_canonical_with_splits(canonical_by_id, split_rows)


def test_join_fails_on_sha256_mismatch():
    canonical_by_id = {"asset-1": _canonical_row(source_asset_id="asset-1", sha256="a" * 64)}
    split_rows = [_split_row(source_asset_id="asset-1", sha256="b" * 64)]

    with pytest.raises(ValueError, match="sha256 no coincide"):
        join_canonical_with_splits(canonical_by_id, split_rows)


def test_join_preserves_canonical_provenance_verbatim():
    canonical_by_id = {"asset-1": _canonical_row(source_asset_id="asset-1")}
    split_rows = [_split_row(source_asset_id="asset-1")]

    joined = join_canonical_with_splits(canonical_by_id, split_rows)

    assert len(joined) == 1
    row = joined[0]
    assert row["product_name"] == canonical_by_id["asset-1"]["product_name"]
    assert row["description"] == canonical_by_id["asset-1"]["description"]
    assert row["product_page_url"] == canonical_by_id["asset-1"]["product_page_url"]
    assert row["image_url"] == canonical_by_id["asset-1"]["image_url"]
    assert row["sha256"] == canonical_by_id["asset-1"]["sha256"]
    assert row["split"] == "train"


def test_load_canonical_source_rejects_duplicate_source_asset_id():
    rows = [_canonical_row(source_asset_id="dup"), _canonical_row(source_asset_id="dup", sku_id="999")]

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "source_assets_full.csv"
        atomic_write_csv(path, rows, list(rows[0].keys()))

        with pytest.raises(ValueError, match="duplicado"):
            load_canonical_source(path)


def test_load_canonical_source_rejects_missing_provenance_field():
    row = _canonical_row()
    row["image_url"] = ""

    with tempfile.TemporaryDirectory() as temp_dir:
        path = Path(temp_dir) / "source_assets_full.csv"
        atomic_write_csv(path, [row], list(row.keys()))

        with pytest.raises(ValueError, match="image_url"):
            load_canonical_source(path)


# --- Provenance NUNCA reconstruida desde observación en vivo ---


def test_canonical_provenance_is_never_overwritten_by_live_fetch():
    """Aunque el fetch en vivo trajera un og:title/og:image distinto, la
    salida debe conservar product_name/description/image_url del manifest
    canónico, no lo observado en la página."""

    joined = _joined_row()

    live_html_with_different_title = (
        "<html><head>"
        '<meta property="og:title" content="TITULO COMPLETAMENTE DISTINTO">'
        '<meta property="og:image:secure_url" '
        'content="https://amarket.com.bo/cdn/shop/files/otra-imagen-distinta.jpg">'
        "</head><body></body></html>"
    ).encode("utf-8")

    responses = {
        joined["product_page_url"]: (200, "text/html", live_html_with_different_title),
        js_url_for(joined["product_page_url"]): (200, "application/json", _product_js()),
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), joined)

    assert enriched["product_name"] == joined["product_name"]
    assert enriched["description"] == joined["description"]
    assert enriched["image_url"] == joined["image_url"]
    assert enriched["product_page_url"] == joined["product_page_url"]
    assert enriched["sha256"] == joined["sha256"]


def test_js_url_derivation_preserves_collection_prefix():
    url = "https://amarket.com.bo/collections/lo-nuevo/products/7773401007956"
    assert js_url_for(url) == "https://amarket.com.bo/collections/lo-nuevo/products/7773401007956.js"


# --- Extracción directa (nunca inferida) ---


def test_html_with_direct_category_is_captured():
    span = '<span class="product-stock-level__availability">Categoría:</span>Alimentos'
    html_text = _product_html(span).decode("utf-8")

    labels = extract_direct_labels(html_text)

    assert labels["category"] == "Alimentos"


def test_html_without_category_leaves_it_empty():
    html_text = _product_html().decode("utf-8")

    labels = extract_direct_labels(html_text)

    assert "category" not in labels


def test_shopify_tags_never_become_category_and_vendor_becomes_brand():
    """shopify_tags/product_type promocionales NUNCA deben poblar `category`;
    `vendor` sí puede poblar `brand` cuando no hay etiqueta "Marca:" directa."""

    joined = _joined_row(sku_id="1111111111111", source_asset_id="asset-tags")

    responses = {
        joined["product_page_url"]: (200, "text/html", _product_html()),
        js_url_for(joined["product_page_url"]): (
            200,
            "application/json",
            _product_js(vendor="ACME", tags=["Lo Nuevo", "Ofertas", "STICKERS1"], product_type="Bebidas"),
        ),
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), joined)

    assert enriched["category"] == ""
    assert enriched["brand"] == "ACME"


def test_explicit_brand_label_wins_over_vendor():
    joined = _joined_row(sku_id="2222222222222", source_asset_id="asset-brand-label")

    span = '<span class="product-stock-level__availability">Marca:</span>Etiqueta Directa'

    responses = {
        joined["product_page_url"]: (200, "text/html", _product_html(span)),
        js_url_for(joined["product_page_url"]): (200, "application/json", _product_js(vendor="VENDOR JSON")),
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), joined)

    assert enriched["brand"] == "Etiqueta Directa"


# --- Errores de red ---


def test_html_404_marks_metadata_failed():
    joined = _joined_row(sku_id="4040404040404", source_asset_id="asset-404")

    not_found_html = HTTPError(joined["product_page_url"], 404, "Not Found", hdrs=None, fp=None)
    not_found_js = HTTPError(js_url_for(joined["product_page_url"]), 404, "Not Found", hdrs=None, fp=None)

    responses = {
        joined["product_page_url"]: not_found_html,
        js_url_for(joined["product_page_url"]): not_found_js,
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), joined)

    assert enriched["metadata_http_status"] == "404"
    assert enriched["metadata_status"] == "FAILED"
    assert "HTML HTTP 404" in enriched["metadata_error"]
    assert "JS HTTP 404" in enriched["metadata_error"]
    # provenance sigue preservada incluso ante fallo de red
    assert enriched["product_name"] == joined["product_name"]
    assert enriched["image_url"] == joined["image_url"]


# --- Identidad preservada end-to-end ---


def test_identity_fields_preserved_through_full_pipeline():
    joined = _joined_row(sku_id="9998887776665", source_asset_id="asset-identity", split="val")

    responses = {
        joined["product_page_url"]: (200, "text/html", _product_html()),
        js_url_for(joined["product_page_url"]): (200, "application/json", _product_js()),
    }

    with _patch_network(responses):
        enriched = enrich_row(_client(), joined)

    for field in ("sku_id", "source_asset_id", "split", "sha256", "product_page_url", "image_url"):
        assert enriched[field] == joined[field]


def test_enrich_row_never_requests_image_cdn_urls():
    """El enriquecedor no debe abrir ninguna URL de imagen (cdn/shop),
    incluso si la página HTML declara una como og:image."""

    joined = _joined_row(sku_id="5551112223334", source_asset_id="asset-no-image")

    html_with_image_link = (
        "<html><head>"
        '<meta property="og:title" content="Producto Test">'
        '<meta property="og:image:secure_url" '
        'content="https://amarket.com.bo/cdn/shop/files/producto.jpg">'
        "</head><body></body></html>"
    ).encode("utf-8")

    responses = {
        joined["product_page_url"]: (200, "text/html", html_with_image_link),
        js_url_for(joined["product_page_url"]): (200, "application/json", _product_js()),
    }

    with _patch_network(responses):
        # Si el código intentara descargar la imagen, _patch_network
        # lanzaría AssertionError por URL no declarada.
        enrich_row(_client(), joined)


# --- Ejecución completa (run) ---


def test_run_output_row_count_equals_source_and_no_duplicates():
    canonical_rows = [
        _canonical_row(sku_id="1000000000001", source_asset_id="asset-a", sha256="a" * 64),
        _canonical_row(sku_id="1000000000002", source_asset_id="asset-b", sha256="b" * 64),
    ]
    split_rows = [
        _split_row(sku_id="1000000000001", source_asset_id="asset-a", sha256="a" * 64),
        _split_row(sku_id="1000000000002", source_asset_id="asset-b", sha256="b" * 64),
    ]

    with tempfile.TemporaryDirectory() as temp_dir:
        root = Path(temp_dir)

        canonical_path = root / "source_assets_full.csv"
        splits_path = root / "splits.csv"
        output_path = root / "enriched.csv"
        summary_path = root / "summary.json"

        atomic_write_csv(canonical_path, canonical_rows, list(canonical_rows[0].keys()))
        atomic_write_csv(splits_path, split_rows, list(split_rows[0].keys()))

        config = {
            "input": {
                "canonical_source_manifest": str(canonical_path),
                "splits_manifest": str(splits_path),
            },
            "http": {
                "user_agent": "PROJECT_AMARKETBOUNDINGBOXES/1.0 test",
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            },
            "outputs": {"enriched_manifest": str(output_path), "summary": str(summary_path)},
        }

        responses = {}
        for row in canonical_rows:
            responses[row["product_page_url"]] = (200, "text/html", _product_html())
            responses[js_url_for(row["product_page_url"])] = (200, "application/json", _product_js())

        with _patch_network(responses):
            summary = run(config, limit=None)

        output_rows = read_csv_rows(output_path)

        assert len(output_rows) == len(canonical_rows)
        assert summary["processed"] == len(canonical_rows)
        assert summary["source_rows"] == len(canonical_rows)

        source_asset_ids = [row["source_asset_id"] for row in output_rows]
        assert len(source_asset_ids) == len(set(source_asset_ids))

        assert list(output_rows[0].keys()) == GOVERNING_SCHEMA_COLUMNS


if __name__ == "__main__":
    import sys

    sys.exit(pytest.main([__file__, "-v"]))
