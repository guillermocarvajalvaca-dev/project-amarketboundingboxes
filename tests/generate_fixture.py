"""
generate_fixture.py

Genera un dataset fixture propio, chico y determinista, en formato YOLO
monoclase (`0: product`), para validar la interfaz de `src/train.py` y
`src/evaluate.py` (issue #6, TRN-001) mientras el dataset real todavia no
existe (BOX-001/SPL-001 sin empezar).

No es el dataset del proyecto. Es sintetico: cada imagen es un rectangulo de
color solido (el "producto") pegado en una posicion conocida sobre un fondo
de color solido distinto, generado con PIL+numpy y semilla fija. Como la
posicion del rectangulo se elige antes de dibujarlo, la caja YOLO es exacta
por construccion -- no hace falta ningun detector de bordes para el fixture.

Uso:
    python tests/generate_fixture.py --salida tests/fixtures/mini_dataset --semilla 42
"""
import argparse
import os
import random

import numpy as np
from PIL import Image

IMG_SIZE = 64  # imagenes chicas a proposito -- esto es un fixture de CLI, no un dataset real
CLASE_ID = 0   # unica clase del contrato: 0 = product


def generar_imagen_y_caja(rng, tamano=IMG_SIZE):
    """
    Dibuja un rectangulo ("producto") de color solido en una posicion
    aleatoria (pero con rng seedeado) sobre un fondo de otro color solido.
    Devuelve (imagen PIL, (xmin, ymin, xmax, ymax)) en pixeles absolutos.
    """
    color_fondo = tuple(rng.integers(180, 255, size=3).tolist())
    color_producto = tuple(rng.integers(0, 80, size=3).tolist())  # bien distinto del fondo

    w = rng.integers(tamano // 4, tamano // 2)
    h = rng.integers(tamano // 4, tamano // 2)
    xmin = rng.integers(2, tamano - w - 2)
    ymin = rng.integers(2, tamano - h - 2)
    xmax, ymax = xmin + w, ymin + h

    arr = np.full((tamano, tamano, 3), color_fondo, dtype=np.uint8)
    arr[ymin:ymax, xmin:xmax] = color_producto
    return Image.fromarray(arr), (int(xmin), int(ymin), int(xmax), int(ymax))


def caja_a_yolo(caja, tamano=IMG_SIZE):
    xmin, ymin, xmax, ymax = caja
    cx = (xmin + xmax) / 2 / tamano
    cy = (ymin + ymax) / 2 / tamano
    w = (xmax - xmin) / tamano
    h = (ymax - ymin) / tamano
    return cx, cy, w, h


def generar_split(rng, carpeta_salida, split, n, indice_inicial):
    dir_img = os.path.join(carpeta_salida, "images", split)
    dir_lbl = os.path.join(carpeta_salida, "labels", split)
    os.makedirs(dir_img, exist_ok=True)
    os.makedirs(dir_lbl, exist_ok=True)

    for i in range(n):
        idx = indice_inicial + i
        nombre = f"fixture_{idx:04d}"
        img, caja = generar_imagen_y_caja(rng)
        img.save(os.path.join(dir_img, f"{nombre}.jpg"))

        cx, cy, w, h = caja_a_yolo(caja)
        with open(os.path.join(dir_lbl, f"{nombre}.txt"), "w") as f:
            f.write(f"{CLASE_ID} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}\n")

    return indice_inicial + n


def escribir_dataset_yaml(carpeta_salida):
    # `path` absoluto a proposito: ultralytics resuelve rutas relativas de
    # `path` contra el directorio de trabajo del proceso, no contra la
    # carpeta del propio dataset.yaml -- con ruta relativa, corridas desde
    # otro cwd rompian silenciosamente. Este dataset.yaml lo regenera
    # generate_fixture.py en cada maquina, no se versiona el path de nadie
    # mas (ver .gitignore de tests/fixtures/).
    ruta_absoluta = os.path.abspath(carpeta_salida)
    contenido = (
        "# Fixture propio de CLI (TRN-001) -- NO es el dataset real del proyecto.\n"
        "# Generado por tests/generate_fixture.py, semilla fija, monoclase.\n"
        "# path absoluto: se regenera por maquina, no depende del cwd de quien entrena.\n"
        f"path: {ruta_absoluta}\n"
        "train: images/train\n"
        "val: images/val\n"
        "test: images/test\n"
        "names:\n"
        "  0: product\n"
    )
    with open(os.path.join(carpeta_salida, "dataset.yaml"), "w") as f:
        f.write(contenido)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", default="tests/fixtures/mini_dataset")
    parser.add_argument("--semilla", type=int, default=42)
    parser.add_argument("--n-train", type=int, default=8)
    parser.add_argument("--n-val", type=int, default=4)
    parser.add_argument("--n-test", type=int, default=4)
    args = parser.parse_args()

    random.seed(args.semilla)
    rng = np.random.default_rng(args.semilla)

    os.makedirs(args.salida, exist_ok=True)
    idx = 0
    idx = generar_split(rng, args.salida, "train", args.n_train, idx)
    idx = generar_split(rng, args.salida, "val", args.n_val, idx)
    idx = generar_split(rng, args.salida, "test", args.n_test, idx)
    escribir_dataset_yaml(args.salida)

    total = args.n_train + args.n_val + args.n_test
    print(f"Fixture generado en {args.salida}: {total} imagenes "
          f"({args.n_train} train / {args.n_val} val / {args.n_test} test), clase unica 'product'.")


if __name__ == "__main__":
    main()
