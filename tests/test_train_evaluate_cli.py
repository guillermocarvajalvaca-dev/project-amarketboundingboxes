"""
test_train_evaluate_cli.py

Prueba de interfaz para TRN-001 (issue #6): corre src/train.py y
src/evaluate.py como subprocesos reales (no importa sus funciones), igual
que los correria cualquier integrante desde la terminal, contra un dataset
fixture propio generado en un directorio temporal (nunca contra datos
reales -- BOX-001/SPL-001 todavia no los producen).

Cubre los criterios de aceptacion de la fase de interfaz del issue #6:
    - `--help` de ambos CLIs devuelve codigo 0.
    - Smoke train pasa sobre el fixture propio.
    - Evaluacion repetida sobre el mismo peso produce metricas identicas.
    - `--split test` esta bloqueado sin `--allow-test`.

Usa unicamente unittest (stdlib) a proposito -- no declara pytest ni ninguna
otra dependencia nueva por fuera de lo que ya fijo ENV-001.

Uso:
    python -m unittest tests/test_train_evaluate_cli.py -v
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PYTHON = sys.executable


def correr(comando, cwd=RAIZ):
    return subprocess.run(comando, cwd=cwd, capture_output=True, text=True)


class TestInterfazCLI(unittest.TestCase):
    """--help debe funcionar sin dataset, sin pesos y sin red."""

    def test_train_help(self):
        r = correr([PYTHON, "src/train.py", "--help"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--config", r.stdout)
        self.assertIn("--seed", r.stdout)

    def test_evaluate_help(self):
        r = correr([PYTHON, "src/evaluate.py", "--help"])
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("--split", r.stdout)


class TestSmokeTrainYEvaluate(unittest.TestCase):
    """
    Genera un fixture propio en un dir temporal, entrena en modo --smoke y
    evalua el peso resultante -- exactamente el flujo que exige el brief
    ("Implementar --help y smoke train en src/train.py") antes de que el
    dataset real este disponible.
    """

    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="trn001_fixture_")
        cls.fixture_dir = os.path.join(cls.tmp, "mini_dataset")
        cls.output_train = os.path.join(cls.tmp, "runs", "smoke")
        cls.output_eval_a = os.path.join(cls.tmp, "eval", "run_a")
        cls.output_eval_b = os.path.join(cls.tmp, "eval", "run_b")

        r = correr([
            PYTHON, "tests/generate_fixture.py",
            "--salida", cls.fixture_dir, "--semilla", "42",
        ])
        assert r.returncode == 0, f"no se pudo generar el fixture:\n{r.stderr}"
        cls.dataset_yaml = os.path.join(cls.fixture_dir, "dataset.yaml")

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def test_01_smoke_train_produce_artefactos_contractuales(self):
        r = correr([
            PYTHON, "src/train.py",
            "--config", "configs/baseline.yaml",
            "--data", self.dataset_yaml,
            "--output-dir", self.output_train,
            "--seed", "42",
            "--smoke",
        ])
        self.assertEqual(r.returncode, 0, r.stderr)

        pesos = os.path.join(self.output_train, "weights", "best.pt")
        self.assertTrue(os.path.isfile(pesos), "faltan los pesos entrenados")
        for nombre in ("resolved_config.yaml", "environment.json", "train_log.csv", "results.png"):
            ruta = os.path.join(self.output_train, nombre)
            self.assertTrue(os.path.isfile(ruta), f"falta el artefacto contractual {nombre}")

    def test_02_train_no_sobrescribe_sin_overwrite(self):
        # depende de que el test anterior ya haya entrenado en self.output_train
        r = correr([
            PYTHON, "src/train.py",
            "--config", "configs/baseline.yaml",
            "--data", self.dataset_yaml,
            "--output-dir", self.output_train,
            "--seed", "42",
            "--smoke",
        ])
        self.assertNotEqual(r.returncode, 0, "deberia rechazar pisar un output-dir con pesos existentes")

    def test_03_evaluar_split_test_bloqueado_sin_allow_test(self):
        pesos = os.path.join(self.output_train, "weights", "best.pt")
        r = correr([
            PYTHON, "src/evaluate.py",
            "--model", pesos,
            "--data", self.dataset_yaml,
            "--split", "test",
            "--output-dir", os.path.join(self.tmp, "eval_test_bloqueado"),
        ])
        self.assertNotEqual(r.returncode, 0, "split test no deberia correr sin --allow-test")

    def test_04_evaluacion_repetida_sobre_mismo_peso_es_identica(self):
        pesos = os.path.join(self.output_train, "weights", "best.pt")

        for output_dir in (self.output_eval_a, self.output_eval_b):
            r = correr([
                PYTHON, "src/evaluate.py",
                "--model", pesos,
                "--data", self.dataset_yaml,
                "--split", "val",
                "--output-dir", output_dir,
            ])
            self.assertEqual(r.returncode, 0, r.stderr)

        with open(os.path.join(self.output_eval_a, "metrics.json")) as f:
            metrics_a = json.load(f)
        with open(os.path.join(self.output_eval_b, "metrics.json")) as f:
            metrics_b = json.load(f)

        self.assertEqual(metrics_a["metricas"], metrics_b["metricas"],
                          "la evaluacion repetida sobre el mismo peso debe coincidir")

        manifest_a = os.path.join(self.output_eval_a, "weight_manifest.json")
        manifest_b = os.path.join(self.output_eval_b, "weight_manifest.json")
        with open(manifest_a) as f:
            hash_a = json.load(f)["sha256"]
        with open(manifest_b) as f:
            hash_b = json.load(f)["sha256"]
        self.assertEqual(hash_a, hash_b, "el hash del mismo peso debe ser identico entre corridas")

        for output_dir in (self.output_eval_a, self.output_eval_b):
            self.assertTrue(os.path.isfile(os.path.join(output_dir, "error_examples.csv")))
            self.assertTrue(os.path.isfile(os.path.join(output_dir, "predictions", "predictions.json")))


if __name__ == "__main__":
    unittest.main()
