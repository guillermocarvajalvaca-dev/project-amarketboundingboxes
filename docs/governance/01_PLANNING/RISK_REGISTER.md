# Registro de riesgos

| ID | Sev. | Riesgo | Mitigación | Owner | Gate |
|---|---|---|---|---|---|
| R-001 | HIGH | Derechos de redistribución no demostrados | piloto privado, registrar estado, no publicar sin permiso | Monserrat | G2/G6 |
| R-002 | HIGH | Sitio cambia HTML o catálogo | manifest snapshot, hashes, JSON/HTML controlado, fallos explícitos | Monserrat | G2 |
| R-003 | HIGH | Scraping excesivo/bloqueo | límite, delay, retry acotado, UA y Stop-the-Line | Monserrat | G2 |
| R-004 | HIGH | Fondo no uniforme produce caja casi completa | filtro, rechazo y QA visual | Monserrat/Andrés | G2/G3 |
| R-005 | HIGH | Error de una unidad en `x_max/y_max` | bordes semiabiertos + T01–T05 | Andrés | G3 |
| R-006 | BLOCKER | Fuga de mismo SKU/duplicado entre splits | split agrupado por SKU/linaje + test automático | Andrés | G3 |
| R-007 | HIGH | Dataset centrado/fondo blanco no generaliza | declararlo; evaluación solo en dominio acordado | Pablo | G5/G6 |
| R-008 | HIGH | Clase/SKU vuelve a confundirse | constante `class_id=0`; tests de schema | Guillermo/Andrés | G0/G3 |
| R-009 | HIGH | Test usado para tuning | bloqueo y ledger de accesos | Guillermo/Pablo | G4/G5 |
| R-010 | HIGH | Entrenamiento solo en notebook | CLI obligatorio + log final | Pablo | G4 |
| R-011 | MEDIUM | CUDA no determinista | seeds, flags, tolerancia y disclosure | Guillermo/Pablo | G5 |
| R-012 | HIGH | Un integrante produce trabajo ajeno | ownership exclusivo + PR/revisión/ledger | Guillermo | G1–G6 |
| R-013 | HIGH | Plazo del 19 de agosto | dataset mínimo viable, freeze temprano, sin scope creep | Guillermo | Todos |
| R-014 | MEDIUM | Hardware insuficiente | inventario + modelo ligero + smoke | Pablo | G4 |
| R-015 | MEDIUM | Dependencias ambiguas | un entorno fijado y prueba limpia | Guillermo | G1 |
| R-016 | MEDIUM | Informe excede 6 páginas | presupuesto de secciones y figuras | Guillermo | G6 |
| R-017 | HIGH | Métricas incomparables/RPC mal citado | protocolo propio; RPC solo contexto | Pablo | G5/G6 |
| R-018 | HIGH | Imagen con varios productos | rechazo inicial; no caja forzada | Monserrat/Andrés | G2/G3 |

Un riesgo se cierra con evidencia, no con la mera existencia de una mitigación.
