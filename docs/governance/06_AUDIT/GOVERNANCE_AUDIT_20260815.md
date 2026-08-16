# Auditoría gobernante v0.2.0 — 2026-08-15

> `HISTORICAL_SUPERSEDED`: este dictamen refleja el estado del 2026-08-15. La
> aceptación del coordinador y el cierre posterior de G0 están registrados en
> `G0_CLOSURE_20260816.md`.

## Veredicto

`CONDITIONAL PASS` para revisión humana del paquete. `BLOCKED` para implementación
hasta que los cuatro integrantes acepten el SDD y se emita `v1.0.0-FROZEN`.

## Alcance y autoridad

Se revisaron la guía oficial adjunta, captura docente, paquete histórico RPC, copia
Qwen y la gobernanza v0.1.2. No se ejecutó código de implementación porque no existe
todavía y cada script pertenece a su integrante.

## Hallazgos y remediación

| ID | Sev. | Evidencia | Riesgo | Decisión | Cierre v0.2.0 |
|---|---|---|---|---|---|
| H-001 | BLOCKER | documentos antiguos trataban SKU como clase | objetivo incorrecto | REQUIRED | clase única `product` |
| H-002 | BLOCKER | checkout/RPC persistían como identidad | scope creep | REQUIRED | fuera; solo contexto científico |
| H-003 | HIGH | split estratificado por SKU multiclase | fuga/métrica inválida | REQUIRED | agrupación exclusiva por SKU/linaje |
| H-004 | HIGH | descripción faltaba en manifest | pérdida de trazabilidad solicitada | REQUIRED | campo incorporado |
| H-005 | HIGH | GitHub no estaba formalizado en templates | colaboración no demostrable | REQUIRED | flujo, issues, PR y ledger |
| H-006 | HIGH | derechos de imágenes no resueltos | publicación indebida | REQUIRED | piloto privado; G2/G6 bloquean publicación |
| H-007 | HIGH | decisiones tardías podían bloquear todo G0 | plazo inviable | REQUIRED | bloqueo por gate, no global |

## Evidencia ejecutada del smoke test Amarket

| Prueba | Resultado |
|---|---|
| GET colección | HTTP 200, HTML, 756139 bytes |
| Descubrimiento | 24 enlaces de producto únicos en respuesta observada |
| JSON de colección `limit=1` | HTTP 200, `application/json` |
| Ficha de producto | HTTP 200, SKU e imágenes extraíbles |
| Archivo visual | HTTP 200, JPEG válido 700×700 |
| Máscara básica de muestra | fondo blanco; bbox y valores YOLO calculables |
| `robots.txt` | HTTP 200; catálogo público permitido, transacciones excluidas |

Esta evidencia prueba viabilidad inicial de fuente y algoritmo en una muestra. No
prueba paginación completa, calidad de todo el catálogo, S01–S10, T01–T10, derechos
de redistribución, modelo o reproducibilidad final.

## Contradicciones resueltas

- `RPC` deja de ser nombre/dataset objetivo y solo puede aparecer como literatura.
- Checkout deja de ser resultado central.
- `sku_id` deja de ser clase y pasa a metadato/grupo de fuga.
- `class_id` es constante 0.
- `predict.py` tiene un único owner: Guillermo.
- Entrenamiento final se ejecuta desde `src/train.py`, no desde notebook.

## Evidencia pendiente

- aceptación de los cuatro integrantes;
- tamaño final, ratios/seed, baseline, hardware, visibilidad y política de IA;
- derechos de publicación;
- repositorio, scripts, tests, CI, dataset, modelo, métricas e informe.

## Próximo paso único

Los cuatro integrantes revisan y registran aceptación o cambios. Guillermo emite
`v1.0.0-FROZEN`; después crea repo e issues sin implementar módulos ajenos.

## Confianza

Está demostrada la coherencia interna del alcance propuesto y la viabilidad técnica
de una muestra Amarket. No está demostrada ninguna implementación del equipo ni la
calidad del dataset/modelo final.
