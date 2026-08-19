import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.scraper_extraction import (
    MANIFEST_FIELDS,
    PoliteHttpClient,
    atomic_write_csv,
    atomic_write_json,
    calculate_sha256,
    duplicate_group_id,
    load_config,
    normalize_product_urls,
    reconcile_outputs,
    request_with_retries,
    save_image_idempotently,
    source_asset_id,
    source_asset_identity_key,
    validate_image_bytes,
    validate_image_content_type,
)


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


if __name__ == "__main__":
    unittest.main()