# Entorno reproducible

Decisión de ENV-001 (issue #2). **Un solo mecanismo para todo el equipo**: Python con
`requirements.txt` pineado. No se usa conda, Poetry ni ningún otro gestor en paralelo:
la deriva entre integrantes es precisamente lo que este documento evita.

## Versión de Python

**3.11.9**, fijada.

En la máquina de verificación había también 3.12 disponible; se eligió 3.11 por ser la
versión con soporte más asentado en el ecosistema de visión por computador en la fecha de
resolución. Quien use otra versión debe declararlo: los pines de `requirements.txt` se
resolvieron contra 3.11.9 y no hay garantía de que resuelvan igual en otra.

## Puesta en marcha

### Windows (PowerShell)

```powershell
py -3.11 -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Si la activación falla por política de ejecución:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
```

### Linux y macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

`.venv/` está en `.gitignore`. **El entorno no se versiona**: se reconstruye desde
`requirements.txt`.

## Verificación

Dependencias de runtime:

```bash
python -c "import PIL, numpy, yaml, pandas; from ultralytics import YOLO; print('OK')"
```

Runner de pruebas gobernante:

```bash
python -m pytest -q
```

ENV-001, 2026-08-16 — evidencia histórica: verificado en venv limpio con pip 24.0.
Importación correcta de las cuatro dependencias directas de entonces y de `YOLO`. Esa
medición no cubre `pandas` ni `pytest`, que no existían en el conjunto declarado.

ENV-002, 2026-08-19: verificado sobre ese mismo `.venv`, con Python **3.11.9** y pip 24.0.
Resultados observados:

| Comprobación | Resultado | Exit code |
|---|---|---|
| `sys.version` | `3.11.9` | 0 |
| `pandas.__version__` | `3.0.5` | 0 |
| `pytest.__version__` | `9.1.1` | 0 |
| `pip check` | «No broken requirements found» | 0 |
| `python -m pytest -q` | 25 passed, 3 warnings | 0 |

`pandas 3.0.5` y `pytest 9.1.1` son por tanto compatibles con Python 3.11.9 en este
entorno; `pandas` se instaló desde el wheel `pandas-3.0.5-cp311-cp311-win_amd64.whl`.

Transitivas que resolvió la instalación, **ninguna declarada como directa**:

- de `pandas`: `tzdata 2026.3`.
- de `pytest`: `colorama 0.4.6`, `iniconfig 2.3.0`, `pluggy 1.6.0`, `Pygments 2.21.0`.
  `packaging 26.3` ya estaba satisfecha por el árbol previo.

Referencia del tamaño: en la medición de ENV-001 el entorno ocupaba aproximadamente
**1,05 GB** y resolvía 39 paquetes desde cuatro declaraciones directas. Medido de nuevo
tras ENV-002 ocupa aproximadamente **1,2 GB** y `pip list` enumera 48 paquetes —`pip`
incluido— desde seis declaraciones directas. La mayor parte sigue siendo `torch`.

## Dependencias

`requirements.txt` declara **solo las directas**, y son **seis**:

| Paquete | Pin | Rol | Para qué |
|---|---|---|---|
| `pillow` | `12.3.0` | runtime | decodificación de imágenes, canal alfa, máscaras |
| `numpy` | `2.4.6` | runtime | operaciones sobre máscaras y extremos de píxel |
| `ultralytics` | `8.4.120` | runtime | detector YOLO: entrenamiento, evaluación e inferencia |
| `PyYAML` | `6.0.3` | runtime | lectura de los `configs/*.yaml` del contrato |
| `pandas` | `3.0.5` | runtime/datos | manipulación tabular de manifests y splits; la requiere SPL-001 |
| `pytest` | `9.1.1` | pruebas | runner gobernante: es el que ejecuta la suite que cierra un gate |

`pytest` es una dependencia **directa**, no de desarrollo aparte. El proceso de validación
gobernante lo invoca explícitamente, y ENV-001 fijó un mecanismo único para todo el
equipo: no se introduce `requirements-dev.txt` ni ningún gestor en paralelo.

Las transitivas —`torch`, `torchvision`, `opencv`, `matplotlib`, `scipy`, `tzdata`,
`colorama`, `iniconfig`, `pluggy`, `Pygments` y demás— las resuelve pip. No se pinean a
mano: volcar un `pip freeze` completo congelaría árboles que nadie declaró y volvería
ilegible cualquier cambio real.

`requests` **no** se incluye. El contrato de scraping es *stdlib-first*: la adquisición se
implementa con la biblioteca estándar.

## PyTorch en CPU

La guía exige demostrar inferencia en CPU, sin CUDA. En Windows, el wheel por defecto de
PyPI que arrastra `ultralytics` es la build de CPU:

```
torch 2.13.0+cpu
torch.cuda.is_available() -> False
```

Es el comportamiento deseado y no requiere acción. Quien entrene en GPU debe instalar el
wheel CUDA correspondiente **por su cuenta y declararlo**, sin modificar
`requirements.txt`: el entorno declarado es el de CPU, y es el que debe reproducirse para
evaluar.

## Dispositivo de la ejecución gobernante

Nota añadida por GOV-002 (issue #21). Alcance limitado: fija **en qué dispositivo** corre
la ejecución que se presenta como resultado del proyecto. **No cambia dependencias ni
versiones**; `requirements.txt` y los pines de la tabla anterior quedan intactos.

Llamamos *ejecución gobernante* a la que produce los pesos, las métricas y las curvas que
se entregan como evidencia de gate. Se distingue de la exploración local, que cada
integrante hace donde quiera y que no cierra ningún gate.

- **La ejecución gobernante se realiza en CPU.** Es la única configuración cubierta por la
  verificación de este documento y la única que los cuatro integrantes pueden reproducir
  con el entorno declarado.
- **Apple MPS no debe utilizarse para la ejecución gobernante de G4.** El backend
  `torch.device("mps")` no está cubierto por los pines verificados aquí —la verificación
  del 2026-08-16 se hizo sobre la build `+cpu` en Windows— y el §8 del contrato SDD exige
  que `evaluate.py`, sobre el mismo peso y el mismo split, produzca métricas idénticas.
  Una métrica producida en MPS no es reproducible por quien evalúa, de modo que no
  satisface esa condición y no puede presentarse como evidencia de gate. MPS queda
  admitido solo para exploración local.
- CUDA mantiene el tratamiento ya descrito en «PyTorch en CPU»: quien entrene en GPU
  instala el wheel por su cuenta y lo declara, sin tocar `requirements.txt`.
- Toda ejecución gobernante **registra el dispositivo efectivo en su log**. Un run cuyo
  dispositivo no conste en el log no satisface la Definition of Done del manual operativo,
  con independencia de las métricas que reporte.

Comando para dejar constancia del dispositivo antes de un run gobernante:

```bash
python -c "import torch; print(torch.__version__, torch.cuda.is_available(), torch.backends.mps.is_available())"
```

`NOT RUN` en GOV-002: esta nota fija la restricción, no ejecuta la comprobación. G4 sigue
bloqueado y ninguna ejecución de entrenamiento está autorizada todavía.

## Toolchain de LaTeX

El informe se compila con `pdflatex`. Basta cualquiera de estas dos opciones:

**MiKTeX** — requiere habilitar la instalación automática de paquetes, o la compilación se
queda colgada esperando un diálogo que en shell no interactivo nunca llega:

```powershell
initexmf --set-config-value "[MPM]AutoInstall=1"
```

**TeX Live completo** — trae los paquetes necesarios y no requiere configuración extra.

Compilación, desde `informe/`:

```bash
pdflatex -interaction=nonstopmode main.tex
```

Se necesitan **tres pasadas** para estabilizar las referencias cruzadas y `hyperref`.
Paquetes requeridos por el documento: `babel-spanish`, `booktabs`, `graphicx`, `amsmath`,
`hyperref`.

Los artefactos de compilación (`.aux`, `.log`, `.out`, `.pdf`) están en `.gitignore`. El
PDF se genera; no se versiona.

## Cambiar el entorno

Cualquier cambio de versión de Python, alta de una dependencia directa o modificación de
un pin exige:

1. Verificación empírica en un venv limpio.
2. Actualización de este documento y de `requirements.txt` en el mismo PR.
3. Revisión cruzada, como cualquier otro artefacto.

Añadir una dependencia por conveniencia local, sin declararla, rompe la reproducibilidad
que sostiene 22 puntos de la rúbrica.
