import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from src.scraper_extraction import normalize_product_urls


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

        self.assertEqual(result, expected)


if __name__ == "__main__":
    unittest.main()
    