# Registro de decisiones

## Decisiones aprobadas por el coordinador

| ID | Decisión | Estado | Evidencia |
|---|---|---|---|
| D-001 | Nombre canónico `PROJECT_AMARKETBOUNDINGBOXES` | `APPROVED` | Instrucción de Guillermo, 2026-08-15 |
| D-002 | Fuente de catálogo: Amarket | `APPROVED` | Instrucción de Guillermo + smoke test |
| D-003 | Unidad de dato: imagen con un producto aislado y fondo uniforme/transparente | `APPROVED` | Horizonte docente comunicado |
| D-004 | Bounding box por extremos de primer plano y normalización YOLO | `APPROVED` | Horizonte docente comunicado |
| D-005 | Una clase: `0=product`; SKU/descripción solo metadatos | `APPROVED` | Aclaración de Guillermo, 2026-08-15 |
| D-006 | Checkout no es objetivo ni artefacto central | `APPROVED` | Aclaración de Guillermo, 2026-08-15 |
| D-007 | Entrega: miércoles 19 de agosto de 2026 | `APPROVED` | Comunicación de Guillermo |
| D-008 | Los scripts finales se ejecutan desde `src/`; notebooks no sustituyen CLIs | `APPROVED` | AUTH-01/02 |
| D-009 | Trabajo individual por artefacto y revisión cruzada vía PR | `APPROVED` | Requisito de colaboración + coordinación de Guillermo |
| D-010 | La aprobación del coordinador basta para abrir/cerrar fases; acknowledgements del equipo no bloquean | `APPROVED` | Directiva expresa de Guillermo, 2026-08-16 |
| D-011 | Congelar `v1.0.0-FROZEN`, cerrar G0 y autorizar únicamente G1 | `APPROVED` | Aceptación del coordinador, 2026-08-16 |

## Decisiones que el equipo debe cerrar

| ID | Decisión | Impacto | Bloquea |
|---|---|---|---|
| O-001 | Tamaño final del dataset aceptado | Suficiencia y tiempo | Crawl completo y G2, no smoke test |
| O-002 | Proporción `train/val/test` y seed fija | Reproducibilidad | G3 |
| O-003 | Baseline preentrenado y versión exacta | Entrenamiento | G4 |
| O-004 | Inventario de hardware y presupuesto de épocas | Viabilidad | G4 |
| O-005 | Visibilidad final del repo y acceso del docente | Entrega | G6 |
| O-006 | Política institucional de uso/atribución de IA | Autoría | Merge final y G6 |
| O-007 | Estado de derechos para distribuir las imágenes | Publicación | G2/G6; no impide piloto privado |

Las decisiones abiertas no autorizan defaults silenciosos. El dueño del gate registra
la opción, fecha, fundamento, afectados y aprobación antes de ejecutar la fase.

## Formato de nueva decisión

```yaml
decision_id: O-000
selected_option: "..."
decided_by: ["..."]
decided_at: "YYYY-MM-DDTHH:MM:SS-04:00"
evidence: "..."
rationale: "..."
affected_artifacts: []
status: APPROVED
```

Cambiar una decisión aprobada exige ADR, análisis de impacto, aprobación expresa del
coordinador, nueva versión contractual y repetición de los gates afectados.
