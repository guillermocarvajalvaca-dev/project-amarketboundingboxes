"""CLI de inferencia para el detector monoclase AMARKET.

Carga un peso YOLO ya entrenado y ejecuta inferencia sobre una imagen o una
carpeta de imágenes. Produce visualizaciones, JSON de detecciones y tiempos.

Ejemplo:
    python src/predict.py \
        --model outputs/demo_model/amarket_yolo11n_g4_A_best.pt \
        --input data/sample \
        --device cpu \
        --output-dir outputs/predictions/demo
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

EXTENSIONES = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sha256_archivo(path: Path) -> str:
    """Calcula SHA-256 de un archivo sin cargarlo completo en memoria."""
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        for bloque in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(bloque)

    return digest.hexdigest()


def resolver_imagenes(input_path: Path) -> list[Path]:
    """Devuelve una lista determinista de imágenes válidas."""
    if input_path.is_file():
        if input_path.suffix.lower() not in EXTENSIONES:
            raise ValueError(
                f"archivo de entrada no soportado: {input_path}"
            )
        return [input_path]

    if not input_path.is_dir():
        raise FileNotFoundError(
            f"no existe --input: {input_path}"
        )

    imagenes = sorted(
        path
        for path in input_path.iterdir()
        if path.is_file() and path.suffix.lower() in EXTENSIONES
    )

    if not imagenes:
        raise ValueError(
            f"no se encontraron imágenes soportadas en: {input_path}"
        )

    return imagenes


def nombre_clase(names, class_id: int) -> str:
    """Resuelve el nombre de clase para dict o lista de Ultralytics."""
    if isinstance(names, dict):
        return str(names.get(class_id, class_id))

    if 0 <= class_id < len(names):
        return str(names[class_id])

    return str(class_id)


def preparar_output(output_dir: Path, overwrite: bool) -> None:
    """Evita sobrescritura silenciosa del directorio de resultados."""
    if output_dir.exists() and any(output_dir.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"{output_dir} ya contiene archivos; "
                "usa --overwrite si es intencional"
            )
        shutil.rmtree(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "annotated").mkdir(parents=True, exist_ok=True)


def ejecutar_inferencia(
    model_path: Path,
    input_path: Path,
    output_dir: Path,
    *,
    device: str = "cpu",
    conf: float = 0.25,
    limit: int | None = None,
    overwrite: bool = False,
) -> dict:
    """Ejecuta inferencia y guarda outputs reproducibles de presentación."""
    if not model_path.is_file():
        raise FileNotFoundError(
            f"no existe --model: {model_path}"
        )

    if not 0.0 <= conf <= 1.0:
        raise ValueError("--conf debe estar entre 0 y 1")

    imagenes = resolver_imagenes(input_path)

    if limit is not None:
        if limit <= 0:
            raise ValueError("--limit debe ser mayor que 0")
        imagenes = imagenes[:limit]

    preparar_output(output_dir, overwrite)

    from ultralytics import YOLO

    modelo = YOLO(str(model_path))

    registros = []
    tiempos_inferencia_ms = []

    for image_path in imagenes:
        resultado = modelo.predict(
            source=str(image_path),
            device=device,
            conf=conf,
            verbose=False,
            save=False,
        )[0]

        detecciones = []

        for xyxy, confianza, clase in zip(
            resultado.boxes.xyxy.tolist(),
            resultado.boxes.conf.tolist(),
            resultado.boxes.cls.tolist(),
        ):
            class_id = int(clase)

            detecciones.append(
                {
                    "class_id": class_id,
                    "class_name": nombre_clase(
                        resultado.names,
                        class_id,
                    ),
                    "confidence": float(confianza),
                    "xyxy": [float(value) for value in xyxy],
                }
            )

        annotated_path = output_dir / "annotated" / image_path.name
        resultado.save(filename=str(annotated_path))

        speed = {
            key: float(value)
            for key, value in dict(resultado.speed).items()
        }

        inference_ms = float(speed.get("inference", 0.0))
        tiempos_inferencia_ms.append(inference_ms)

        registros.append(
            {
                "image": image_path.name,
                "source": str(image_path),
                "detections": detecciones,
                "speed_ms": speed,
                "annotated_image": str(annotated_path),
            }
        )

    promedio = (
        sum(tiempos_inferencia_ms) / len(tiempos_inferencia_ms)
        if tiempos_inferencia_ms
        else 0.0
    )

    payload = {
        "model": str(model_path),
        "model_sha256": sha256_archivo(model_path),
        "device": device,
        "conf_threshold": conf,
        "n_images": len(imagenes),
        "mean_inference_ms": promedio,
        "predictions": registros,
    }

    with (output_dir / "predictions.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            payload,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    timing = {
        "device": device,
        "n_images": len(imagenes),
        "inference_ms": tiempos_inferencia_ms,
        "mean_inference_ms": promedio,
    }

    with (output_dir / "timing_summary.json").open(
        "w",
        encoding="utf-8",
    ) as handle:
        json.dump(
            timing,
            handle,
            indent=2,
            ensure_ascii=False,
        )

    return payload


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--model",
        required=True,
        type=Path,
        help="Ruta al peso entrenado .pt",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Imagen o carpeta de imágenes",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Dispositivo de inferencia; para la demo final usar cpu",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        type=Path,
        help="Directorio de salida",
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.25,
        help="Umbral de confianza",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="M?ximo de im?genes a procesar; debe ser mayor que 0",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Permite reemplazar explícitamente un output existente",
    )

    args = parser.parse_args()

    try:
        payload = ejecutar_inferencia(
            args.model,
            args.input,
            args.output_dir,
            device=args.device,
            conf=args.conf,
            limit=args.limit,
            overwrite=args.overwrite,
        )
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print("OK: inferencia completada.")
    print(f"    device={payload['device']}")
    print(f"    imágenes={payload['n_images']}")
    print(
        "    mean_inference_ms="
        f"{payload['mean_inference_ms']:.3f}"
    )
    print(
        "    model_sha256="
        f"{payload['model_sha256']}"
    )
    print(f"    outputs={args.output_dir}")


if __name__ == "__main__":
    main()