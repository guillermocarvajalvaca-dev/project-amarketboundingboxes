"""
train.py

Entrena el detector baseline (YOLO11n, transfer learning desde COCO) sobre el
dataset monoclase (`0: product`) del proyecto, segun la interfaz congelada en
docs/governance/02_CONTRACTS/CLI_AND_EVALUATION_CONTRACT.md (TRN-001, issue #6).

Fase actual (G2, interfaz): se corre contra un dataset fixture propio
(tests/fixtures/mini_dataset, generado por tests/generate_fixture.py), NO
contra el dataset real -- BOX-001/SPL-001 todavia no lo producen. El
entrenamiento final sobre datos reales pertenece a G4 y exige baseline,
versiones y hardware ya congelados (ver brief de Pablo).

Todos los hiperparametros viven en el YAML de --config (nunca embebidos en
este archivo); la unica excepcion es --seed, que puede sobreescribir el valor
del config para dejar explicito con que semilla se corrio cada experimento.

Uso (interfaz congelada):
    python src/train.py --config configs/baseline.yaml --data configs/dataset.yaml \\
        --output-dir outputs/runs/baseline --seed 42

Smoke train sobre el fixture propio:
    python src/train.py --config configs/baseline.yaml \\
        --data tests/fixtures/mini_dataset/dataset.yaml \\
        --output-dir outputs/runs/smoke --seed 42 --smoke
"""
import argparse
import csv
import json
import os
import platform
import random
import shutil
import subprocess
import sys

import numpy as np
import yaml


def cargar_config(ruta_config):
    with open(ruta_config, "r") as f:
        return yaml.safe_load(f)


def resolver_hiperparametros(config, args):
    """
    Combina configs/baseline.yaml con los overrides explicitos de CLI
    (--seed, --smoke) en un unico diccionario de hiperparametros efectivos
    -- esto es lo que se vuelca despues en resolved_config.yaml, para que
    "que se corrio" nunca dependa de leer el codigo.
    """
    resuelto = {
        "modelo": config["modelo"],
        "epochs": config["epochs"],
        "imgsz": config["imgsz"],
        "batch": config["batch"],
        "device": config["device"],
        "optimizer": config.get("optimizer", "auto"),
        "lr0": config.get("lr0"),
        "seed": args.seed if args.seed is not None else config["seed"],
        "augment": config.get("augment", False),
        "mosaic": config.get("mosaic", 0.0),
        "hsv_h": config.get("hsv_h", 0.0),
        "hsv_s": config.get("hsv_s", 0.0),
        "hsv_v": config.get("hsv_v", 0.0),
        "fliplr": config.get("fliplr", 0.0),
        "flipud": config.get("flipud", 0.0),
        "smoke": bool(args.smoke),
    }
    if args.smoke:
        smoke_cfg = config.get("smoke", {})
        resuelto["epochs"] = smoke_cfg.get("epochs", 1)
        resuelto["imgsz"] = smoke_cfg.get("imgsz", 64)
        resuelto["batch"] = smoke_cfg.get("batch", 2)
    resuelto["data"] = args.data
    resuelto["config_fuente"] = os.path.abspath(args.config)
    return resuelto


def fijar_semillas(seed):
    os.environ.setdefault("PYTHONHASHSEED", str(seed))
    random.seed(seed)
    np.random.seed(seed)
    try:
        import torch
        torch.manual_seed(seed)
    except ImportError:
        pass


def obtener_commit_git():
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except Exception:
        return None


def version_paquete(nombre):
    try:
        from importlib.metadata import version
        return version(nombre)
    except Exception:
        return None


def registrar_entorno(seed_efectiva, pythonhashseed_previo):
    import torch

    return {
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "processor": platform.processor(),
        "git_commit": obtener_commit_git(),
        "paquetes": {
            "torch": version_paquete("torch"),
            "torchvision": version_paquete("torchvision"),
            "ultralytics": version_paquete("ultralytics"),
            "numpy": version_paquete("numpy"),
            "pillow": version_paquete("pillow"),
            "pyyaml": version_paquete("PyYAML"),
        },
        "hardware": {
            "cuda_available": torch.cuda.is_available(),
            "mps_available": torch.backends.mps.is_available(),
        },
        "determinismo": {
            "seed": seed_efectiva,
            "pythonhashseed_declarado_antes_de_correr": pythonhashseed_previo,
            "nota": (
                "PYTHONHASHSEED solo tiene efecto si se fija ANTES de arrancar "
                "el interprete; si no venia seteado en el entorno, este script "
                "lo fija para procesos hijos pero no para si mismo -- registrar "
                "esa limitacion es preferible a aparentar un determinismo que "
                "no se cumple."
            ),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", required=True, help="Ruta a configs/baseline.yaml (hiperparametros)")
    parser.add_argument("--data", required=True, help="Ruta a un dataset.yaml formato YOLO (real o fixture)")
    parser.add_argument("--output-dir", required=True, help="Carpeta de salida (pesos, config resuelta, entorno, curvas, logs)")
    parser.add_argument("--seed", type=int, default=None, help="Sobrescribe la semilla de --config si se pasa")
    parser.add_argument("--smoke", action="store_true", help="Corrida minima (pocas epocas/imgsz chico) para validar la interfaz, no un entrenamiento real")
    parser.add_argument("--overwrite", action="store_true", help="Permite sobrescribir --output-dir si ya tiene pesos de una corrida previa")
    args = parser.parse_args()

    if not os.path.isfile(args.config):
        print(f"ERROR: no existe --config {args.config}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.data):
        print(f"ERROR: no existe --data {args.data}", file=sys.stderr)
        sys.exit(1)

    pesos_previos = os.path.join(args.output_dir, "weights", "best.pt")
    if os.path.isfile(pesos_previos) and not args.overwrite:
        print(
            f"ERROR: {pesos_previos} ya existe. Este CLI no sobrescribe outputs "
            f"silenciosamente (convencion del contrato) -- usa --overwrite si es intencional.",
            file=sys.stderr,
        )
        sys.exit(1)

    pythonhashseed_previo = os.environ.get("PYTHONHASHSEED")

    config = cargar_config(args.config)
    hp = resolver_hiperparametros(config, args)
    fijar_semillas(hp["seed"])

    os.makedirs(args.output_dir, exist_ok=True)

    with open(os.path.join(args.output_dir, "resolved_config.yaml"), "w") as f:
        yaml.safe_dump(hp, f, sort_keys=False, allow_unicode=True)

    entorno = registrar_entorno(hp["seed"], pythonhashseed_previo)
    with open(os.path.join(args.output_dir, "environment.json"), "w") as f:
        json.dump(entorno, f, indent=2, ensure_ascii=False)

    from ultralytics import YOLO

    proyecto = os.path.dirname(os.path.abspath(args.output_dir)) or "."
    nombre = os.path.basename(os.path.abspath(args.output_dir))

    modelo = YOLO(hp["modelo"])
    modelo.train(
        data=os.path.abspath(args.data),
        epochs=hp["epochs"],
        imgsz=hp["imgsz"],
        batch=hp["batch"],
        device=hp["device"],
        optimizer=hp["optimizer"],
        lr0=hp["lr0"] if hp["lr0"] is not None else 0.01,
        seed=hp["seed"],
        augment=hp["augment"],
        mosaic=hp["mosaic"],
        hsv_h=hp["hsv_h"],
        hsv_s=hp["hsv_s"],
        hsv_v=hp["hsv_v"],
        fliplr=hp["fliplr"],
        flipud=hp["flipud"],
        project=proyecto,
        name=nombre,
        exist_ok=True,
        workers=0,  # determinismo -- sin paralelismo de dataloader que reordene lotes
        verbose=False,
    )

    # ultralytics ya escribe results.csv y results.png en output_dir; el
    # contrato pide train_log.csv explicitamente -- lo dejamos con ese nombre
    # tambien, sin borrar el original.
    results_csv = os.path.join(args.output_dir, "results.csv")
    train_log = os.path.join(args.output_dir, "train_log.csv")
    if os.path.isfile(results_csv):
        shutil.copyfile(results_csv, train_log)

    pesos_finales = os.path.join(args.output_dir, "weights", "best.pt")
    if not os.path.isfile(pesos_finales):
        print(f"ERROR: entrenamiento termino pero no se encontraron pesos en {pesos_finales}", file=sys.stderr)
        sys.exit(1)

    print(f"OK: entrenamiento terminado. Pesos en {pesos_finales}")
    print(f"    resolved_config.yaml, environment.json, train_log.csv y curvas en {args.output_dir}")


if __name__ == "__main__":
    main()
