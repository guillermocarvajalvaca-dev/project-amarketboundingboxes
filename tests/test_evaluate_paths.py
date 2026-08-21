"""
test_evaluate_paths.py

Prueba unitaria focalizada para issue #15 (punto 2): resolver_carpeta_labels
(src/evaluate.py) debe derivar la carpeta de labels a partir de la de
imagenes de forma independiente del separador de rutas del SO.

El bug original comparaba contra os.sep: en Windows, os.path.join solo
inserta el separador nativo entre carpeta_base y el segundo argumento, sin
reescribir los '/' que ya trae el string -- si dataset.yaml declara
"images/val" (con '/' literal, como lo escribe tests/generate_fixture.py),
el path resultante en Windows queda con separadores mezclados
("...\\mini_dataset\\images/val") y la comparacion contra "\\images\\" nunca
matchea. El fallo es silencioso: leer_gt_yolo() devuelve lista vacia cuando
el .txt no existe (por diseno, para imagenes sin caja), asi que la
evaluacion corria "bien" pero contra cero ground truth reales.

Esta prueba reproduce el caso Windows inyectando pathlib.PureWindowsPath, sin
necesitar una maquina Windows real. La verificacion final en Windows con
Python 3.11.9 (alcance declarado del issue #15) la hace el reviewer.

No importa torch/ultralytics -- src/evaluate.py solo los importa dentro de
main(), asi que este test es liviano y rapido.

Uso:
    python tests/test_evaluate_paths.py -v
"""
import os
import sys
import unittest
from pathlib import PurePosixPath, PureWindowsPath

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if RAIZ not in sys.path:
    sys.path.insert(0, RAIZ)

from src.evaluate import resolver_carpeta_labels  # noqa: E402


class TestResolverCarpetaLabels(unittest.TestCase):

    def test_posix_separadores_consistentes(self):
        ruta = "/tmp/fixture/images/val"
        self.assertEqual(
            resolver_carpeta_labels(ruta, clase_ruta=PurePosixPath),
            "/tmp/fixture/labels/val",
        )

    def test_windows_separadores_mixtos_bug_original(self):
        # Reproduce exactamente el bug: os.path.join(base_windows, "images/val")
        # deja el ultimo tramo con '/' aunque el resto use '\\'.
        ruta = r"C:\Users\pablo\mini_dataset\images/val"
        self.assertEqual(
            resolver_carpeta_labels(ruta, clase_ruta=PureWindowsPath),
            r"C:\Users\pablo\mini_dataset\labels\val",
        )

    def test_windows_separadores_consistentes(self):
        ruta = r"C:\Users\pablo\mini_dataset\images\val"
        self.assertEqual(
            resolver_carpeta_labels(ruta, clase_ruta=PureWindowsPath),
            r"C:\Users\pablo\mini_dataset\labels\val",
        )

    def test_sin_segmento_images_falla_ruidosamente(self):
        # Antes: 0 ground truth silencioso. Ahora: error explicito, no
        # una carpeta de labels inventada.
        with self.assertRaises(ValueError):
            resolver_carpeta_labels("/tmp/fixture/pics/val", clase_ruta=PurePosixPath)

    def test_default_usa_path_nativo_del_so_actual(self):
        # Sin clase_ruta explicita (como la usa evaluate.main()), debe
        # funcionar igual con las rutas nativas del SO donde corre esto.
        ruta = os.path.join(RAIZ, "images", "val")
        esperado = os.path.join(RAIZ, "labels", "val")
        self.assertEqual(resolver_carpeta_labels(ruta), esperado)


if __name__ == "__main__":
    unittest.main()
