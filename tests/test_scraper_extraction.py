import contextlib
import csv
import io
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from PIL import Image

from src.scraper_extraction import (
    MANIFEST_FIELDS,
    PoliteHttpClient,
    atomic_write_csv,
    atomic_write_json,
    calculate_sha256,
    check_robots,
    discover_all_product_urls,
    extract_next_collection_url,
    duplicate_group_id,
    load_config,
    main,
    normalize_product_urls,
    read_csv_rows,
    reconcile_outputs,
    request_with_retries,
    run_full_crawl,
    run_smoke_test,
    save_image_idempotently,
    source_asset_id,
    source_asset_identity_key,
    validate_image_bytes,
    validate_image_content_type,
)


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


def _make_test_image_bytes(color):
    """Genera bytes PNG válidos y de fondo uniforme para fixtures."""

    buffer = io.BytesIO()

    Image.new(
        "RGB",
        (12, 12),
        color=color,
    ).save(
        buffer,
        format="PNG",
    )

    return buffer.getvalue()


def _build_amarket_fixture(product_count):
    """Construye colección, fichas e imágenes falsas de Amarket.

    Cada producto aparece dos veces en la colección (con y sin barra
    final) para probar que la canonicalización/deduplicación produce
    exactamente `product_count` URLs únicas.
    """

    collection_url = "https://amarket.com.bo/collections/lo-nuevo"
    robots_url = "https://amarket.com.bo/robots.txt"

    anchors = "".join(
        f'<a href="/products/producto-{index}">Producto {index}</a>\n'
        f'<a href="/products/producto-{index}/">Producto {index} dup</a>\n'
        for index in range(1, product_count + 1)
    )

    collection_html = f"<html><body>{anchors}</body></html>".encode(
        "utf-8"
    )

    responses = {
        robots_url: (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        collection_url: (200, "text/html", collection_html),
    }

    expected_urls = []

    for index in range(1, product_count + 1):
        product_url = (
            f"https://amarket.com.bo/products/producto-{index}"
        )
        image_url = (
            "https://amarket.com.bo/cdn/shop/files/"
            f"producto-{index}.png"
        )

        product_html = (
            "<html><head>"
            f"<title>Producto {index} — Amarket</title>"
            f'<meta property="og:title" content="Producto {index}">'
            '<meta property="og:description" '
            f'content="Descripcion {index}">'
            '<meta property="og:image:secure_url" '
            f'content="{image_url}">'
            "</head><body></body></html>"
        ).encode("utf-8")

        image_bytes = _make_test_image_bytes(
            (10 + index, 10 + index, 10 + index)
        )

        responses[product_url] = (200, "text/html", product_html)
        responses[image_url] = (200, "image/png", image_bytes)

        expected_urls.append(product_url)

    return collection_url, responses, sorted(expected_urls)


def _patch_amarket_network(responses):
    """Reemplaza request_with_retries por un doble fiel a las fixtures."""

    def _side_effect(url, **kwargs):
        if url not in responses:
            raise AssertionError(
                f"URL inesperada solicitada en el test: {url}"
            )

        status, content_type, body = responses[url]

        return _FakeHTTPResponse(body, content_type, status)

    return patch(
        "src.scraper_extraction.request_with_retries",
        side_effect=_side_effect,
    )


def _build_paginated_collection_fixture():
    """Colección de 3 páginas con productos repetidos entre páginas.

    Página 1: A, B, link a página 2.
    Página 2: B repetido, C, link a página 3.
    Página 3: D, sin siguiente.
    Resultado esperado: 3 páginas, productos únicos A, B, C, D.
    """

    base_url = "https://amarket.com.bo/collections/lo-nuevo"
    page2_url = f"{base_url}?page=2"
    page3_url = f"{base_url}?page=3"
    robots_url = "https://amarket.com.bo/robots.txt"

    page1_html = (
        "<html><body>"
        '<a href="/products/producto-a">Producto A</a>'
        '<a href="/products/producto-b">Producto B</a>'
        f'<a href="{page2_url}">Siguiente</a>'
        "</body></html>"
    ).encode("utf-8")

    page2_html = (
        "<html><body>"
        '<a href="/products/producto-b">Producto B repetido</a>'
        '<a href="/products/producto-c">Producto C</a>'
        f'<a href="{base_url}">Anterior</a>'
        f'<a href="{page3_url}">Siguiente</a>'
        "</body></html>"
    ).encode("utf-8")

    page3_html = (
        "<html><body>"
        '<a href="/products/producto-d">Producto D</a>'
        f'<a href="{page2_url}">Anterior</a>'
        "</body></html>"
    ).encode("utf-8")

    responses = {
        robots_url: (200, "text/plain", b"User-agent: *\nAllow: /\n"),
        base_url: (200, "text/html", page1_html),
        page2_url: (200, "text/html", page2_html),
        page3_url: (200, "text/html", page3_html),
    }

    expected_urls = sorted(
        f"https://amarket.com.bo/products/producto-{letter}"
        for letter in ("a", "b", "c", "d")
    )

    return base_url, responses, expected_urls


def _build_fixture_config(root, collection_url, extra_limits=None):
    """Config mínima de test apuntando a un directorio temporal."""

    limits = {
        "max_images_per_product": 1,
        "max_image_bytes": 5_242_880,
    }

    if extra_limits:
        limits.update(extra_limits)

    return {
        "source": {
            "name": "AMARKET",
            "collection_url": collection_url,
        },
        "http": {
            "user_agent": "PROJECT_AMARKETBOUNDINGBOXES/1.0 test",
            "delay_seconds": 0,
            "timeout_seconds": 20,
            "max_retries": 3,
            "backoff_seconds": 0,
        },
        "limits": limits,
        "outputs": {
            "images_dir": str(root / "images"),
            "manifest": str(root / "manifest.csv"),
            "rejects": str(root / "rejects.csv"),
            "summary": str(root / "summary.json"),
        },
    }


class TestScraperExtraction(unittest.TestCase):

    def test_s01_help_returns_zero(self):
        """S01: --help debe terminar con código 0."""

        result = subprocess.run(
            [
                sys.executable,
                "src/scraper_extraction.py",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "--config",
            result.stdout,
        )

        self.assertIn(
            "--limit",
            result.stdout,
        )

        self.assertIn(
            "--smoke-test",
            result.stdout,
        )

    def test_s02_incomplete_config_fails(self):
        """S02: configuración incompleta debe fallar."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir)
                / "incomplete.yaml"
            )

            config_path.write_text(
                "source:\n"
                "  name: AMARKET\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    "src/scraper_extraction.py",
                    "--config",
                    str(config_path),
                ],
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "Falta la sección obligatoria",
            result.stderr,
        )

    def test_config_requires_max_image_bytes(self):
        """La configuración debe declarar el límite de imagen."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir)
                / "missing_max_image_bytes.yaml"
            )

            config_path.write_text(
                "source:\n"
                "  name: AMARKET\n"
                "  collection_url: "
                "https://amarket.com.bo/collections/lo-nuevo\n"
                "http:\n"
                "  user_agent: "
                "PROJECT_AMARKETBOUNDINGBOXES/1.0 "
                "academic-smoke-test\n"
                "  delay_seconds: 1.0\n"
                "  timeout_seconds: 20\n"
                "  max_retries: 3\n"
                "  backoff_seconds: 2.0\n"
                "limits:\n"
                "  max_products: 3\n"
                "  max_images_per_product: 1\n"
                "outputs:\n"
                "  images_dir: data/raw/amarket\n"
                "  manifest: "
                "data/manifests/source_assets.csv\n"
                "  rejects: "
                "data/manifests/scrape_rejections.csv\n"
                "  summary: "
                "outputs/scrape_summary.json\n",
                encoding="utf-8",
            )

            with self.assertRaises(ValueError) as context:
                load_config(config_path)

            self.assertIn(
                "limits.max_image_bytes",
                str(context.exception),
            )

    def test_image_download_size_limit_is_enforced(self):
        """La descarga de imagen debe respetar max_bytes."""

        config = {
            "http": {
                "user_agent": (
                    "PROJECT_AMARKETBOUNDINGBOXES/1.0 "
                    "academic-smoke-test"
                ),
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            }
        }

        client = PoliteHttpClient(config)

        class FakeResponse:
            def __init__(
                self,
                body,
                content_length=None,
            ):
                self.status = 200
                self.body = body
                self.read_called = False
                self.closed = False
                self.headers = {
                    "Content-Type": "image/jpeg",
                }

                if content_length is not None:
                    self.headers[
                        "Content-Length"
                    ] = str(content_length)

            def getcode(self):
                return self.status

            def read(self, amount=None):
                self.read_called = True

                if amount is None:
                    return self.body

                return self.body[:amount]

            def close(self):
                self.closed = True

        declared_too_large = FakeResponse(
            body=b"x" * 10,
            content_length=5_242_881,
        )

        with patch(
            "src.scraper_extraction.request_with_retries",
            return_value=declared_too_large,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "REJECTED_MAX_BYTES",
            ):
                client.get(
                    "https://amarket.com.bo/test.jpg",
                    max_bytes=5_242_880,
                )

        self.assertFalse(
            declared_too_large.read_called
        )
        self.assertTrue(
            declared_too_large.closed
        )

        body_too_large = FakeResponse(
            body=b"x" * 5_242_881,
            content_length=None,
        )

        with patch(
            "src.scraper_extraction.request_with_retries",
            return_value=body_too_large,
        ):
            with self.assertRaisesRegex(
                RuntimeError,
                "REJECTED_MAX_BYTES",
            ):
                client.get(
                    "https://amarket.com.bo/test.jpg",
                    max_bytes=5_242_880,
                )

        self.assertTrue(
            body_too_large.read_called
        )
        self.assertTrue(
            body_too_large.closed
        )

        accepted = FakeResponse(
            body=b"x" * 100,
            content_length=100,
        )

        with patch(
            "src.scraper_extraction.request_with_retries",
            return_value=accepted,
        ):
            result = client.get(
                "https://amarket.com.bo/test.jpg",
                max_bytes=5_242_880,
            )

        self.assertEqual(
            len(result["body"]),
            100,
        )
        self.assertTrue(
            accepted.closed
        )

    def test_cli_output_paths_override_yaml(self):
        """CLI explícito debe tener prioridad sobre las rutas del YAML."""

        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                "src/scraper_extraction.py",
                "--config",
                "configs/data_sources.yaml",
                "--output-dir",
                "tmp/cli-images",
                "--manifest",
                "tmp/cli-manifest.csv",
            ],
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "Output dir: tmp/cli-images",
            result.stdout,
        )

        self.assertIn(
            "Manifest: tmp/cli-manifest.csv",
            result.stdout,
        )

    def test_s03_urls_are_unique_canonical_and_sorted(self):
        """S03: URLs duplicadas/desordenadas se normalizan."""

        urls = [
            "https://amarket.com.bo/products/z-producto?variant=123",
            "https://amarket.com.bo/products/a-producto/",
            "https://amarket.com.bo/products/z-producto",
            "https://amarket.com.bo/products/a-producto#foto",
        ]

        result = (
            normalize_product_urls(
                urls
            )
        )

        expected = [
            "https://amarket.com.bo/products/a-producto",
            "https://amarket.com.bo/products/z-producto",
        ]

        self.assertEqual(
            result,
            expected,
        )

    def test_s04_http_errors_have_bounded_retries(self):
        """S04: 404 no reintenta; 429/500 tienen retry acotado."""

        common_args = {
            "url": "https://amarket.com.bo/products/test",
            "user_agent": (
                "PROJECT_AMARKETBOUNDINGBOXES/1.0 "
                "academic-smoke-test"
            ),
            "timeout_seconds": 20,
            "max_retries": 3,
            "backoff_seconds": 0,
        }

        error_404 = HTTPError(
            common_args["url"],
            404,
            "Not Found",
            hdrs=None,
            fp=None,
        )

        with patch(
            "src.scraper_extraction.urlopen",
            side_effect=error_404,
        ) as mocked_urlopen:

            with self.assertRaises(
                HTTPError
            ):
                request_with_retries(
                    **common_args
                )

            self.assertEqual(
                mocked_urlopen.call_count,
                1,
            )

        for status_code in (
            429,
            500,
        ):
            error = HTTPError(
                common_args["url"],
                status_code,
                "Retryable error",
                hdrs=None,
                fp=None,
            )

            with patch(
                "src.scraper_extraction.urlopen",
                side_effect=error,
            ) as mocked_urlopen:

                with self.assertRaises(
                    HTTPError
                ):
                    request_with_retries(
                        **common_args
                    )

                self.assertEqual(
                    mocked_urlopen.call_count,
                    common_args["max_retries"] + 1,
                )

    def test_s05_non_image_mime_is_rejected(self):
        """S05: MIME que no sea imagen debe rechazarse."""

        with self.assertRaises(
            ValueError
        ):
            validate_image_content_type(
                "text/html"
            )

        with self.assertRaises(
            ValueError
        ):
            validate_image_content_type(
                "application/json"
            )

        self.assertEqual(
            validate_image_content_type(
                "image/jpeg"
            ),
            "image/jpeg",
        )

        self.assertEqual(
            validate_image_content_type(
                "image/png; charset=binary"
            ),
            "image/png",
        )

    def test_s06_corrupt_image_bytes_are_rejected(self):
        """S06: bytes corruptos deben rechazarse."""

        corrupt_bytes = (
            b"esto-no-es-una-imagen"
        )

        with self.assertRaises(
            ValueError
        ):
            validate_image_bytes(
                corrupt_bytes
            )

    def test_historical_manifest_identity_ignores_shopify_version_query(self):
        """Manifest histórico y URL Shopify nueva conservan identidad lógica."""

        sha256 = calculate_sha256(
            b"misma-imagen-binaria"
        )

        historical_key = source_asset_identity_key(
            "AMARKET",
            "https://amarket.com.bo/products/producto",
            (
                "https://amarket.com.bo/cdn/shop/files/"
                "producto.jpg?v=1786860434"
            ),
            sha256,
        )

        current_key = source_asset_identity_key(
            "AMARKET",
            "https://amarket.com.bo/products/producto",
            (
                "https://amarket.com.bo/cdn/shop/files/"
                "producto.jpg?v=1787033279"
            ),
            sha256,
        )

        self.assertEqual(
            historical_key,
            current_key,
        )

    def test_source_asset_id_ignores_shopify_version_query(self):
        """Misma imagen Shopify con distinto ?v= conserva identidad."""

        sha256 = calculate_sha256(
            b"misma-imagen-binaria"
        )

        first_id = source_asset_id(
            "AMARKET",
            "https://amarket.com.bo/products/producto",
            (
                "https://amarket.com.bo/cdn/shop/files/"
                "producto.jpg?v=1786860434"
            ),
            sha256,
        )

        second_id = source_asset_id(
            "AMARKET",
            "https://amarket.com.bo/products/producto",
            (
                "https://amarket.com.bo/cdn/shop/files/"
                "producto.jpg?v=1787033279"
            ),
            sha256,
        )

        self.assertEqual(
            first_id,
            second_id,
        )

    def test_s07_same_bytes_are_idempotent(self):
        """S07: mismos bytes no crean otra versión."""

        image_bytes = (
            b"contenido-controlado-de-prueba"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = (
                Path(temp_dir)
                / "producto.jpg"
            )

            first_result = (
                save_image_idempotently(
                    destination,
                    image_bytes,
                )
            )

            second_result = (
                save_image_idempotently(
                    destination,
                    image_bytes,
                )
            )

            self.assertEqual(
                first_result["status"],
                "created",
            )

            self.assertEqual(
                second_result["status"],
                "existing",
            )

            self.assertEqual(
                first_result["sha256"],
                second_result["sha256"],
            )

            self.assertEqual(
                destination.read_bytes(),
                image_bytes,
            )

    def test_s07_different_bytes_do_not_overwrite(self):
        """S07: bytes distintos no sobrescriben evidencia."""

        original_bytes = (
            b"version-original"
        )

        changed_bytes = (
            b"version-cambiada"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = (
                Path(temp_dir)
                / "producto.jpg"
            )

            save_image_idempotently(
                destination,
                original_bytes,
            )

            with self.assertRaises(
                FileExistsError
            ):
                save_image_idempotently(
                    destination,
                    changed_bytes,
                )

            self.assertEqual(
                destination.read_bytes(),
                original_bytes,
            )

    def test_atomic_image_write_cleans_temp_on_replace_failure(self):
        """Un fallo en os.replace no debe dejar destino parcial ni temporal."""

        image_bytes = b"contenido-atomico-de-prueba"

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = (
                Path(temp_dir)
                / "producto.jpg"
            )

            with patch(
                "src.scraper_extraction.os.replace",
                side_effect=OSError(
                    "fallo-controlado"
                ),
            ):
                with self.assertRaises(
                    OSError
                ):
                    save_image_idempotently(
                        destination,
                        image_bytes,
                    )

            self.assertFalse(
                destination.exists()
            )

            temp_files = list(
                Path(temp_dir).glob(
                    ".producto.jpg.*.tmp"
                )
            )

            self.assertEqual(
                temp_files,
                [],
            )

    def test_s08_same_bytes_different_urls_share_duplicate_group(self):
        """S08: mismos bytes desde URLs distintas comparten grupo."""

        url_a = (
            "https://amarket.com.bo/"
            "cdn/shop/files/producto-a.jpg"
        )

        url_b = (
            "https://amarket.com.bo/"
            "cdn/shop/files/copia-producto.jpg"
        )

        image_bytes = (
            b"misma-imagen-binaria"
        )

        group_a = (
            duplicate_group_id(
                image_bytes
            )
        )

        group_b = (
            duplicate_group_id(
                image_bytes
            )
        )

        self.assertNotEqual(
            url_a,
            url_b,
        )

        self.assertEqual(
            group_a,
            group_b,
        )

        self.assertEqual(
            group_a,
            calculate_sha256(
                image_bytes
            ),
        )

    def test_s09_resume_preserves_previous_success(self):
        """S09: reanudar conserva éxitos guardados."""

        first_bytes = (
            b"imagen-producto-uno"
        )

        second_bytes = (
            b"imagen-producto-dos"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(
                temp_dir
            )

            first_destination = (
                temp_path
                / "producto_1.jpg"
            )

            second_destination = (
                temp_path
                / "producto_2.jpg"
            )

            first_run = (
                save_image_idempotently(
                    first_destination,
                    first_bytes,
                )
            )

            self.assertEqual(
                first_run["status"],
                "created",
            )

            first_hash_before = (
                calculate_sha256(
                    first_destination.read_bytes()
                )
            )

            self.assertFalse(
                second_destination.exists()
            )

            resumed_first = (
                save_image_idempotently(
                    first_destination,
                    first_bytes,
                )
            )

            self.assertEqual(
                resumed_first["status"],
                "existing",
            )

            resumed_second = (
                save_image_idempotently(
                    second_destination,
                    second_bytes,
                )
            )

            self.assertEqual(
                resumed_second["status"],
                "created",
            )

            first_hash_after = (
                calculate_sha256(
                    first_destination.read_bytes()
                )
            )

            self.assertEqual(
                first_hash_before,
                first_hash_after,
            )

            self.assertEqual(
                first_destination.read_bytes(),
                first_bytes,
            )

            self.assertEqual(
                second_destination.read_bytes(),
                second_bytes,
            )

    def test_s10_files_rows_and_counts_reconcile(self):
        """S10: archivos, manifest, rechazos y resumen reconcilian."""

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(
                temp_dir
            )

            images_dir = (
                root
                / "data"
                / "raw"
                / "amarket"
            )

            manifest_path = (
                root
                / "data"
                / "manifests"
                / "source_assets.csv"
            )

            rejects_path = (
                root
                / "data"
                / "manifests"
                / "scrape_rejections.csv"
            )

            summary_path = (
                root
                / "outputs"
                / "scrape_summary.json"
            )

            image_a = (
                b"imagen-aceptada-a"
            )

            image_b = (
                b"imagen-aceptada-b"
            )

            path_a = (
                images_dir
                / "sku_a.jpg"
            )

            path_b = (
                images_dir
                / "sku_b.jpg"
            )

            save_image_idempotently(
                path_a,
                image_a,
            )

            save_image_idempotently(
                path_b,
                image_b,
            )

            manifest_rows = [
                {
                    "source_asset_id": "asset-a",
                    "sku_id": "sku-a",
                    "product_name": "Producto A",
                    "description": "",
                    "source_name": "AMARKET",
                    "product_page_url": (
                        "https://amarket.com.bo/products/a"
                    ),
                    "image_url": (
                        "https://amarket.com.bo/cdn/shop/files/a.jpg"
                    ),
                    "retrieved_at": "2026-08-16T12:00:00-04:00",
                    "retrieval_run_id": "run-test",
                    "http_status": "200",
                    "content_type": "image/jpeg",
                    "scraper_version": "1.0.0",
                    "sha256": calculate_sha256(
                        image_a
                    ),
                    "duplicate_group_id": (
                        duplicate_group_id(
                            image_a
                        )
                    ),
                    "width_px": "700",
                    "height_px": "700",
                    "image_mode": "RGB",
                    "background_mode": "UNIFORM_RGB",
                    "rights_status": "REDISTRIBUTION_PROHIBITED",
                    "acceptance_status": "ACCEPTED",
                    "rejection_reason": "",
                    "local_path": str(
                        path_a
                    ),
                },
                {
                    "source_asset_id": "asset-b",
                    "sku_id": "sku-b",
                    "product_name": "Producto B",
                    "description": "",
                    "source_name": "AMARKET",
                    "product_page_url": (
                        "https://amarket.com.bo/products/b"
                    ),
                    "image_url": (
                        "https://amarket.com.bo/cdn/shop/files/b.jpg"
                    ),
                    "retrieved_at": "2026-08-16T12:00:01-04:00",
                    "retrieval_run_id": "run-test",
                    "http_status": "200",
                    "content_type": "image/jpeg",
                    "scraper_version": "1.0.0",
                    "sha256": calculate_sha256(
                        image_b
                    ),
                    "duplicate_group_id": (
                        duplicate_group_id(
                            image_b
                        )
                    ),
                    "width_px": "700",
                    "height_px": "700",
                    "image_mode": "RGB",
                    "background_mode": "UNIFORM_RGB",
                    "rights_status": "REDISTRIBUTION_PROHIBITED",
                    "acceptance_status": "ACCEPTED",
                    "rejection_reason": "",
                    "local_path": str(
                        path_b
                    ),
                },
            ]

            rejection_rows = [
                {
                    "product_page_url": (
                        "https://amarket.com.bo/products/rejected"
                    ),
                    "image_url": "",
                    "rejection_reason": "MIME_NOT_IMAGE",
                }
            ]

            atomic_write_csv(
                manifest_path,
                manifest_rows,
                MANIFEST_FIELDS,
            )

            atomic_write_csv(
                rejects_path,
                rejection_rows,
                [
                    "product_page_url",
                    "image_url",
                    "rejection_reason",
                ],
            )

            summary = reconcile_outputs(
                manifest_rows,
                rejection_rows,
                images_dir,
            )

            atomic_write_json(
                summary_path,
                summary,
            )

            self.assertTrue(
                manifest_path.exists()
            )

            self.assertTrue(
                rejects_path.exists()
            )

            self.assertTrue(
                summary_path.exists()
            )

            with manifest_path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as file:
                manifest_file_rows = list(
                    csv.DictReader(
                        file
                    )
                )

            self.assertEqual(
                len(manifest_file_rows),
                2,
            )

            with rejects_path.open(
                "r",
                encoding="utf-8",
                newline="",
            ) as file:
                rejection_file_rows = list(
                    csv.DictReader(
                        file
                    )
                )

            self.assertEqual(
                len(rejection_file_rows),
                1,
            )

            with summary_path.open(
                "r",
                encoding="utf-8",
            ) as file:
                summary_file = json.load(
                    file
                )

            self.assertEqual(
                summary_file["attempted"],
                3,
            )

            self.assertEqual(
                summary_file["accepted"],
                2,
            )

            self.assertEqual(
                summary_file["rejected"],
                1,
            )

            self.assertEqual(
                summary_file["image_files"],
                2,
            )

            self.assertEqual(
                summary_file["manifest_rows"],
                2,
            )

            self.assertEqual(
                summary_file["rejection_rows"],
                1,
            )

    def test_reconcile_ignores_non_managed_auxiliary_file(self):
        """desktop.ini y otros archivos no-imagen no cuentan en image_files."""

        with tempfile.TemporaryDirectory() as temp_dir:
            images_dir = Path(temp_dir) / "images"

            image_bytes = b"imagen-administrada-unica"

            managed_path = images_dir / "sku_a.jpg"

            save_image_idempotently(
                managed_path,
                image_bytes,
            )

            auxiliary_path = images_dir / "desktop.ini"

            auxiliary_path.write_bytes(
                b"[.ShellClassInfo]\r\n"
                b"IconResource=C:\\Windows\\System32.dll,-235\r\n"
            )

            manifest_rows = [
                {
                    "source_asset_id": "asset-a",
                    "sha256": calculate_sha256(
                        image_bytes
                    ),
                    "local_path": str(managed_path),
                }
            ]

            summary = reconcile_outputs(
                manifest_rows,
                [],
                images_dir,
            )

            self.assertEqual(summary["accepted"], 1)
            self.assertEqual(summary["image_files"], 1)
            self.assertEqual(summary["manifest_rows"], 1)
            self.assertEqual(summary["rejected"], 0)
            self.assertEqual(summary["attempted"], 1)

    def test_reconcile_still_detects_orphan_managed_image(self):
        """Una imagen administrada huérfana real sigue provocando fallo."""

        with tempfile.TemporaryDirectory() as temp_dir:
            images_dir = Path(temp_dir) / "images"

            save_image_idempotently(
                images_dir / "sku_a.jpg",
                b"imagen-administrada-a",
            )

            save_image_idempotently(
                images_dir / "sku_b.jpg",
                b"imagen-administrada-b",
            )

            manifest_rows = [
                {
                    "source_asset_id": "asset-a",
                    "sha256": calculate_sha256(
                        b"imagen-administrada-a"
                    ),
                    "local_path": str(
                        images_dir / "sku_a.jpg"
                    ),
                }
            ]

            with self.assertRaisesRegex(
                ValueError,
                "Reconciliaci\u00f3n inv\u00e1lida",
            ):
                reconcile_outputs(
                    manifest_rows,
                    [],
                    images_dir,
                )

    def test_reconcile_still_detects_missing_managed_image(self):
        """Una fila aceptada sin imagen administrada real sigue fallando."""

        with tempfile.TemporaryDirectory() as temp_dir:
            images_dir = Path(temp_dir) / "images"

            images_dir.mkdir(parents=True)

            manifest_rows = [
                {
                    "source_asset_id": "asset-a",
                    "sha256": calculate_sha256(
                        b"imagen-nunca-guardada"
                    ),
                    "local_path": str(
                        images_dir / "sku_a.jpg"
                    ),
                }
            ]

            with self.assertRaisesRegex(
                ValueError,
                "Reconciliaci\u00f3n inv\u00e1lida",
            ):
                reconcile_outputs(
                    manifest_rows,
                    [],
                    images_dir,
                )

    def test_smoke_and_full_crawl_are_mutually_exclusive(self):
        """--smoke-test y --full-crawl no pueden usarse juntos."""

        result = subprocess.run(
            [
                sys.executable,
                "src/scraper_extraction.py",
                "--smoke-test",
                "--full-crawl",
            ],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "not allowed with argument",
            result.stderr,
        )

    def test_full_crawl_rejects_limit_argument(self):
        """--limit no debe aceptarse (ni ignorarse) junto a --full-crawl."""

        result = subprocess.run(
            [
                sys.executable,
                "src/scraper_extraction.py",
                "--full-crawl",
                "--limit",
                "5",
                "--config",
                "configs/data_sources_full.yaml",
            ],
            capture_output=True,
            text=True,
        )

        self.assertNotEqual(
            result.returncode,
            0,
        )

        self.assertIn(
            "--limit no es compatible con --full-crawl",
            result.stderr,
        )

    def test_no_mode_means_zero_network_access(self):
        """Sin --smoke-test ni --full-crawl no debe haber acceso a red."""

        def _fail_if_called(*args, **kwargs):
            raise AssertionError(
                "No debía llamarse a la red sin un modo explícito."
            )

        output = io.StringIO()

        with patch(
            "src.scraper_extraction.request_with_retries",
            side_effect=_fail_if_called,
        ):
            with patch(
                "sys.argv",
                ["src/scraper_extraction.py"],
            ):
                with contextlib.redirect_stdout(output):
                    main()

        self.assertIn(
            "No se accede a red",
            output.getvalue(),
        )

    def test_full_crawl_config_requires_rights_section(self):
        """La config full sin sección rights debe fallar antes de red."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir) / "full_no_rights.yaml"
            )

            config_path.write_text(
                "source:\n"
                "  name: AMARKET\n"
                "  collection_url: "
                "https://amarket.com.bo/collections/lo-nuevo\n"
                "http:\n"
                "  user_agent: "
                "PROJECT_AMARKETBOUNDINGBOXES/1.0 test\n"
                "  delay_seconds: 1.0\n"
                "  timeout_seconds: 20\n"
                "  max_retries: 3\n"
                "  backoff_seconds: 2.0\n"
                "limits:\n"
                "  max_images_per_product: 1\n"
                "  max_image_bytes: 5242880\n"
                "outputs:\n"
                "  images_dir: data/raw/amarket_full\n"
                "  manifest: "
                "data/manifests/source_assets_full.csv\n"
                "  rejects: "
                "data/manifests/scrape_rejections_full.csv\n"
                "  summary: outputs/scrape_summary_full.json\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "rights",
            ):
                load_config(
                    config_path,
                    mode="full",
                )

    def test_full_crawl_config_validated_before_any_network_access(self):
        """rights.status incorrecto falla antes de tocar la red."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir) / "full_bad_rights.yaml"
            )

            config_path.write_text(
                "source:\n"
                "  name: AMARKET\n"
                "  collection_url: "
                "https://amarket.com.bo/collections/lo-nuevo\n"
                "http:\n"
                "  user_agent: "
                "PROJECT_AMARKETBOUNDINGBOXES/1.0 test\n"
                "  delay_seconds: 1.0\n"
                "  timeout_seconds: 20\n"
                "  max_retries: 3\n"
                "  backoff_seconds: 2.0\n"
                "limits:\n"
                "  max_images_per_product: 1\n"
                "  max_image_bytes: 5242880\n"
                "rights:\n"
                "  status: NEGOTIABLE\n"
                "outputs:\n"
                "  images_dir: data/raw/amarket_full\n"
                "  manifest: "
                "data/manifests/source_assets_full.csv\n"
                "  rejects: "
                "data/manifests/scrape_rejections_full.csv\n"
                "  summary: outputs/scrape_summary_full.json\n",
                encoding="utf-8",
            )

            with patch(
                "src.scraper_extraction.request_with_retries",
                side_effect=AssertionError(
                    "No debía llamarse a la red."
                ),
            ) as mocked_request:
                with self.assertRaisesRegex(
                    ValueError,
                    "REDISTRIBUTION_PROHIBITED",
                ):
                    load_config(
                        config_path,
                        mode="full",
                    )

            self.assertEqual(
                mocked_request.call_count,
                0,
            )

    def test_full_crawl_config_rejects_oversized_image_limit(self):
        """max_image_bytes > 5 MiB debe fallar en full crawl."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir) / "full_oversized.yaml"
            )

            config_path.write_text(
                "source:\n"
                "  name: AMARKET\n"
                "  collection_url: "
                "https://amarket.com.bo/collections/lo-nuevo\n"
                "http:\n"
                "  user_agent: "
                "PROJECT_AMARKETBOUNDINGBOXES/1.0 test\n"
                "  delay_seconds: 1.0\n"
                "  timeout_seconds: 20\n"
                "  max_retries: 3\n"
                "  backoff_seconds: 2.0\n"
                "limits:\n"
                "  max_images_per_product: 1\n"
                "  max_image_bytes: 6000000\n"
                "rights:\n"
                "  status: REDISTRIBUTION_PROHIBITED\n"
                "outputs:\n"
                "  images_dir: data/raw/amarket_full\n"
                "  manifest: "
                "data/manifests/source_assets_full.csv\n"
                "  rejects: "
                "data/manifests/scrape_rejections_full.csv\n"
                "  summary: outputs/scrape_summary_full.json\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "5 MiB",
            ):
                load_config(
                    config_path,
                    mode="full",
                )

    def test_full_crawl_config_does_not_require_max_products(self):
        """La config full válida no exige ni conserva max_products."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = (
                Path(temp_dir) / "full_valid.yaml"
            )

            config_path.write_text(
                "source:\n"
                "  name: AMARKET\n"
                "  collection_url: "
                "https://amarket.com.bo/collections/lo-nuevo\n"
                "http:\n"
                "  user_agent: "
                "PROJECT_AMARKETBOUNDINGBOXES/1.0 test\n"
                "  delay_seconds: 1.0\n"
                "  timeout_seconds: 20\n"
                "  max_retries: 3\n"
                "  backoff_seconds: 2.0\n"
                "limits:\n"
                "  max_images_per_product: 1\n"
                "  max_image_bytes: 5242880\n"
                "rights:\n"
                "  status: REDISTRIBUTION_PROHIBITED\n"
                "outputs:\n"
                "  images_dir: data/raw/amarket_full\n"
                "  manifest: "
                "data/manifests/source_assets_full.csv\n"
                "  rejects: "
                "data/manifests/scrape_rejections_full.csv\n"
                "  summary: outputs/scrape_summary_full.json\n",
                encoding="utf-8",
            )

            config = load_config(
                config_path,
                mode="full",
            )

            self.assertNotIn(
                "max_products",
                config["limits"],
            )

    def test_data_sources_full_yaml_is_valid_and_relative(self):
        """El YAML entregado cumple los valores contractuales del punto 4."""

        config = load_config(
            "configs/data_sources_full.yaml",
            mode="full",
        )

        self.assertEqual(
            config["http"]["delay_seconds"],
            1.0,
        )

        self.assertEqual(
            config["http"]["timeout_seconds"],
            20,
        )

        self.assertEqual(
            config["http"]["max_retries"],
            3,
        )

        self.assertEqual(
            config["http"]["backoff_seconds"],
            2.0,
        )

        self.assertEqual(
            config["limits"]["max_image_bytes"],
            5242880,
        )

        self.assertEqual(
            config["rights"]["status"],
            "REDISTRIBUTION_PROHIBITED",
        )

        for key in (
            "images_dir",
            "manifest",
            "rejects",
            "summary",
        ):
            path_value = config["outputs"][key]

            self.assertFalse(
                Path(path_value).is_absolute(),
                f"outputs.{key} no debe ser una ruta absoluta: "
                f"{path_value}",
            )

    def test_smoke_test_stays_limited_to_three(self):
        """--smoke-test sigue limitado a 3 productos con 5 disponibles."""

        collection_url, responses, expected_urls = (
            _build_amarket_fixture(5)
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            config = _build_fixture_config(
                root,
                collection_url,
                extra_limits={"max_products": 3},
            )

            with _patch_amarket_network(responses):
                summary = run_smoke_test(
                    config,
                    limit=3,
                )

            self.assertEqual(
                summary["selected_products"],
                3,
            )

            self.assertEqual(
                summary["accepted"],
                3,
            )

            manifest_rows = read_csv_rows(
                config["outputs"]["manifest"]
            )

            processed_urls = sorted(
                row["product_page_url"]
                for row in manifest_rows
            )

            self.assertEqual(
                processed_urls,
                expected_urls[:3],
            )

    def test_full_crawl_processes_all_unique_urls(self):
        """Full crawl procesa todas las URLs únicas, sin límite ni slicing."""

        collection_url, responses, expected_urls = (
            _build_amarket_fixture(5)
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            config = _build_fixture_config(
                root,
                collection_url,
            )

            self.assertNotIn(
                "max_products",
                config["limits"],
            )

            with _patch_amarket_network(responses):
                summary = run_full_crawl(config)

            self.assertEqual(
                summary["selected_products"],
                5,
            )

            self.assertEqual(
                summary["accepted"],
                5,
            )

            manifest_rows = read_csv_rows(
                config["outputs"]["manifest"]
            )

            processed_urls = sorted(
                row["product_page_url"]
                for row in manifest_rows
            )

            self.assertEqual(
                processed_urls,
                expected_urls,
            )

    def test_full_crawl_idempotency_and_resume(self):
        """Segunda corrida de full crawl no duplica ni sobrescribe evidencia."""

        collection_url, responses, expected_urls = (
            _build_amarket_fixture(4)
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            config = _build_fixture_config(
                root,
                collection_url,
            )

            with _patch_amarket_network(responses):
                first_summary = run_full_crawl(config)

            first_manifest_rows = read_csv_rows(
                config["outputs"]["manifest"]
            )

            first_hashes = sorted(
                row["sha256"]
                for row in first_manifest_rows
            )

            with _patch_amarket_network(responses):
                second_summary = run_full_crawl(config)

            second_manifest_rows = read_csv_rows(
                config["outputs"]["manifest"]
            )

            second_hashes = sorted(
                row["sha256"]
                for row in second_manifest_rows
            )

            self.assertEqual(
                first_summary["accepted"],
                4,
            )

            self.assertEqual(
                first_summary["accepted_this_run"],
                4,
            )

            self.assertEqual(
                second_summary["accepted"],
                4,
            )

            self.assertEqual(
                second_summary["accepted_this_run"],
                0,
            )

            self.assertEqual(
                len(second_manifest_rows),
                4,
            )

            self.assertEqual(
                first_hashes,
                second_hashes,
            )

            self.assertEqual(
                sorted(
                    row["product_page_url"]
                    for row in second_manifest_rows
                ),
                expected_urls,
            )

    def test_full_crawl_rejection_is_idempotent_across_runs(self):
        """Full crawl: un rechazo repetido no debe duplicarse ni inflar conteos."""

        collection_url = (
            "https://amarket.com.bo/collections/lo-nuevo"
        )
        robots_url = "https://amarket.com.bo/robots.txt"

        accepted_product_url = (
            "https://amarket.com.bo/products/producto-1"
        )
        rejected_product_url = (
            "https://amarket.com.bo/products/producto-2"
        )

        accepted_image_url = (
            "https://amarket.com.bo/cdn/shop/files/"
            "producto-1.png"
        )
        rejected_image_url = (
            "https://amarket.com.bo/cdn/shop/files/"
            "producto-2.png"
        )

        collection_html = (
            "<html><body>"
            '<a href="/products/producto-1">Producto 1</a>'
            '<a href="/products/producto-2">Producto 2</a>'
            "</body></html>"
        ).encode("utf-8")

        accepted_product_html = (
            "<html><head>"
            "<title>Producto 1 — Amarket</title>"
            '<meta property="og:title" content="Producto 1">'
            '<meta property="og:description" '
            'content="Descripcion 1">'
            '<meta property="og:image:secure_url" '
            f'content="{accepted_image_url}">'
            "</head><body></body></html>"
        ).encode("utf-8")

        rejected_product_html = (
            "<html><head>"
            "<title>Producto 2 — Amarket</title>"
            '<meta property="og:title" content="Producto 2">'
            '<meta property="og:description" '
            'content="Descripcion 2">'
            '<meta property="og:image:secure_url" '
            f'content="{rejected_image_url}">'
            "</head><body></body></html>"
        ).encode("utf-8")

        accepted_image_bytes = _make_test_image_bytes(
            (20, 20, 20)
        )

        responses = {
            robots_url: (
                200,
                "text/plain",
                b"User-agent: *\nAllow: /\n",
            ),
            collection_url: (
                200,
                "text/html",
                collection_html,
            ),
            accepted_product_url: (
                200,
                "text/html",
                accepted_product_html,
            ),
            rejected_product_url: (
                200,
                "text/html",
                rejected_product_html,
            ),
            accepted_image_url: (
                200,
                "image/png",
                accepted_image_bytes,
            ),
            rejected_image_url: (
                200,
                "text/plain",
                b"esto-no-es-una-imagen",
            ),
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            config = _build_fixture_config(
                root,
                collection_url,
            )

            with _patch_amarket_network(responses):
                first_summary = run_full_crawl(config)

            first_rejection_rows = read_csv_rows(
                config["outputs"]["rejects"]
            )

            self.assertEqual(
                first_summary["accepted"],
                1,
            )

            self.assertEqual(
                first_summary["rejected"],
                1,
            )

            self.assertEqual(
                len(first_rejection_rows),
                1,
            )

            with _patch_amarket_network(responses):
                second_summary = run_full_crawl(config)

            second_rejection_rows = read_csv_rows(
                config["outputs"]["rejects"]
            )

            second_manifest_rows = read_csv_rows(
                config["outputs"]["manifest"]
            )

            self.assertEqual(
                second_summary["accepted"],
                1,
            )

            self.assertEqual(
                second_summary["accepted_this_run"],
                0,
            )

            self.assertEqual(
                len(second_manifest_rows),
                1,
            )

            self.assertEqual(
                second_summary["rejected"],
                1,
                "La segunda corrida no debe inflar "
                "el conteo de rechazos.",
            )

            self.assertEqual(
                second_summary["rejected_this_run"],
                0,
                "Un rechazo ya registrado no debe "
                "contarse otra vez en la misma forma.",
            )

            self.assertEqual(
                len(second_rejection_rows),
                1,
                "rejects.csv no debe duplicar el mismo "
                "rechazo entre corridas idénticas.",
            )

            self.assertEqual(
                second_rejection_rows[0][
                    "product_page_url"
                ],
                first_rejection_rows[0][
                    "product_page_url"
                ],
            )

            self.assertEqual(
                second_rejection_rows[0][
                    "rejection_reason"
                ],
                first_rejection_rows[0][
                    "rejection_reason"
                ],
            )

            self.assertEqual(
                second_summary["attempted"],
                second_summary["accepted"]
                + second_summary["rejected"],
            )


    def test_discover_all_product_urls_paginates_and_deduplicates(self):
        """Recorre 3 páginas de colección, deduplica global y termina
        sin next link, sin acceder realmente a AMARKET."""

        base_url, responses, expected_urls = (
            _build_paginated_collection_fixture()
        )

        config = {
            "http": {
                "user_agent": (
                    "PROJECT_AMARKETBOUNDINGBOXES/1.0 test"
                ),
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            }
        }

        client = PoliteHttpClient(config)

        with _patch_amarket_network(responses):
            robots_parser = check_robots(
                client,
                base_url,
                base_url,
            )

            product_urls, collection_pages = (
                discover_all_product_urls(
                    client,
                    robots_parser,
                    base_url,
                )
            )

        self.assertEqual(
            collection_pages,
            3,
        )

        self.assertEqual(
            product_urls,
            expected_urls,
        )


    def test_pagination_ignores_external_domain(self):
        """No sigue paginación fuera del dominio contractual."""

        base_url = (
            "https://amarket.com.bo/collections/lo-nuevo"
        )

        html = (
            "<html><body>"
            '<a href="/products/producto-a">'
            "Producto A"
            "</a>"
            '<a href="https://evil.example/'
            'collections/lo-nuevo?page=2">'
            "Siguiente"
            "</a>"
            "</body></html>"
        ).encode("utf-8")

        next_url = extract_next_collection_url(
            html,
            base_url,
        )

        self.assertIsNone(
            next_url
        )


    def test_pagination_loop_fails_explicitly(self):
        """Un loop debe fallar, no truncar silenciosamente."""

        base_url, responses, _ = (
            _build_paginated_collection_fixture()
        )

        config = {
            "http": {
                "user_agent": (
                    "PROJECT_AMARKETBOUNDINGBOXES/1.0 test"
                ),
                "delay_seconds": 0,
                "timeout_seconds": 20,
                "max_retries": 3,
                "backoff_seconds": 0,
            }
        }

        client = PoliteHttpClient(
            config
        )

        with _patch_amarket_network(
            responses
        ):
            robots_parser = check_robots(
                client,
                base_url,
                base_url,
            )

            with patch(
                "src.scraper_extraction."
                "extract_next_collection_url",
                return_value=base_url,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "PAGINATION_LOOP_DETECTED",
                ):
                    discover_all_product_urls(
                        client,
                        robots_parser,
                        base_url,
                    )


if __name__ == "__main__":
    unittest.main()