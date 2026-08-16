"""Scraper y extractor de imágenes de Amarket.

Responsable: Monserrat Barba
Proyecto: PROJECT_AMARKETBOUNDINGBOXES

Implementación conforme a SCRAPER_EXTRACTION_CONTRACT v1.0.0.
"""

import argparse
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import yaml


REQUIRED_SECTIONS = ("source", "http", "limits", "outputs")


def parse_args():
    """Procesa los argumentos de línea de comandos."""

    parser = argparse.ArgumentParser(
        description="Adquisición controlada de imágenes públicas de Amarket."
    )

    parser.add_argument(
        "--config",
        default="configs/data_sources.yaml",
        help="Ruta al archivo YAML de configuración.",
    )

    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Número máximo de productos a procesar.",
    )

    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Ejecuta el piloto controlado definido por el contrato.",
    )

    return parser.parse_args()


def load_config(config_path):
    """Carga y valida la configuración antes de cualquier acceso a red."""

    path = Path(config_path)

    if not path.is_file():
        raise FileNotFoundError(
            f"No existe el archivo de configuración: {config_path}"
        )

    with path.open("r", encoding="utf-8") as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "La configuración YAML debe contener un objeto raíz."
        )

    for section in REQUIRED_SECTIONS:
        if section not in config:
            raise ValueError(
                f"Falta la sección obligatoria '{section}' "
                "en la configuración."
            )

    return config


def canonicalize_product_url(url):
    """Canonicaliza una URL de producto eliminando query y fragment."""

    parsed = urlsplit(url)

    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()

    path = parsed.path.rstrip("/")

    return urlunsplit(
        (
            scheme,
            netloc,
            path,
            "",
            "",
        )
    )


def normalize_product_urls(urls):
    """Canonicaliza, elimina duplicados y ordena URLs de productos."""

    canonical_urls = {
        canonicalize_product_url(url)
        for url in urls
    }

    return sorted(canonical_urls)


def main():
    """Punto de entrada del scraper."""

    args = parse_args()

    # La configuración se valida antes de cualquier acceso a red.
    config = load_config(args.config)

    configured_limit = config["limits"]["max_products"]
    limit = args.limit if args.limit is not None else configured_limit

    if limit < 1:
        raise ValueError(
            "El límite debe ser mayor o igual a 1."
        )

    if limit > configured_limit:
        raise ValueError(
            f"El límite solicitado ({limit}) supera el máximo "
            f"permitido por la configuración ({configured_limit})."
        )

    print("Configuración válida.")
    print("Fuente:", config["source"]["name"])
    print("Límite:", limit)
    print("Smoke test:", args.smoke_test)


if __name__ == "__main__":
    main()