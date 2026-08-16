"""Scraper y extractor de imágenes de Amarket.

Responsable: Monserrat Barba
Proyecto: PROJECT_AMARKETBOUNDINGBOXES

Implementación conforme a SCRAPER_EXTRACTION_CONTRACT v1.0.0.
"""

import argparse
import csv
import hashlib
import json
import os
import tempfile
import time
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

import yaml
from PIL import Image, UnidentifiedImageError


REQUIRED_SECTIONS = (
    "source",
    "http",
    "limits",
    "outputs",
)

RETRYABLE_STATUS_CODES = {
    429,
    500,
    502,
    503,
    504,
}

MANIFEST_FIELDS = [
    "source_asset_id",
    "sku_id",
    "product_name",
    "description",
    "source_name",
    "product_page_url",
    "image_url",
    "retrieved_at",
    "retrieval_run_id",
    "http_status",
    "content_type",
    "scraper_version",
    "sha256",
    "duplicate_group_id",
    "width_px",
    "height_px",
    "image_mode",
    "background_mode",
    "rights_status",
    "acceptance_status",
    "rejection_reason",
    "local_path",
]


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

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    if not isinstance(
        config,
        dict,
    ):
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
    """Canonicaliza una URL eliminando query, fragment y slash final."""

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
    """Canonicaliza, elimina duplicados y ordena URLs."""

    canonical_urls = {
        canonicalize_product_url(url)
        for url in urls
    }

    return sorted(
        canonical_urls
    )


def request_with_retries(
    url,
    user_agent,
    timeout_seconds,
    max_retries,
    backoff_seconds,
):
    """Realiza una petición HTTP con reintentos acotados."""

    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
        },
    )

    total_attempts = (
        max_retries + 1
    )

    for attempt in range(
        total_attempts
    ):
        try:
            return urlopen(
                request,
                timeout=timeout_seconds,
            )

        except HTTPError as error:
            if (
                error.code
                not in RETRYABLE_STATUS_CODES
            ):
                raise

            if (
                attempt
                == total_attempts - 1
            ):
                raise

        except URLError:
            if (
                attempt
                == total_attempts - 1
            ):
                raise

        sleep_seconds = (
            backoff_seconds
            * (attempt + 1)
        )

        if sleep_seconds > 0:
            time.sleep(
                sleep_seconds
            )

    raise RuntimeError(
        "La petición HTTP terminó en un estado inesperado."
    )


def validate_image_content_type(
    content_type,
):
    """Valida que Content-Type corresponda a una imagen."""

    if not content_type:
        raise ValueError(
            "Content-Type ausente."
        )

    normalized = (
        content_type
        .split(";", 1)[0]
        .strip()
        .lower()
    )

    if not normalized.startswith(
        "image/"
    ):
        raise ValueError(
            f"MIME no permitido para imagen: {content_type}"
        )

    return normalized


def validate_image_bytes(
    image_bytes,
):
    """Valida que los bytes correspondan a una imagen decodificable."""

    if not image_bytes:
        raise ValueError(
            "La imagen está vacía."
        )

    try:
        with Image.open(
            BytesIO(image_bytes)
        ) as image:
            image.verify()

    except (
        UnidentifiedImageError,
        OSError,
    ) as error:
        raise ValueError(
            "Los bytes descargados no corresponden "
            "a una imagen válida."
        ) from error

    return True


def calculate_sha256(
    data,
):
    """Calcula SHA-256."""

    return hashlib.sha256(
        data
    ).hexdigest()


def duplicate_group_id(
    image_bytes,
):
    """Genera un identificador estable para bytes duplicados."""

    return calculate_sha256(
        image_bytes
    )


def save_image_idempotently(
    destination,
    image_bytes,
):
    """Guarda sin duplicar ni sobrescribir bytes distintos."""

    destination = Path(
        destination
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    new_hash = calculate_sha256(
        image_bytes
    )

    if destination.exists():
        existing_bytes = (
            destination.read_bytes()
        )

        existing_hash = (
            calculate_sha256(
                existing_bytes
            )
        )

        if (
            existing_hash
            == new_hash
        ):
            return {
                "status": "existing",
                "sha256": new_hash,
                "duplicate_group_id": (
                    duplicate_group_id(
                        image_bytes
                    )
                ),
                "path": str(
                    destination
                ),
            }

        raise FileExistsError(
            "El archivo ya existe con bytes distintos: "
            f"{destination}"
        )

    destination.write_bytes(
        image_bytes
    )

    return {
        "status": "created",
        "sha256": new_hash,
        "duplicate_group_id": (
            duplicate_group_id(
                image_bytes
            )
        ),
        "path": str(
            destination
        ),
    }


def atomic_write_csv(
    destination,
    rows,
    fieldnames,
):
    """Escribe CSV mediante archivo temporal y reemplazo atómico."""

    destination = Path(
        destination
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        newline="",
        delete=False,
        dir=destination.parent,
        prefix=destination.name,
        suffix=".tmp",
    )

    temp_path = Path(
        temp_file.name
    )

    try:
        with temp_file:
            writer = csv.DictWriter(
                temp_file,
                fieldnames=fieldnames,
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(
                    row
                )

        os.replace(
            temp_path,
            destination,
        )

    except Exception:
        if temp_path.exists():
            temp_path.unlink()

        raise


def atomic_write_json(
    destination,
    payload,
):
    """Escribe JSON mediante archivo temporal y reemplazo atómico."""

    destination = Path(
        destination
    )

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    temp_file = tempfile.NamedTemporaryFile(
        mode="w",
        encoding="utf-8",
        delete=False,
        dir=destination.parent,
        prefix=destination.name,
        suffix=".tmp",
    )

    temp_path = Path(
        temp_file.name
    )

    try:
        with temp_file:
            json.dump(
                payload,
                temp_file,
                ensure_ascii=False,
                indent=2,
            )

        os.replace(
            temp_path,
            destination,
        )

    except Exception:
        if temp_path.exists():
            temp_path.unlink()

        raise


def reconcile_outputs(
    manifest_rows,
    rejection_rows,
    images_dir,
):
    """Reconcilia imágenes, manifest y rechazos."""

    images_dir = Path(
        images_dir
    )

    if images_dir.exists():
        image_files = [
            path
            for path in images_dir.iterdir()
            if path.is_file()
        ]
    else:
        image_files = []

    accepted_count = len(
        manifest_rows
    )

    rejected_count = len(
        rejection_rows
    )

    attempted_count = (
        accepted_count
        + rejected_count
    )

    image_count = len(
        image_files
    )

    if (
        image_count
        != accepted_count
    ):
        raise ValueError(
            "Reconciliación inválida: "
            f"{image_count} archivos para "
            f"{accepted_count} filas aceptadas."
        )

    return {
        "attempted": attempted_count,
        "accepted": accepted_count,
        "rejected": rejected_count,
        "image_files": image_count,
        "manifest_rows": accepted_count,
        "rejection_rows": rejected_count,
    }


def main():
    """Punto de entrada del scraper."""

    args = parse_args()

    config = load_config(
        args.config
    )

    configured_limit = (
        config["limits"]["max_products"]
    )

    limit = (
        args.limit
        if args.limit is not None
        else configured_limit
    )

    if limit < 1:
        raise ValueError(
            "El límite debe ser mayor o igual a 1."
        )

    if (
        limit
        > configured_limit
    ):
        raise ValueError(
            f"El límite solicitado ({limit}) supera el máximo "
            f"permitido por la configuración ({configured_limit})."
        )

    print(
        "Configuración válida."
    )

    print(
        "Fuente:",
        config["source"]["name"],
    )

    print(
        "Límite:",
        limit,
    )

    print(
        "Smoke test:",
        args.smoke_test,
    )


if __name__ == "__main__":
    main()