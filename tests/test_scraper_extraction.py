import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError

from src.scraper_extraction import (
    calculate_sha256,
    duplicate_group_id,
    normalize_product_urls,
    request_with_retries,
    save_image_idempotently,
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

        self.assertEqual(result.returncode, 0)
        self.assertIn("--config", result.stdout)
        self.assertIn("--limit", result.stdout)
        self.assertIn("--smoke-test", result.stdout)

    def test_s02_incomplete_config_fails(self):
        """S02: configuración incompleta debe fallar."""

        with tempfile.TemporaryDirectory() as temp_dir:
            config_path = Path(temp_dir) / "incomplete.yaml"

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

        self.assertNotEqual(result.returncode, 0)

        self.assertIn(
            "Falta la sección obligatoria",
            result.stderr,
        )

    def test_s03_urls_are_unique_canonical_and_sorted(self):
        """S03: URLs duplicadas/desordenadas se normalizan."""

        urls = [
            "https://amarket.com.bo/products/z-producto?variant=123",
            "https://amarket.com.bo/products/a-producto/",
            "https://amarket.com.bo/products/z-producto",
            "https://amarket.com.bo/products/a-producto#foto",
        ]

        result = normalize_product_urls(urls)

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

            with self.assertRaises(HTTPError):
                request_with_retries(
                    **common_args
                )

            self.assertEqual(
                mocked_urlopen.call_count,
                1,
            )

        for status_code in (429, 500):
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

                with self.assertRaises(HTTPError):
                    request_with_retries(
                        **common_args
                    )

                self.assertEqual(
                    mocked_urlopen.call_count,
                    common_args["max_retries"] + 1,
                )

    def test_s05_non_image_mime_is_rejected(self):
        """S05: MIME que no sea imagen debe rechazarse."""

        with self.assertRaises(ValueError):
            validate_image_content_type(
                "text/html"
            )

        with self.assertRaises(ValueError):
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

        with self.assertRaises(ValueError):
            validate_image_bytes(
                corrupt_bytes
            )

    def test_s07_same_bytes_are_idempotent(self):
        """S07: mismos bytes no crean otra versión."""

        image_bytes = (
            b"contenido-controlado-de-prueba"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = (
                Path(temp_dir) / "producto.jpg"
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
        """S07: bytes distintos no sobrescriben evidencia previa."""

        original_bytes = (
            b"version-original"
        )

        changed_bytes = (
            b"version-cambiada"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            destination = (
                Path(temp_dir) / "producto.jpg"
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

        group_a = duplicate_group_id(
            image_bytes
        )

        group_b = duplicate_group_id(
            image_bytes
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
        """S09: reanudar conserva éxitos ya guardados."""

        first_bytes = (
            b"imagen-producto-uno"
        )

        second_bytes = (
            b"imagen-producto-dos"
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)

            first_destination = (
                temp_path / "producto_1.jpg"
            )

            second_destination = (
                temp_path / "producto_2.jpg"
            )

            # Primera ejecución:
            # producto 1 se guarda correctamente.
            first_run = save_image_idempotently(
                first_destination,
                first_bytes,
            )

            self.assertEqual(
                first_run["status"],
                "created",
            )

            first_hash_before_resume = (
                calculate_sha256(
                    first_destination.read_bytes()
                )
            )

            # Aquí simulamos una interrupción:
            # producto 2 todavía no fue guardado.
            self.assertFalse(
                second_destination.exists()
            )

            # Reanudación:
            # producto 1 debe conservarse sin duplicarse.
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

            # Ahora continúa con el producto pendiente.
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

            first_hash_after_resume = (
                calculate_sha256(
                    first_destination.read_bytes()
                )
            )

            # El éxito anterior quedó intacto.
            self.assertEqual(
                first_hash_before_resume,
                first_hash_after_resume,
            )

            self.assertEqual(
                first_destination.read_bytes(),
                first_bytes,
            )

            self.assertEqual(
                second_destination.read_bytes(),
                second_bytes,
            )


if __name__ == "__main__":
    unittest.main()