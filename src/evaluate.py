"""
evaluate.py

Evalua un peso ya entrenado (src/train.py) sobre un split del dataset
monoclase (`0: product`), segun la interfaz congelada en
docs/governance/02_CONTRACTS/CLI_AND_EVALUATION_CONTRACT.md (TRN-001, issue #6).

Metricas (protocolo del contrato, formula declarada en metrics.json):
    precision = TP / (TP + FP)
    recall    = TP / (TP + FN)
    F1        = 2 * precision * recall / (precision + recall)
    mAP@0.5      = AP promediado sobre clases, IoU=0.5
    mAP@0.5:0.95 = AP promediado sobre clases y sobre IoU de 0.5 a 0.95 (paso 0.05)
No hay metricas por SKU: SKU no es clase (una unica clase, "product").

El split "test" queda bloqueado por defecto (--allow-test lo desbloquea
explicitamente) porque el contrato exige que el conjunto de test no se toque
para tuning y solo se habilite despues de G4.

Uso (interfaz congelada):
    python src/evaluate.py --model outputs/runs/baseline/best.pt \\
        --data configs/dataset.yaml --split test --output-dir outputs/evaluation/baseline

Sobre el fixture propio, split val (test queda bloqueado sin --allow-test):
    python src/evaluate.py --model outputs/runs/smoke/weights/best.pt \\
        --data tests/fixtures/mini_dataset/dataset.yaml --split val \\
        --output-dir outputs/evaluation/smoke
"""
import argparse
import csv
import hashlib
import json
import os
import sys

import yaml


FORMULAS = {
    "precision": "TP / (TP + FP)",
    "recall": "TP / (TP + FN)",
    "f1": "2 * precision * recall / (precision + recall)",
    "map50": "mean(AP_c para IoU=0.5, promediado sobre clases)",
    "map50_95": "mean(AP_c promediado sobre IoU=0.5:0.95 paso 0.05, sobre clases)",
}

CATEGORIAS_AUTOMATICAS = {
    "correcto": "IoU(prediccion, ground truth) >= --iou-umbral y misma clase (0)",
    "omision": "ground truth sin ninguna prediccion que la cubra con IoU suficiente",
    "falso_positivo": "prediccion sin ningun ground truth que la cubra con IoU suficiente",
}
CATEGORIAS_MANUALES_NOTA = (
    "Las categorias 'fondo_iluminacion', 'producto_recortado', "
    "'caja_automatica_deficiente' y 'dominio_no_representado' (seccion 6 del "
    "contrato) exigen inspeccion visual humana sobre datos reales -- no se "
    "infieren automaticamente de este fixture sintetico. Se completan en "
    "notebooks/analisis_errores.ipynb cuando el dataset real este disponible."
)


def sha256_de_archivo(ruta):
    h = hashlib.sha256()
    with open(ruta, "rb") as f:
        for bloque in iter(lambda: f.read(65536), b""):
            h.update(bloque)
    return h.hexdigest()


def cargar_dataset_yaml(ruta_data):
    with open(ruta_data, "r") as f:
        return yaml.safe_load(f)


def leer_gt_yolo(ruta_label):
    """Lee un .txt YOLO (contrato: exactamente 1 caja por imagen aceptada)."""
    cajas = []
    if not os.path.isfile(ruta_label):
        return cajas
    with open(ruta_label, "r") as f:
        for linea in f:
            partes = linea.strip().split()
            if len(partes) != 5:
                continue
            clase, cx, cy, w, h = partes
            cajas.append((int(clase), float(cx), float(cy), float(w), float(h)))
    return cajas


def yolo_a_xyxy(caja, img_w, img_h):
    _, cx, cy, w, h = caja
    xmin = (cx - w / 2) * img_w
    ymin = (cy - h / 2) * img_h
    xmax = (cx + w / 2) * img_w
    ymax = (cy + h / 2) * img_h
    return xmin, ymin, xmax, ymax


def iou(caja_a, caja_b):
    ax1, ay1, ax2, ay2 = caja_a
    bx1, by1, bx2, by2 = caja_b
    ix1, iy1 = max(ax1, bx1), max(ay1, by1)
    ix2, iy2 = min(ax2, bx2), min(ay2, by2)
    inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - inter
    return inter / union if union > 0 else 0.0


def construir_weight_manifest(ruta_modelo):
    return {
        "ruta": os.path.abspath(ruta_modelo),
        "sha256": sha256_de_archivo(ruta_modelo),
        "tamano_bytes": os.path.getsize(ruta_modelo),
    }


def calcular_predicciones_y_errores(modelo, carpeta_imagenes, carpeta_labels, conf, iou_umbral, device):
    from PIL import Image

    nombres = sorted(
        n for n in os.listdir(carpeta_imagenes) if n.lower().endswith((".jpg", ".jpeg", ".png"))
    )
    predicciones = []
    ejemplos = []

    for nombre in nombres:
        ruta_img = os.path.join(carpeta_imagenes, nombre)
        base = os.path.splitext(nombre)[0]
        ruta_label = os.path.join(carpeta_labels, base + ".txt")

        with Image.open(ruta_img) as im:
            img_w, img_h = im.size

        resultado = modelo.predict(source=ruta_img, device=device, conf=conf, verbose=False, save=False)[0]
        cajas_pred = []
        for xyxy, confianza, clase in zip(
            resultado.boxes.xyxy.tolist(), resultado.boxes.conf.tolist(), resultado.boxes.cls.tolist()
        ):
            cajas_pred.append({"xyxy": xyxy, "confianza": confianza, "clase": int(clase)})

        predicciones.append({"source_asset_id": base, "imagen": nombre, "predicciones": cajas_pred})

        cajas_gt = [yolo_a_xyxy(c, img_w, img_h) for c in leer_gt_yolo(ruta_label)]
        gt_cubierto = [False] * len(cajas_gt)
        pred_usada = [False] * len(cajas_pred)

        # emparejar cada GT con la mejor prediccion disponible (greedy por IoU)
        for i, caja_gt in enumerate(cajas_gt):
            mejor_iou, mejor_j = 0.0, None
            for j, p in enumerate(cajas_pred):
                if pred_usada[j]:
                    continue
                val = iou(caja_gt, tuple(p["xyxy"]))
                if val > mejor_iou:
                    mejor_iou, mejor_j = val, j
            if mejor_j is not None and mejor_iou >= iou_umbral:
                gt_cubierto[i] = True
                pred_usada[mejor_j] = True
                ejemplos.append({
                    "source_asset_id": base,
                    "categoria": "correcto",
                    "confianza": cajas_pred[mejor_j]["confianza"],
                    "iou": round(mejor_iou, 4),
                    "hipotesis": "-",
                })

        for i, cubierto in enumerate(gt_cubierto):
            if not cubierto:
                ejemplos.append({
                    "source_asset_id": base,
                    "categoria": "omision",
                    "confianza": None,
                    "iou": 0.0,
                    "hipotesis": "ground truth sin prediccion que lo cubra con IoU suficiente",
                })
        for j, usada in enumerate(pred_usada):
            if not usada:
                ejemplos.append({
                    "source_asset_id": base,
                    "categoria": "falso_positivo",
                    "confianza": cajas_pred[j]["confianza"],
                    "iou": 0.0,
                    "hipotesis": "prediccion sin ground truth que la cubra con IoU suficiente",
                })

    return predicciones, ejemplos


def seleccionar_ejemplos(ejemplos, n_por_categoria_grupo=15):
    """
    Selecciona reproduciblemente hasta 10-15 aciertos y hasta 10-15 errores
    (seccion 6 del contrato). Orden deterministico: por source_asset_id, no
    por azar. Si el fixture/dataset tiene menos ejemplos que el minimo, se
    toman todos los disponibles -- el contrato pide 10-15, no "al menos 10"
    sobre un universo mas chico.
    """
    correctos = sorted(
        (e for e in ejemplos if e["categoria"] == "correcto"),
        key=lambda e: (-e["confianza"], e["source_asset_id"]),
    )[:n_por_categoria_grupo]
    incorrectos = sorted(
        (e for e in ejemplos if e["categoria"] != "correcto"),
        key=lambda e: (e["source_asset_id"], e["categoria"]),
    )[:n_por_categoria_grupo]
    return correctos, incorrectos


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="Ruta al peso entrenado (.pt)")
    parser.add_argument("--data", required=True, help="Ruta a un dataset.yaml formato YOLO (real o fixture)")
    parser.add_argument("--split", required=True, choices=["train", "val", "test"], help="Split a evaluar")
    parser.add_argument("--output-dir", required=True, help="Carpeta de salida (metrics.json, predicciones, manifest, ejemplos de error)")
    parser.add_argument("--conf", type=float, default=0.25, help="Umbral de confianza para predicciones (declarado, no implicito)")
    parser.add_argument("--iou-umbral", type=float, default=0.5, help="Umbral de IoU para considerar una prediccion como acierto")
    parser.add_argument("--device", default="cpu")
    parser.add_argument("--allow-test", action="store_true", help="Desbloquea --split test. Solo despues de G4 -- ver brief y contrato.")
    parser.add_argument("--overwrite", action="store_true", help="Permite sobrescribir --output-dir si ya tiene metrics.json de una corrida previa")
    args = parser.parse_args()

    if args.split == "test" and not args.allow_test:
        print(
            "ERROR: --split test esta bloqueado por defecto. El contrato exige que el "
            "conjunto de test no se use para tuning y se desbloquee solo despues de G4. "
            "Si esto corre post-G4 de forma intencional, repeti el comando con --allow-test.",
            file=sys.stderr,
        )
        sys.exit(1)

    if not os.path.isfile(args.model):
        print(f"ERROR: no existe --model {args.model}", file=sys.stderr)
        sys.exit(1)
    if not os.path.isfile(args.data):
        print(f"ERROR: no existe --data {args.data}", file=sys.stderr)
        sys.exit(1)

    metrics_previas = os.path.join(args.output_dir, "metrics.json")
    if os.path.isfile(metrics_previas) and not args.overwrite:
        print(
            f"ERROR: {metrics_previas} ya existe. Este CLI no sobrescribe outputs "
            f"silenciosamente -- usa --overwrite si es intencional.",
            file=sys.stderr,
        )
        sys.exit(1)

    os.makedirs(args.output_dir, exist_ok=True)

    from ultralytics import YOLO

    modelo = YOLO(args.model)

    proyecto = os.path.dirname(os.path.abspath(args.output_dir)) or "."
    nombre = os.path.basename(os.path.abspath(args.output_dir))
    resultado = modelo.val(
        data=os.path.abspath(args.data),
        split=args.split,
        device=args.device,
        workers=0,
        conf=args.conf,
        iou=args.iou_umbral,
        project=proyecto,
        name=nombre,
        exist_ok=True,
        plots=True,
        verbose=False,
    )

    f1 = float(resultado.box.f1.mean()) if len(resultado.box.f1) else 0.0
    metricas = {
        "split": args.split,
        "conf_umbral": args.conf,
        "iou_umbral": args.iou_umbral,
        "n_imagenes": int(resultado.box.nc) if hasattr(resultado.box, "nc") else None,
        "metricas": {
            "map50": float(resultado.box.map50),
            "map50_95": float(resultado.box.map),
            "map75": float(resultado.box.map75),
            "precision": float(resultado.box.mp),
            "recall": float(resultado.box.mr),
            "f1": f1,
        },
        "formulas": FORMULAS,
        "nota_sku": "No hay metricas por SKU: SKU es metadato, no clase (unica clase 'product').",
    }
    with open(os.path.join(args.output_dir, "metrics.json"), "w") as f:
        json.dump(metricas, f, indent=2, ensure_ascii=False)

    manifest = construir_weight_manifest(args.model)
    with open(os.path.join(args.output_dir, "weight_manifest.json"), "w") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    ds = cargar_dataset_yaml(args.data)
    carpeta_base = ds.get("path", os.path.dirname(os.path.abspath(args.data)))
    carpeta_imagenes = os.path.join(carpeta_base, ds[args.split])
    carpeta_labels = carpeta_imagenes.replace(os.sep + "images" + os.sep, os.sep + "labels" + os.sep)

    predicciones, ejemplos = calcular_predicciones_y_errores(
        modelo, carpeta_imagenes, carpeta_labels, args.conf, args.iou_umbral, args.device
    )

    carpeta_pred = os.path.join(args.output_dir, "predictions")
    os.makedirs(carpeta_pred, exist_ok=True)
    with open(os.path.join(carpeta_pred, "predictions.json"), "w") as f:
        json.dump(predicciones, f, indent=2, ensure_ascii=False)

    correctos, incorrectos = seleccionar_ejemplos(ejemplos)
    ruta_ejemplos = os.path.join(args.output_dir, "error_examples.csv")
    with open(ruta_ejemplos, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["source_asset_id", "categoria", "confianza", "iou", "hipotesis"])
        writer.writeheader()
        for e in correctos + incorrectos:
            writer.writerow(e)

    with open(os.path.join(args.output_dir, "error_categories_README.txt"), "w") as f:
        f.write("Categorias automaticas:\n")
        for k, v in CATEGORIAS_AUTOMATICAS.items():
            f.write(f"  - {k}: {v}\n")
        f.write("\n" + CATEGORIAS_MANUALES_NOTA + "\n")

    print(f"OK: evaluacion terminada sobre split '{args.split}'.")
    print(f"    mAP@0.5={metricas['metricas']['map50']:.4f}  mAP@0.5:0.95={metricas['metricas']['map50_95']:.4f}  "
          f"P={metricas['metricas']['precision']:.4f}  R={metricas['metricas']['recall']:.4f}  F1={f1:.4f}")
    print(f"    metrics.json, weight_manifest.json, predictions/, error_examples.csv en {args.output_dir}")
    print(f"    aciertos seleccionados: {len(correctos)}  errores seleccionados: {len(incorrectos)}")


if __name__ == "__main__":
    main()
