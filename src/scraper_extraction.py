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
import re
import tempfile
import time
import uuid

from datetime import datetime, timezone
from html.parser import HTMLParser
from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

import yaml
from PIL import Image, UnidentifiedImageError


SCRAPER_VERSION = "1.0.0"

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

REJECTION_FIELDS = [
    "product_page_url",
    "image_url",
    "retrieved_at",
    "retrieval_run_id",
    "rejection_reason",
]


class CollectionParser(HTMLParser):
    """Extrae enlaces de producto desde la colección."""

    def __init__(self):
        super().__init__()
        self.product_links = []

    def handle_starttag(self, tag, attrs):
        if tag.lower() != "a":
            return

        attributes = dict(attrs)
        href = attributes.get("href")

        if href and "/products/" in href:
            self.product_links.append(href)


class ProductParser(HTMLParser):
    """Extrae metadatos públicos de una ficha de producto."""

    def __init__(self):
        super().__init__()
        self.meta = {}
        self.images = []
        self.text_parts = []
        self._inside_title = False
        self._title_parts = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        tag = tag.lower()

        if tag == "meta":
            key = (
                attributes.get("property")
                or attributes.get("name")
            )
            content = attributes.get("content")

            if key and content:
                self.meta[key.lower()] = content.strip()

        elif tag == "img":
            image_url = (
                attributes.get("src")
                or attributes.get("data-src")
            )
            alt = attributes.get("alt", "")

            if image_url:
                self.images.append(
                    {
                        "url": image_url,
                        "alt": alt.strip(),
                    }
                )

        elif tag == "title":
            self._inside_title = True

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self._inside_title = False

    def handle_data(self, data):
        clean = " ".join(data.split())

        if not clean:
            return

        self.text_parts.append(clean)

        if self._inside_title:
            self._title_parts.append(clean)

    @property
    def page_text(self):
        return " ".join(self.text_parts)

    @property
    def title(self):
        return " ".join(self._title_parts).strip()


class PoliteHttpClient:
    """Cliente HTTP que respeta el delay contractual."""

    def __init__(self, config):
        self.user_agent = config["http"]["user_agent"]
        self.delay_seconds = float(
            config["http"]["delay_seconds"]
        )
        self.timeout_seconds = float(
            config["http"]["timeout_seconds"]
        )
        self.max_retries = int(
            config["http"]["max_retries"]
        )
        self.backoff_seconds = float(
            config["http"]["backoff_seconds"]
        )
        self._last_request_time = None

    def _wait_if_needed(self):
        if self._last_request_time is None:
            return

        elapsed = time.monotonic() - self._last_request_time
        remaining = self.delay_seconds - elapsed

        if remaining > 0:
            time.sleep(remaining)

    def get(self, url, max_bytes=None):
        self._wait_if_needed()

        if max_bytes is not None:
            try:
                max_bytes = int(max_bytes)
            except (TypeError, ValueError) as error:
                raise ValueError(
                    "max_bytes debe ser un entero positivo."
                ) from error

            if max_bytes <= 0:
                raise ValueError(
                    "max_bytes debe ser un entero positivo."
                )

        response = request_with_retries(
            url=url,
            user_agent=self.user_agent,
            timeout_seconds=self.timeout_seconds,
            max_retries=self.max_retries,
            backoff_seconds=self.backoff_seconds,
        )

        try:
            status = getattr(response, "status", None)

            if status is None:
                status = response.getcode()

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            if max_bytes is None:
                body = response.read()

            else:
                content_length = response.headers.get(
                    "Content-Length"
                )

                if content_length:
                    try:
                        declared_size = int(
                            content_length
                        )
                    except (TypeError, ValueError):
                        declared_size = None

                    if (
                        declared_size is not None
                        and declared_size > max_bytes
                    ):
                        raise RuntimeError(
                            "REJECTED_MAX_BYTES"
                        )

                body = response.read(
                    max_bytes + 1
                )

                if len(body) > max_bytes:
                    raise RuntimeError(
                        "REJECTED_MAX_BYTES"
                    )

        finally:
            response.close()
            self._last_request_time = time.monotonic()

        return {
            "status": status,
            "content_type": content_type,
            "body": body,
        }


def parse_args():
    """Procesa los argumentos de línea de comandos."""

    parser = argparse.ArgumentParser(
        description=(
            "Adquisición controlada de imágenes "
            "públicas de Amarket."
        )
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
        "--output-dir",
        default=None,
        help=(
            "Directorio de salida para imágenes. "
            "Si se especifica, tiene prioridad sobre el YAML."
        ),
    )

    parser.add_argument(
        "--manifest",
        default=None,
        help=(
            "Ruta del manifest CSV. "
            "Si se especifica, tiene prioridad sobre el YAML."
        ),
    )

    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help=(
            "Ejecuta el piloto controlado "
            "definido por el contrato."
        ),
    )

    return parser.parse_args()


def load_config(config_path):
    """Carga y valida configuración antes de red."""

    path = Path(config_path)

    if not path.is_file():
        raise FileNotFoundError(
            "No existe el archivo de configuración: "
            f"{config_path}"
        )

    with path.open(
        "r",
        encoding="utf-8",
    ) as file:
        config = yaml.safe_load(file)

    if not isinstance(config, dict):
        raise ValueError(
            "La configuración YAML debe contener un objeto raíz."
        )

    for section in REQUIRED_SECTIONS:
        if section not in config:
            raise ValueError(
                f"Falta la sección obligatoria "
                f"'{section}' en la configuración."
            )

    required_values = {
        "source": (
            "name",
            "collection_url",
        ),
        "http": (
            "user_agent",
            "delay_seconds",
            "timeout_seconds",
            "max_retries",
            "backoff_seconds",
        ),
        "limits": (
            "max_products",
            "max_images_per_product",
            "max_image_bytes",
        ),
        "outputs": (
            "images_dir",
            "manifest",
            "rejects",
            "summary",
        ),
    }

    for section, keys in required_values.items():
        for key in keys:
            if key not in config[section]:
                raise ValueError(
                    f"Falta '{section}.{key}' "
                    "en la configuración."
                )

    if config["source"]["name"] != "AMARKET":
        raise ValueError(
            "La fuente contractual debe ser AMARKET."
        )

    if int(
        config["limits"]["max_images_per_product"]
    ) != 1:
        raise ValueError(
            "El smoke test permite una imagen "
            "principal por producto."
        )

    try:
        max_image_bytes = int(
            config["limits"]["max_image_bytes"]
        )
    except (TypeError, ValueError) as error:
        raise ValueError(
            "limits.max_image_bytes debe ser "
            "un entero positivo."
        ) from error

    if max_image_bytes <= 0:
        raise ValueError(
            "limits.max_image_bytes debe ser "
            "un entero positivo."
        )

    return config


def canonicalize_product_url(url):
    """Canonicaliza URL de producto."""

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
    """Canonicaliza, deduplica y ordena URLs."""

    canonical_urls = {
        canonicalize_product_url(url)
        for url in urls
    }

    return sorted(canonical_urls)


def request_with_retries(
    url,
    user_agent,
    timeout_seconds,
    max_retries,
    backoff_seconds,
):
    """Realiza petición HTTP con retry acotado."""

    request = Request(
        url,
        headers={
            "User-Agent": user_agent,
        },
    )

    total_attempts = max_retries + 1

    for attempt in range(total_attempts):
        try:
            return urlopen(
                request,
                timeout=timeout_seconds,
            )

        except HTTPError as error:
            if error.code not in RETRYABLE_STATUS_CODES:
                raise

            if attempt == total_attempts - 1:
                raise

        except URLError:
            if attempt == total_attempts - 1:
                raise

        sleep_seconds = backoff_seconds * (attempt + 1)

        if sleep_seconds > 0:
            time.sleep(sleep_seconds)

    raise RuntimeError(
        "La petición HTTP terminó "
        "en un estado inesperado."
    )


def validate_html_content_type(content_type):
    """Valida respuesta HTML."""

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

    if normalized not in (
        "text/html",
        "application/xhtml+xml",
    ):
        raise ValueError(
            f"Content-Type HTML inesperado: "
            f"{content_type}"
        )

    return normalized


def validate_image_content_type(content_type):
    """Valida MIME de imagen."""

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

    if not normalized.startswith("image/"):
        raise ValueError(
            f"MIME no permitido para imagen: "
            f"{content_type}"
        )

    return normalized


def validate_image_bytes(image_bytes):
    """Valida decodificación de una imagen."""

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
            "Los bytes descargados "
            "no corresponden a una imagen válida."
        ) from error

    return True


def inspect_image(image_bytes):
    """Obtiene dimensiones, modo y fondo."""

    validate_image_bytes(image_bytes)

    with Image.open(
        BytesIO(image_bytes)
    ) as image:
        image.load()

        width, height = image.size

        if width <= 0 or height <= 0:
            raise ValueError(
                "Dimensiones de imagen inválidas."
            )

        image_mode = image.mode
        has_transparency = False

        if "A" in image.getbands():
            alpha = image.getchannel("A")
            extrema = alpha.getextrema()

            if extrema[0] < 255:
                has_transparency = True

        if has_transparency:
            background_mode = "TRANSPARENT_ALPHA"

        else:
            rgb = image.convert("RGB")

            corners = [
                rgb.getpixel((0, 0)),
                rgb.getpixel((width - 1, 0)),
                rgb.getpixel((0, height - 1)),
                rgb.getpixel(
                    (
                        width - 1,
                        height - 1,
                    )
                ),
            ]

            reference = corners[0]

            uniform = all(
                all(
                    abs(
                        channel
                        - reference[index]
                    ) <= 12
                    for index, channel
                    in enumerate(pixel)
                )
                for pixel in corners[1:]
            )

            background_mode = (
                "UNIFORM_RGB"
                if uniform
                else "COMPLEX"
            )

        return {
            "width_px": width,
            "height_px": height,
            "image_mode": image_mode,
            "background_mode": background_mode,
            "format": image.format,
        }


def calculate_sha256(data):
    """Calcula hash SHA-256."""

    return hashlib.sha256(data).hexdigest()


def duplicate_group_id(image_bytes):
    """Grupo estable de bytes duplicados."""

    return calculate_sha256(image_bytes)


def source_asset_identity_key(
    source_name,
    product_page_url,
    image_url,
    sha256,
):
    """Identidad estable ignorando query/fragment temporales de la imagen."""

    parsed_image = urlsplit(image_url)

    canonical_image_url = urlunsplit(
        (
            parsed_image.scheme.lower(),
            parsed_image.netloc.lower(),
            parsed_image.path,
            "",
            "",
        )
    )

    return "|".join(
        (
            source_name,
            canonicalize_product_url(product_page_url),
            canonical_image_url,
            sha256,
        )
    )


def source_asset_id(
    source_name,
    product_page_url,
    image_url,
    sha256,
):
    """Genera identificador trazable del asset."""

    canonical_string = source_asset_identity_key(
        source_name,
        product_page_url,
        image_url,
        sha256,
    )

    return calculate_sha256(
        canonical_string.encode("utf-8")
    )


def save_image_idempotently(
    destination,
    image_bytes,
):
    """Guarda sin duplicar ni sobrescribir."""

    destination = Path(destination)

    destination.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    new_hash = calculate_sha256(
        image_bytes
    )

    if destination.exists():
        existing_bytes = destination.read_bytes()

        existing_hash = calculate_sha256(
            existing_bytes
        )

        if existing_hash == new_hash:
            return {
                "status": "existing",
                "sha256": new_hash,
                "duplicate_group_id": duplicate_group_id(
                    image_bytes
                ),
                "path": str(destination),
            }

        raise FileExistsError(
            "El archivo ya existe con bytes "
            f"distintos: {destination}"
        )

    temp_file = tempfile.NamedTemporaryFile(
        mode="wb",
        dir=destination.parent,
        prefix=f".{destination.name}.",
        suffix=".tmp",
        delete=False,
    )

    temp_path = Path(temp_file.name)

    try:
        with temp_file:
            temp_file.write(
                image_bytes
            )
            temp_file.flush()
            os.fsync(
                temp_file.fileno()
            )

        os.replace(
            temp_path,
            destination,
        )

    except Exception:
        if temp_path.exists():
            temp_path.unlink()

        raise

    return {
        "status": "created",
        "sha256": new_hash,
        "duplicate_group_id": duplicate_group_id(
            image_bytes
        ),
        "path": str(destination),
    }


def atomic_write_csv(
    destination,
    rows,
    fieldnames,
):
    """Escritura atómica de CSV."""

    destination = Path(destination)

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

    temp_path = Path(temp_file.name)

    try:
        with temp_file:
            writer = csv.DictWriter(
                temp_file,
                fieldnames=fieldnames,
                extrasaction="ignore",
                lineterminator="\n",
            )

            writer.writeheader()

            for row in rows:
                writer.writerow(row)

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
    """Escritura atómica de JSON."""

    destination = Path(destination)

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

    temp_path = Path(temp_file.name)

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


def read_csv_rows(path):
    """Carga filas previas si el CSV existe."""

    path = Path(path)

    if not path.exists():
        return []

    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        return list(
            csv.DictReader(file)
        )


def reconcile_outputs(
    manifest_rows,
    rejection_rows,
    images_dir,
):
    """Reconcilia archivos y registros."""

    images_dir = Path(images_dir)

    if images_dir.exists():
        image_files = [
            path
            for path
            in images_dir.iterdir()
            if path.is_file()
        ]
    else:
        image_files = []

    accepted_count = len(manifest_rows)
    rejected_count = len(rejection_rows)
    attempted_count = (
        accepted_count
        + rejected_count
    )
    image_count = len(image_files)

    if image_count != accepted_count:
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


def check_robots(
    client,
    base_url,
    target_url,
):
    """Consulta robots.txt y valida target."""

    parsed_base = urlsplit(base_url)

    robots_url = urlunsplit(
        (
            parsed_base.scheme,
            parsed_base.netloc,
            "/robots.txt",
            "",
            "",
        )
    )

    response = client.get(
        robots_url
    )

    if response["status"] != 200:
        raise RuntimeError(
            "No se pudo verificar robots.txt."
        )

    text = response[
        "body"
    ].decode(
        "utf-8",
        errors="replace",
    )

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(
        text.splitlines()
    )

    allowed = parser.can_fetch(
        client.user_agent,
        target_url,
    )

    if not allowed:
        raise PermissionError(
            "robots.txt no permite acceder a: "
            f"{target_url}"
        )

    return parser


def extract_product_urls(
    html_bytes,
    collection_url,
):
    """Extrae productos desde colección."""

    html = html_bytes.decode(
        "utf-8",
        errors="replace",
    )

    parser = CollectionParser()
    parser.feed(html)

    urls = [
        urljoin(
            collection_url,
            href,
        )
        for href
        in parser.product_links
    ]

    valid_urls = []

    for url in urls:
        parsed = urlsplit(url)

        if (
            parsed.scheme == "https"
            and parsed.netloc.lower()
            == "amarket.com.bo"
            and "/products/"
            in parsed.path
        ):
            valid_urls.append(url)

    return normalize_product_urls(
        valid_urls
    )


def extract_sku_from_product_url(product_url):
    """Extrae SKU desde el slug /products/<sku> cuando está disponible."""

    parsed = urlsplit(product_url)

    match = re.search(
        r"/products/([^/?#]+)$",
        parsed.path.rstrip("/"),
        flags=re.IGNORECASE,
    )

    if not match:
        return ""

    candidate = match.group(1).strip()

    if re.fullmatch(
        r"[A-Za-z0-9._-]+",
        candidate,
    ):
        return candidate

    return ""


def normalize_image_url(
    image_url,
    product_url,
):
    """Normaliza URL candidata de imagen."""

    if not image_url:
        return None

    image_url = image_url.replace(
        "&amp;",
        "&",
    )

    absolute = urljoin(
        product_url,
        image_url,
    )

    parsed = urlsplit(
        absolute
    )

    path = parsed.path

    if "/cdn/shop/files/" not in path:
        return None

    start = path.index(
        "/cdn/shop/files/"
    )

    allowed_path = path[
        start:
    ]

    return urlunsplit(
        (
            "https",
            "amarket.com.bo",
            allowed_path,
            parsed.query,
            "",
        )
    )


def extract_product_metadata(
    html_bytes,
    product_url,
):
    """Extrae SKU, nombre, descripción e imagen principal."""

    html = html_bytes.decode(
        "utf-8",
        errors="replace",
    )

    parser = ProductParser()
    parser.feed(html)

    product_name = (
        parser.meta.get(
            "og:title"
        )
        or parser.title
        or ""
    ).strip()

    if " — Amarket" in product_name:
        product_name = (
            product_name
            .replace(
                " — Amarket",
                "",
            )
            .strip()
        )

    description = (
        parser.meta.get(
            "og:description"
        )
        or parser.meta.get(
            "description"
        )
        or ""
    ).strip()

    sku_id = extract_sku_from_product_url(
        product_url
    )

    if not sku_id:
        sku_match = re.search(
            r'"sku"\s*:\s*"([A-Za-z0-9._-]+)"',
            html,
            flags=re.IGNORECASE,
        )

        if sku_match:
            sku_id = sku_match.group(1).strip()

    image_candidates = []

    for key in (
        "og:image:secure_url",
        "og:image",
        "twitter:image",
    ):
        candidate = parser.meta.get(key)

        if candidate:
            image_candidates.append(
                candidate
            )

    matching_alt = [
        item["url"]
        for item in parser.images
        if product_name
        and product_name.lower()
        in item["alt"].lower()
    ]

    image_candidates.extend(
        matching_alt
    )

    image_candidates.extend(
        item["url"]
        for item in parser.images
    )

    image_url = None

    for candidate in image_candidates:
        normalized = normalize_image_url(
            candidate,
            product_url,
        )

        if normalized:
            image_url = normalized
            break

    if not product_name:
        raise ValueError(
            "No se pudo extraer nombre del producto."
        )

    if not sku_id:
        raise ValueError(
            "No se pudo extraer SKU del producto."
        )

    if not image_url:
        raise ValueError(
            "No se encontró imagen principal "
            "en el dominio permitido."
        )

    return {
        "sku_id": sku_id,
        "product_name": product_name,
        "description": description,
        "product_page_url": canonicalize_product_url(
            product_url
        ),
        "image_url": image_url,
    }


def extension_from_image(
    image_info,
    content_type,
):
    """Obtiene extensión coherente."""

    image_format = (
        image_info.get(
            "format"
        )
        or ""
    ).upper()

    mapping = {
        "JPEG": ".jpg",
        "PNG": ".png",
        "WEBP": ".webp",
    }

    extension = mapping.get(
        image_format
    )

    if extension:
        return extension

    mime_mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
    }

    if content_type in mime_mapping:
        return mime_mapping[
            content_type
        ]

    raise ValueError(
        "Formato de imagen no permitido."
    )


def make_rejection(
    product_page_url,
    image_url,
    run_id,
    reason,
):
    """Construye registro explícito de rechazo."""

    return {
        "product_page_url": product_page_url,
        "image_url": image_url or "",
        "retrieved_at": datetime.now(
            timezone.utc
        ).isoformat(),
        "retrieval_run_id": run_id,
        "rejection_reason": reason,
    }


def run_smoke_test(
    config,
    limit,
):
    """Ejecuta el piloto real controlado."""

    client = PoliteHttpClient(
        config
    )

    collection_url = (
        config["source"][
            "collection_url"
        ]
    )

    source_name = (
        config["source"][
            "name"
        ]
    )

    images_dir = Path(
        config["outputs"][
            "images_dir"
        ]
    )

    manifest_path = Path(
        config["outputs"][
            "manifest"
        ]
    )

    rejects_path = Path(
        config["outputs"][
            "rejects"
        ]
    )

    summary_path = Path(
        config["outputs"][
            "summary"
        ]
    )

    run_id = str(
        uuid.uuid4()
    )

    print(
        "1/5 Verificando robots.txt..."
    )

    robots_parser = check_robots(
        client,
        collection_url,
        collection_url,
    )

    print(
        "2/5 Descargando colección..."
    )

    collection_response = client.get(
        collection_url
    )

    if (
        collection_response["status"]
        != 200
    ):
        raise RuntimeError(
            "La colección no respondió HTTP 200."
        )

    validate_html_content_type(
        collection_response[
            "content_type"
        ]
    )

    product_urls = extract_product_urls(
        collection_response[
            "body"
        ],
        collection_url,
    )

    if not product_urls:
        raise RuntimeError(
            "No se encontraron URLs de producto."
        )

    selected_urls = product_urls[
        :limit
    ]

    print(
        f"3/5 Productos seleccionados: "
        f"{len(selected_urls)}"
    )

    previous_manifest = read_csv_rows(
        manifest_path
    )

    previous_rejections = read_csv_rows(
        rejects_path
    )

    manifest_by_id = {
        row["source_asset_id"]: row
        for row
        in previous_manifest
        if row.get(
            "source_asset_id"
        )
    }

    manifest_by_identity = {
        source_asset_identity_key(
            row.get("source_name", ""),
            row.get("product_page_url", ""),
            row.get("image_url", ""),
            row.get("sha256", ""),
        ): row
        for row in previous_manifest
        if row.get("sha256")
    }

    rejection_rows = list(
        previous_rejections
    )

    accepted_this_run = 0
    rejected_this_run = 0

    for index, product_url in enumerate(
        selected_urls,
        start=1,
    ):
        print(
            f"   Producto "
            f"{index}/{len(selected_urls)}"
        )

        image_url = ""

        try:
            if not robots_parser.can_fetch(
                client.user_agent,
                product_url,
            ):
                raise PermissionError(
                    "ROBOTS_PRODUCT_BLOCKED"
                )

            product_response = client.get(
                product_url
            )

            if (
                product_response[
                    "status"
                ]
                != 200
            ):
                raise RuntimeError(
                    "PRODUCT_HTTP_NOT_200"
                )

            validate_html_content_type(
                product_response[
                    "content_type"
                ]
            )

            metadata = extract_product_metadata(
                product_response[
                    "body"
                ],
                product_url,
            )

            image_url = metadata[
                "image_url"
            ]

            if not robots_parser.can_fetch(
                client.user_agent,
                image_url,
            ):
                raise PermissionError(
                    "ROBOTS_IMAGE_BLOCKED"
                )

            image_response = client.get(
                image_url,
                max_bytes=int(
                    config["limits"][
                        "max_image_bytes"
                    ]
                ),
            )

            if (
                image_response[
                    "status"
                ]
                != 200
            ):
                raise RuntimeError(
                    "IMAGE_HTTP_NOT_200"
                )

            content_type = validate_image_content_type(
                image_response[
                    "content_type"
                ]
            )

            image_bytes = image_response[
                "body"
            ]

            image_info = inspect_image(
                image_bytes
            )

            if (
                image_info[
                    "background_mode"
                ]
                not in (
                    "TRANSPARENT_ALPHA",
                    "UNIFORM_RGB",
                )
            ):
                raise ValueError(
                    "BACKGROUND_COMPLEX"
                )

            sha256 = calculate_sha256(
                image_bytes
            )

            group_id = duplicate_group_id(
                image_bytes
            )

            asset_id = source_asset_id(
                source_name,
                metadata[
                    "product_page_url"
                ],
                image_url,
                sha256,
            )

            extension = extension_from_image(
                image_info,
                content_type,
            )

            filename = (
                f"{metadata['sku_id']}"
                f"_{sha256[:12]}"
                f"{extension}"
            )

            destination = (
                images_dir
                / filename
            )

            save_result = save_image_idempotently(
                destination,
                image_bytes,
            )

            row = {
                "source_asset_id": asset_id,
                "sku_id": metadata[
                    "sku_id"
                ],
                "product_name": metadata[
                    "product_name"
                ],
                "description": metadata[
                    "description"
                ],
                "source_name": source_name,
                "product_page_url": metadata[
                    "product_page_url"
                ],
                "image_url": image_url,
                "retrieved_at": datetime.now(
                    timezone.utc
                ).isoformat(),
                "retrieval_run_id": run_id,
                "http_status": str(
                    image_response[
                        "status"
                    ]
                ),
                "content_type": content_type,
                "scraper_version": SCRAPER_VERSION,
                "sha256": sha256,
                "duplicate_group_id": group_id,
                "width_px": str(
                    image_info[
                        "width_px"
                    ]
                ),
                "height_px": str(
                    image_info[
                        "height_px"
                    ]
                ),
                "image_mode": image_info[
                    "image_mode"
                ],
                "background_mode": image_info[
                    "background_mode"
                ],
                "rights_status": (
                    "REDISTRIBUTION_PROHIBITED"
                ),
                "acceptance_status": (
                    "ACCEPTED"
                ),
                "rejection_reason": "",
                "local_path": save_result[
                    "path"
                ],
            }

            identity_key = source_asset_identity_key(
                source_name,
                metadata["product_page_url"],
                image_url,
                sha256,
            )

            if (
                asset_id not in manifest_by_id
                and identity_key not in manifest_by_identity
            ):
                accepted_this_run += 1
                manifest_by_id[
                    asset_id
                ] = row
                manifest_by_identity[
                    identity_key
                ] = row

            print(
                "      ACCEPTED "
                f"SKU={metadata['sku_id']}"
            )

        except Exception as error:
            reason = (
                f"{type(error).__name__}: "
                f"{error}"
            )

            rejection_rows.append(
                make_rejection(
                    product_url,
                    image_url,
                    run_id,
                    reason,
                )
            )

            rejected_this_run += 1

            print(
                "      REJECTED "
                f"{reason}"
            )

    manifest_rows = sorted(
        manifest_by_id.values(),
        key=lambda row: row[
            "source_asset_id"
        ],
    )

    atomic_write_csv(
        manifest_path,
        manifest_rows,
        MANIFEST_FIELDS,
    )

    atomic_write_csv(
        rejects_path,
        rejection_rows,
        REJECTION_FIELDS,
    )

    summary = reconcile_outputs(
        manifest_rows,
        rejection_rows,
        images_dir,
    )

    summary.update(
        {
            "retrieval_run_id": run_id,
            "selected_products": len(
                selected_urls
            ),
            "accepted_this_run": (
                accepted_this_run
            ),
            "rejected_this_run": (
                rejected_this_run
            ),
        }
    )

    atomic_write_json(
        summary_path,
        summary,
    )

    print(
        "4/5 Outputs escritos."
    )

    print(
        "5/5 Resumen:"
    )

    print(
        json.dumps(
            summary,
            ensure_ascii=False,
            indent=2,
        )
    )

    return summary


def main():
    """Punto de entrada."""

    args = parse_args()

    config = load_config(
        args.config
    )

    if args.output_dir is not None:
        config["outputs"]["images_dir"] = (
            args.output_dir
        )

    if args.manifest is not None:
        config["outputs"]["manifest"] = (
            args.manifest
        )

    configured_limit = int(
        config["limits"][
            "max_products"
        ]
    )

    limit = (
        args.limit
        if args.limit is not None
        else configured_limit
    )

    if limit < 1:
        raise ValueError(
            "El límite debe ser "
            "mayor o igual a 1."
        )

    if limit > configured_limit:
        raise ValueError(
            f"El límite solicitado ({limit}) "
            f"supera el máximo permitido "
            f"por la configuración "
            f"({configured_limit})."
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

    print(
        "Max image bytes:",
        config["limits"]["max_image_bytes"],
    )

    print(
        "Output dir:",
        config["outputs"]["images_dir"],
    )

    print(
        "Manifest:",
        config["outputs"]["manifest"],
    )

    if not args.smoke_test:
        print(
            "No se accede a red sin "
            "--smoke-test."
        )
        return

    run_smoke_test(
        config,
        limit,
    )


if __name__ == "__main__":
    main()