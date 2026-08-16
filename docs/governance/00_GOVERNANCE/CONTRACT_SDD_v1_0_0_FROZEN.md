# Contrato SDD — Project AmarketBoundingBoxes v1.0.0 — FROZEN

Este es un acuerdo académico-operativo, no un contrato legal.

## 1. Partes

- Guillermo Carvajal Vaca: coordinación, gobierno, integración y reproducibilidad.
- Monserrat Barba: adquisición, validación y documentación de datos.
- Andrés Poiche: generación de cajas, dataset YOLO, splits y EDA.
- Pablo Linares: fine-tuning, evaluación y análisis de errores.

La propiedad exacta está en `RACI_AND_ARTIFACT_MATRIX.md`.

## 2. Problema y objetivo

El proyecto construirá de forma colaborativa un dataset propio de productos de
Amarket. Para cada imagen aceptada con un producto aislado se identificará el primer
plano mediante un algoritmo básico, se registrarán `x_min`, `y_min`, `x_max`,
`y_max` y se generará una etiqueta YOLO relativa al tamaño original.

El entrenamiento de un detector preentrenado es la validación downstream exigida por
la rúbrica. No redefine el proyecto como identificación de SKU ni como checkout.

## 3. Alcance obligatorio

### MUST

- Extraer imágenes principales, nombre, descripción, SKU y URLs públicas de Amarket.
- Conservar procedencia, fecha, estado HTTP, dimensiones y SHA-256 en un manifest.
- Aceptar inicialmente una imagen solo si contiene un producto aislado y fondo
  transparente o suficientemente uniforme.
- Generar exactamente una caja YOLO monoclase por cada imagen aceptada.
- Usar `class_id=0` y `class_name=product` en todo el dataset.
- Mantener SKU, nombre y descripción como metadatos, nunca como clase.
- Separar adquisición, validación, cajas, splits, entrenamiento, evaluación e
  inferencia mediante contratos explícitos.
- Producir `src/train.py`, `src/evaluate.py`, `src/predict.py` con `argparse` y rutas
  relativas; el entrenamiento final corre sin abrir Jupyter.
- Producir `notebooks/inferencia_cpu.ipynb` y probarlo sin CUDA.
- Fijar entorno, semillas, configuraciones y evidencia de ejecución.
- Entregar informe LaTeX de 4–6 páginas, fuente y PDF, README y demo colaborativa.
- Mantener datasets y pesos grandes fuera de GitHub.

### MUST NOT

- Automatizar carrito, checkout, pago, login ni áreas privadas de Amarket.
- Evadir CAPTCHA, bloqueos, límites, robots o controles de acceso.
- Extraer datos personales, cookies, credenciales, precios o stock como requisito.
- Tratar SKU o nombres de productos como clases YOLO.
- Introducir escenas multiproducto, identificación fine-grained o RPC como dataset
  central sin un cambio contractual aprobado.
- Forzar una caja sobre imágenes con máscara vacía, fondo complejo o varios productos.
- Ajustar modelos o umbrales mirando el conjunto de test.
- Reemplazar scripts obligatorios con notebooks.
- Fusionar un artefacto sin revisor distinto del autor.
- Presentar código generado por otra persona o IA como autoría individual no declarada.

## 4. Arquitectura por capas

| Capa | Módulo | Entrada | Salida | Owner |
|---|---|---|---|---|
| Adquisición | `src/scraper_extraction.py` | URL/config Amarket | imágenes + manifest | Monserrat |
| Validación | `src/data/validate_downloads.py` | descargas | aceptados/rechazos | Monserrat |
| Anotación | `src/data/make_boxes.py` | aceptados + manifest | labels YOLO + auditoría | Andrés |
| Partición | `src/data/make_splits.py` | imágenes/labels | train/val/test + dataset YAML | Andrés |
| Entrenamiento | `src/train.py` | dataset congelado | pesos + curvas + logs | Pablo |
| Evaluación | `src/evaluate.py` | peso + test bloqueado | métricas + predicciones | Pablo |
| Inferencia | `src/predict.py` | peso + imagen/carpeta | detecciones visuales/JSON | Guillermo |
| Integración | README, notebook CPU, informe | artefactos aprobados | entrega reproducible | Guillermo |

Un módulo consumidor no corrige silenciosamente la salida del proveedor. Abre issue y
devuelve el handoff con evidencia.

## 5. Contrato de etiqueta

Una etiqueta válida contiene:

```text
0 x_center y_center width height
```

Los cuatro valores se expresan con seis decimales y cumplen:

```text
0 <= x_center <= 1
0 <= y_center <= 1
0 < width <= 1
0 < height <= 1
```

La normalización se realiza contra `W,H` originales. Los extremos inclusivos se
convierten a bordes semiabiertos mediante `x1=x_max+1`, `y1=y_max+1`.

## 6. Política de split y fuga

- La clase única debe existir en todos los splits.
- Una misma `sku_id`, imagen fuente, hash exacto, grupo perceptual o derivado no puede
  cruzar splits.
- La división se realiza por grupos antes de cualquier aumentación.
- El test queda bloqueado hasta congelar modelo, configuración y pesos.
- Si no hay suficientes grupos SKU para los tres splits, G3 se detiene; no se crea
  independencia artificial mediante copias o aumentaciones.

## 7. Estados y gates

- `PROPOSED`: especificado, sin aprobación.
- `APPROVED`: aceptado para implementación.
- `IMPLEMENTED`: existe en commit identificable.
- `EXECUTED`: fue ejecutado y generó evidencia.
- `PASSED`: cumplió todos los criterios del gate.
- `BLOCKED`: falta decisión, acceso o evidencia indispensable.

Solo `PASSED` permite continuar a una fase dependiente.

## 8. Reproducibilidad mínima

- Elegir un único mecanismo: `requirements.txt` o `environment.yml`.
- Fijar versiones utilizadas y semilla contractual.
- Registrar Python, framework, CPU/GPU y configuración resuelta.
- `evaluate.py` sobre el mismo peso/split debe producir métricas idénticas.
- La repetición del entrenamiento se evalúa con una tolerancia declarada; no se
  promete identidad bit a bit en CUDA sin demostrarla.
- README probado por alguien que no escribió esas instrucciones.

## 9. Trabajo colaborativo verificable

Cada tarea incluye `task_id`, owner, reviewer, entradas, salidas, comandos, pruebas,
evidencia y `done_when`. El historial Git, PR, ledger y revisión deben demostrar la
contribución individual. Guillermo puede integrar, pero no sustituir la implementación
de los demás.

## 10. Control de cambios y Stop-the-Line

Se detiene el avance ante autoridad contradictoria, fuga, secretos, uso sin derechos,
prueba crítica fallida, output fuera de contrato, métrica sin protocolo o resultado no
reproducible. Todo cambio contractual exige ADR, análisis de impacto, aprobación
expresa del coordinador, nueva versión y reejecución de gates dependientes. El owner
afectado debe ser informado y puede registrar objeciones técnicas; la decisión de fase
corresponde al coordinador.

## 11. Aprobación y autoridad de fase

Guillermo Carvajal Vaca, como coordinador y líder, es la autoridad suficiente para
congelar el contrato y autorizar cada fase. Los demás integrantes deben conocer su
brief, ejecutar únicamente sus artefactos y dejar evidencia individual, pero su
acknowledgement no es una precondición para iniciar una fase autorizada.

La aceptación registrada el 2026-08-16 congela `v1.0.0-FROZEN`, cierra G0 y autoriza
G1: creación del repositorio, controles de colaboración y scaffold sin lógica técnica
de los módulos asignados. G2 y fases posteriores requieren autorización expresa
posterior; el crawl completo sigue condicionado a O-001/O-007.

| Integrante | Estado | Fecha | Evidencia |
|---|---|---|---|
| Jose Guilermo Carvajal Vaca | `ACCEPTED_AND_AUTHORIZED_G1` | 2026-08-16 | Declaración expresa; GitHub `guillermocarvajalvaca-dev` |
| Monserrat Barba | `ACKNOWLEDGEMENT_PENDING_NON_BLOCKING` | | Brief individual |
| Andrés Poiche | `ACKNOWLEDGEMENT_PENDING_NON_BLOCKING` | | Brief individual |
| Pablo Linares | `ACKNOWLEDGEMENT_PENDING_NON_BLOCKING` | | Brief individual |

La autoridad del coordinador no permite atribuirle scripts de otros integrantes ni
elimina la revisión cruzada: nadie aprueba su propio PR.
