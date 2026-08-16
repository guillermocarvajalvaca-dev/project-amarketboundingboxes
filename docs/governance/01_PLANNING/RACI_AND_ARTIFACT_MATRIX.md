# Matriz RACI y propiedad de artefactos

`A` = autor/owner, `V` = verificador distinto. El coordinador integra, pero no asume
retroactivamente la autoría técnica de otro integrante.

| ID | Artefacto | A | V | Evidencia mínima |
|---|---|---|---|---|
| GOV-001 | Repo, protección de `main`, plantillas y `.gitignore` | Guillermo | Pablo | configuración + PR |
| GOV-002 | SDD, manual, decisiones, gates y ledgers | Guillermo | Monserrat | versión + hash + autorización del coordinador |
| REP-001 | README integrado y comandos | Guillermo | Monserrat | reproducción en entorno ajeno |
| REP-002 | `src/common/reproducibility.py` | Guillermo | Pablo | tests de seed/config |
| INF-001 | `src/predict.py` | Guillermo | Pablo | CLI + outputs JSON/imagen |
| INF-002 | `notebooks/inferencia_cpu.ipynb` | Guillermo | Andrés | Restart & Run All sin CUDA |
| DAT-001 | `configs/data_sources.yaml` | Monserrat | Guillermo | fuente, robots, fecha y política |
| DAT-002 | `src/scraper_extraction.py` | Monserrat | Andrés | S01–S10 + log piloto |
| DAT-003 | `src/data/validate_downloads.py` | Monserrat | Andrés | reporte aceptados/rechazados |
| DAT-004 | `data/manifests/source_assets.csv` | Monserrat | Guillermo | esquema, hashes y procedencia |
| DAT-005 | Mini-datasheet y sección Datos | Monserrat | Guillermo | cifras derivadas del manifest |
| BOX-001 | `src/data/make_boxes.py` | Andrés | Monserrat | T01–T10 + tests geométricos |
| BOX-002 | `outputs/box_audit.csv` y grilla visual | Andrés | Monserrat | extremos + caja + QA |
| SPL-001 | `src/data/make_splits.py` | Andrés | Guillermo | prueba anti-fuga por SKU/linaje |
| CFG-001 | `configs/dataset.yaml` | Andrés | Pablo | clase única y rutas relativas |
| EDA-001 | `notebooks/eda.ipynb` | Andrés | Monserrat | Restart & Run All + tablas |
| MOD-001 | `configs/baseline.yaml` | Pablo | Guillermo | configuración congelada |
| MOD-002 | `src/train.py` | Pablo | Guillermo | `--help`, smoke y log final |
| EVA-001 | `src/evaluate.py` | Pablo | Guillermo | métricas repetidas idénticas |
| EVA-002 | `notebooks/analisis_errores.ipynb` | Pablo | Andrés | 10–15 aciertos/errores |
| RPT-001 | Metodología y resultados | Pablo | Guillermo | texto, tablas y figuras |
| RPT-002 | Datos y limitaciones | Monserrat | Andrés | trazabilidad a manifest |
| RPT-003 | Algoritmo, cajas y splits | Andrés | Monserrat | trazabilidad a box audit |
| RPT-004 | Integración/compilación LaTeX | Guillermo | Pablo | log + PDF inspeccionado |
| DEM-001 | Guion y demo | Guillermo integra; todos presentan | Todos | ensayo y checklist |

## Defensa

- Guillermo: problema, arquitectura, reproducibilidad e integración.
- Monserrat: fuente, scraper, manifest, derechos y limitaciones.
- Andrés: máscara, extremos, YOLO, QA y split anti-fuga.
- Pablo: baseline, métricas, curvas y análisis de errores.

Cada integrante presenta un artefacto que creó o ejecutó y puede rastrear a un PR/log.

## Prohibiciones de solapamiento

- Monserrat no crea cajas, splits ni modelo.
- Andrés no modifica el scraper ni ajusta hiperparámetros.
- Pablo no corrige datos/splits ni implementa inferencia asignada a Guillermo.
- Guillermo no escribe scraper, cajas/splits o entrenamiento de otros.
- El integrador no cambia interfaces sin handoff y ADR.
