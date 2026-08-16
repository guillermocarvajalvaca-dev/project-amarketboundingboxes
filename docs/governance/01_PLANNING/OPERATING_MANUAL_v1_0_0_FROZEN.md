# Manual operativo — Project AmarketBoundingBoxes v1.0.0 — FROZEN

El SDD define qué es obligatorio. Este manual establece cómo lo ejecuta el equipo.
No puede modificar el alcance ni las interfaces del SDD.

## 1. Arranque y autorización

1. Guillermo registra la decisión de fase y su alcance exacto.
2. La aceptación del coordinador congela la versión gobernante aplicable.
3. Cada integrante recibe SDD, manual, matriz RACI y su brief antes de su primer issue.
4. Los acknowledgements del equipo se registran, pero no bloquean una fase autorizada.
5. Guillermo crea el repositorio y protege `main` durante G1.
6. Se crean issues desde los artefactos de la matriz.
7. Comienza el scaffold sin implementar lógica técnica de otros owners; el crawl
   completo permanece bloqueado hasta G2 y una nueva autorización del coordinador.

## 2. Estructura objetivo del repositorio

```text
project-amarketboundingboxes/
├── .github/
│   ├── ISSUE_TEMPLATE/
│   └── pull_request_template.md
├── README.md
├── CONTRIBUTING.md
├── requirements.txt                 # o environment.yml; nunca ambos a medias
├── configs/
│   ├── data_sources.yaml
│   ├── dataset.yaml
│   └── baseline.yaml
├── data/
│   ├── sample/
│   ├── manifests/
│   └── README.md
├── docs/
│   ├── governance/
│   ├── decisions/
│   └── evidence/
├── informe/
│   ├── main.tex
│   ├── figuras/
│   └── informe.pdf
├── notebooks/
│   ├── eda.ipynb
│   ├── analisis_errores.ipynb
│   └── inferencia_cpu.ipynb
├── src/
│   ├── scraper_extraction.py
│   ├── data/
│   │   ├── validate_downloads.py
│   │   ├── make_boxes.py
│   │   └── make_splits.py
│   ├── common/
│   │   └── reproducibility.py
│   ├── train.py
│   ├── evaluate.py
│   └── predict.py
├── tests/
├── outputs/.gitkeep
└── .gitignore
```

Los notebooks explican o exploran. Las rutas obligatorias se ejecutan desde `src/`.

## 3. GitHub y ramas

- `main` protegida: sin commits directos, sin force-push y merge solo por PR.
- Una tarea corresponde a un issue y una rama.
- Rama: `<tipo>/<owner>/<task-id>-descripcion`.
- Ejemplos:
  - `feat/monserrat/dat-002-scraper`
  - `feat/andres/box-001-pixel-extremes`
  - `feat/pablo/mod-002-train-cli`
  - `feat/guillermo/inf-001-predict-cli`
- Commits: `feat:`, `fix:`, `test:`, `docs:`, `chore:`.
- Cada integrante configura su nombre y correo Git personal.
- No se mezclan artefactos de owners diferentes salvo un handoff o integración
  mecánica declarada.

## 4. Ciclo de una tarea

1. Guillermo abre el issue y vincula requisito, gate y contrato.
2. Owner confirma inputs, outputs y prohibiciones.
3. Owner crea rama desde `main` actualizada.
4. Owner implementa solamente sus artefactos y pruebas.
5. Owner ejecuta el comando exacto y registra exit code, outputs y logs.
6. Owner abre PR con la plantilla gobernante.
7. Reviewer distinto reproduce la prueba mínima; no reescribe el trabajo para aprobar.
8. Si falla, marca `REQUEST_CHANGES` con evidencia concreta.
9. Si pasa, aprueba; Guillermo verifica trazabilidad y fusiona.
10. El gate cambia a `PASSED` únicamente cuando todas sus condiciones tienen evidencia.

## 5. Revisiones cruzadas

| Autor | Revisor primario |
|---|---|
| Monserrat | Andrés |
| Andrés | Monserrat |
| Pablo | Guillermo |
| Guillermo | Pablo o Monserrat según artefacto |

Nadie aprueba su propio PR. Un reviewer no se convierte en coautor por ejecutar tests.

## 6. Handoffs obligatorios

### Monserrat → Andrés

- `source_assets.csv` congelado y hash.
- Imágenes aceptadas o ubicación/instrucción de materialización.
- Rechazos y resumen de adquisición.
- Evidencia de que cada aceptada decodifica y tiene un producto aislado.

### Andrés → Pablo

- Dataset YOLO congelado y hash.
- `dataset.yaml`, `splits.csv` y auditoría de fuga.
- Labels, box audit y muestra visual.
- Conteos train/val/test derivados del manifest.

### Pablo → Guillermo

- Peso seleccionado y SHA-256.
- Configuración resuelta, versiones y hardware.
- Interfaz de carga y clases.
- Métricas, curvas y logs reproducibles.

El consumidor no modifica el artefacto recibido. Si no cumple, abre issue al owner.

## 7. Flujo por gates

### G0 — Spec Readiness

El coordinador acepta los documentos, cierra las decisiones que correspondan a la
fase y emite contrato congelado. Los acknowledgements del equipo no bloquean. Código
técnico bloqueado mientras G0 esté abierto.

### G1 — Repository & Environment

Crear árbol, protección, entorno único, `.gitignore`, plantillas, imports y `--help`.
No implementar por adelantado lógica asignada a otro integrante.

### G2 — Acquisition & Provenance

Monserrat implementa tests S01–S10, smoke test de hasta tres productos y revisión
visual. El crawl completo requiere objetivo de tamaño y derechos documentados.

### G3 — Bounding Boxes & Dataset

Andrés implementa T01–T10, genera cajas, QA visual y splits agrupados por SKU/linaje.
El test se bloquea al congelar el split.

### G4 — Baseline

Pablo ejecuta smoke train, congela baseline y entrena desde CLI con train/val.

### G5 — Evaluation & CPU Inference

Pablo evalúa el peso congelado; Guillermo reproduce inferencia CLI y notebook CPU.

### G6 — Report, README & Defense

Integrar informe LaTeX, README probado por no autor, 10–15 aciertos y 10–15 errores,
links externos accesibles, contribuciones y ensayo de defensa.

## 8. Datos en Drive y código en GitHub

GitHub contiene código, configuraciones, pruebas, documentos, manifests pequeños y
una muestra permitida. Drive contiene imágenes completas, pesos, runs y artefactos
grandes. `.gitignore` debe cubrir al menos:

```gitignore
data/raw/
data/processed/
outputs/runs/
*.pt
*.pth
.env
__pycache__/
.ipynb_checkpoints/
```

No se publica el dataset completo hasta cerrar el estado de derechos.

## 9. Definition of Done

Una tarea está terminada cuando:

- el artefacto está en commit y PR identificables;
- el comando documentado termina con código 0;
- pruebas focalizadas, contrato y caso de error pasan;
- outputs coinciden exactamente con el contrato;
- el revisor reproduce el caso mínimo;
- evidencia y contribución quedan registradas;
- no hay secretos, rutas absolutas ni archivos grandes;
- documentación afectada queda actualizada.

“Funciona en mi notebook” o “el archivo existe” no satisface Definition of Done.

## 10. Bloqueos e incidentes

- Bloqueo técnico de 4 horas: abrir issue y notificar al coordinador por el plazo corto.
- Autoridad, seguridad, derechos, fuga o prueba crítica: Stop-the-Line inmediato.
- No se elimina evidencia fallida; se registra causa y remediación.
- Un cambio de interfaz requiere ADR y aprobación de productor y consumidor.

## 11. Reuniones y registro

Cada sincronización registra fecha, asistentes, decisiones, tareas, owner y fecha
límite. Para este plazo se recomienda una sincronización breve diaria hasta la
entrega; la reunión no sustituye PR, evidencia ni autorización de fase.
