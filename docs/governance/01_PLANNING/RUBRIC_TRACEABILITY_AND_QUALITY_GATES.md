# Trazabilidad de rúbrica y Quality Gates

## 1. Matriz de trazabilidad

| Requisito | Fuente | Artefacto | Evidencia | Gate |
|---|---|---|---|---|
| Informe LaTeX 4–6 páginas | Guía §1 | `.tex`, figuras, PDF | compilación + inspección | G6 |
| Resumen 150–200 palabras | Guía §1 | Resumen | conteo + revisión | G6 |
| Fuente, licencia, tamaño, splits, balance y límites | Guía §1/2 | datasheet + informe | manifest + tablas | G2/G3/G6 |
| Métricas y curva train/val | Guía §1 | JSON + figuras | logs | G4/G5 |
| 10–15 aciertos y 10–15 errores | Guía §1 | notebook/figuras | Run All | G5/G6 |
| `train.py`, `evaluate.py`, `predict.py` | Guía §2 | tres CLIs | `--help` + smoke | G1/G4/G5 |
| Entrenamiento sin Jupyter | Guía §2 + captura | `src/train.py` | comando final + log | G4 |
| Un entorno completo | Guía §2 | requirements o environment | instalación limpia | G1 |
| Semillas e hiperparámetros | Guía §2 | configs + logs | repetición controlada | G4/G5 |
| Inferencia CPU | Guía §2 | notebook CPU | Run All sin CUDA | G5 |
| Sin rutas absolutas | Guía §2 | repo | búsqueda automatizada | G1/G6 |
| Datos/pesos grandes fuera de Git | Guía §2 | gitignore + links | inspección | G1/G6 |
| README probado por no autor | Guía §2 | README | log del revisor | G6 |
| Scraping Amarket | Aclaración docente D-002/003 | scraper + manifest | S01–S10 + piloto | G2 |
| Píxeles extremos y YOLO relativo | Aclaración D-004 | boxes + audit | T01–T10 + grilla | G3 |
| Colaboración verificable | Rúbrica/defensa + SDD | issues, commits, PRs, ledger | revisión cruzada | G1–G6 |

## 2. Ponderación oficial

| Criterio | Puntos | Evidencia primaria |
|---|---:|---|
| Calidad y documentación de datos | 22 | Monserrat + Andrés |
| Solución técnica y resultados | 34 | Pablo + Andrés |
| Reproducibilidad | 22 | Guillermo + cada owner |
| Demo y defensa | 22 | Todos |

## 3. Gates y aceptación

### G0 — Spec Readiness

SDD/manual aceptados por el coordinador; objetivo monoclase sin contradicción;
owner/reviewer e interfaces definidos; fecha fijada. Los acknowledgements del equipo
no bloquean. Las decisiones específicas de fases posteriores pueden quedar abiertas
si bloquean solo su gate.

### G1 — Repository & Environment

Árbol, protección, entorno único, imports y `--help` pasan; no hay secretos, rutas
absolutas o archivos grandes; templates y ownership están activos.

### G2 — Acquisition & Provenance

S01–S10 pasan; piloto limitado produce imágenes decodificables, manifest, hashes,
rechazos y resumen; cada aceptada contiene un producto aislado; derechos están
clasificados. Crawl completo requiere O-001/O-007.

### G3 — Bounding Boxes & Dataset

T01–T10 pasan; una etiqueta válida por aceptada; cero huérfanos; extremos y valores
relativos auditados; QA visual; cero cruces de SKU/linaje; test bloqueado.

### G4 — Baseline

Baseline/versiones/hardware congelados; smoke train pasa; entrenamiento final CLI
genera peso, configuración, curvas y logs sin consultar test.

### G5 — Evaluation & CPU

Métricas con fórmula y JSON; misma evaluación repetida coincide; `predict.py` y
notebook CPU pasan; análisis contiene 10–15 correctos y 10–15 incorrectos.

### G6 — Delivery & Defense

Checklist oficial completo; PDF compila; README reproducido por no autor; notebooks
Run All; links externos accesibles; contribución y defensa demostradas.

## 4. Estados

`PASS`, `PARTIAL`, `FAIL`, `BLOCKED`, `NOT ASSESSED`. La ausencia de evidencia nunca
se transforma en `PASS`.

## 5. QA candidato

Se ejecuta solo después de fijar el stack. Si una herramienta no está instalada, se
registra `NOT RUN`; no se instala silenciosamente.

```text
ruff check src tests
mypy src --strict
bandit -r src
pip-audit
pytest -v
pytest --cov=src --cov-report=term-missing
jupyter nbconvert --execute --to notebook NOTEBOOK --output EXECUTED.ipynb
```
