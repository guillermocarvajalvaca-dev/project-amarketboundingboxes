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

```bash
python -c "import PIL, numpy, yaml; from ultralytics import YOLO; print('OK')"
```

Verificado el 2026-08-16 en venv limpio con pip 24.0. Resultado: importación correcta de
las cuatro dependencias directas y de `YOLO`.

Referencia del tamaño: el entorno completo ocupa aproximadamente **1,05 GB** y resuelve
39 paquetes a partir de las cuatro declaraciones directas. La mayor parte es `torch`.

## Dependencias

`requirements.txt` declara **solo las directas**:

| Paquete | Pin | Para qué |
|---|---|---|
| `pillow` | `12.3.0` | decodificación de imágenes, canal alfa, máscaras |
| `numpy` | `2.4.6` | operaciones sobre máscaras y extremos de píxel |
| `ultralytics` | `8.4.120` | detector YOLO: entrenamiento, evaluación e inferencia |
| `PyYAML` | `6.0.3` | lectura de los `configs/*.yaml` del contrato |

Las transitivas —`torch`, `torchvision`, `opencv`, `matplotlib`, `scipy`, `pandas` y
demás— las resuelve pip. No se pinean a mano: volcar un `pip freeze` completo congelaría
árboles que nadie declaró y volvería ilegible cualquier cambio real.

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
