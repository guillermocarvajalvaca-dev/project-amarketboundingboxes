# Project AmarketBoundingBoxes — Governance v1.0.0 — FROZEN

Paquete gobernante previo a la implementación del proyecto final de MCI-509,
Procesamiento de Imágenes y Visión Computacional, de la Universidad Católica
Boliviana “San Pablo”, Sede Santa Cruz.

## Identidad y estado

- Proyecto: `PROJECT_AMARKETBOUNDINGBOXES`
- Repositorio previsto: `project-amarketboundingboxes`
- Versión contractual: `1.0.0-FROZEN`
- Fecha de evidencia: `2026-08-16`
- Entrega comunicada por el coordinador: `2026-08-19`
- Estado: `FROZEN`
- Autorización vigente: `G1_REPOSITORY_AND_SCAFFOLD`
- Autoridad de fase: Guillermo Carvajal Vaca, coordinador y líder
- Política sin evidencia: `ABSTAIN`

`FROZEN` significa que el alcance y las interfaces de esta versión gobiernan la
implementación. La aceptación expresa del coordinador del 2026-08-16 cerró G0 y
autorizó G1. Las fases posteriores requieren autorización expresa del coordinador.
La aceptación o existencia de un archivo no prueba implementación, ejecución ni
cumplimiento.

## Objetivo congelable

Construir un dataset propio de imágenes públicas de productos de Amarket, localizar
automáticamente los píxeles extremos del producto aislado y producir anotaciones de
detección en formato YOLO. El dataset es monoclase:

```yaml
names:
  0: product
```

El SKU, nombre y descripción son metadatos de procedencia; no son clases. Checkout,
identificación fine-grained del SKU, escenas multiproducto y RPC como dataset objetivo
quedan fuera. RPC puede citarse únicamente como antecedente científico.

## Orden de lectura

1. `00_GOVERNANCE/DOCUMENT_AUTHORITY.md`
2. `00_GOVERNANCE/CONTRACT_SDD_v1_0_0_FROZEN.md`
3. `00_GOVERNANCE/DECISION_REGISTER.md`
4. `01_PLANNING/OPERATING_MANUAL_v1_0_0_FROZEN.md`
5. `01_PLANNING/RACI_AND_ARTIFACT_MATRIX.md`
6. `01_PLANNING/RUBRIC_TRACEABILITY_AND_QUALITY_GATES.md`
7. `02_CONTRACTS/` según el módulo asignado
8. brief individual en `04_EXECUTION_BRIEFS/`

## Regla de colaboración

Cada artefacto tiene un autor y un revisor distinto. Guillermo coordina e integra,
pero no escribe retroactivamente los scripts asignados a Monserrat, Andrés o Pablo.
Nadie aprueba su propio PR. Un archivo existente no prueba que funcione: solo una
ejecución reproducida y registrada puede cerrar un gate.

La autorización del coordinador basta para abrir o cerrar una fase. Esta autoridad
no transfiere la autoría de los artefactos, no permite self-approval de PR y no elimina
la obligación de que cada integrante ejecute y evidencie su trabajo asignado.

## Exclusiones del paquete

Este paquete no crea el repositorio remoto, no instala dependencias, no ejecuta el
scraper completo, no descarga un dataset, no entrena modelos y no atribuye código a
ningún integrante. Define las obligaciones para que cada persona produzca su parte.
