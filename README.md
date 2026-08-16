# Project AmarketBoundingBoxes

Proyecto final de MCI-509, Procesamiento de Imágenes y Visión Computacional,
Universidad Católica Boliviana "San Pablo", Sede Santa Cruz.

## Estado

`G1_BOOTSTRAP`

El repositorio contiene únicamente el paquete gobernante y el andamiaje
estructural. La existencia de un archivo o de una carpeta no prueba
implementación, ejecución ni cumplimiento.

## Objetivo

Construir un dataset propio de imágenes públicas de productos de Amarket,
localizar automáticamente los píxeles extremos del producto aislado y producir
anotaciones de detección en formato YOLO.

El dataset es **monoclase**:

```yaml
names:
  0: product
```

El SKU, el nombre y la descripción son **metadatos de procedencia; no son
clases**. Checkout, identificación fine-grained del SKU, escenas multiproducto
y RPC como dataset objetivo quedan fuera del alcance.

## Documentos gobernantes

Están en [`docs/governance/`](docs/governance/), validados contra
`docs/governance/MANIFEST.sha256`. Orden de lectura y reglas de colaboración en
[`docs/governance/README.md`](docs/governance/README.md).

| Documento | Ruta |
|---|---|
| Contrato SDD (FROZEN) | `docs/governance/00_GOVERNANCE/CONTRACT_SDD_v1_0_0_FROZEN.md` |
| ADR-001 autoridad de gate | `docs/governance/00_GOVERNANCE/ADR-001_COORDINATOR_GATE_AUTHORITY.md` |
| Manual operativo (FROZEN) | `docs/governance/01_PLANNING/OPERATING_MANUAL_v1_0_0_FROZEN.md` |
| Cierre de G0 | `docs/governance/06_AUDIT/G0_CLOSURE_20260816.md` |

## Estado de implementación

| Componente | Estado |
|---|---|
| Scraper de extracción | `NOT IMPLEMENTED` |
| Generación de bounding boxes | `NOT IMPLEMENTED` |
| Splits del dataset | `NOT IMPLEMENTED` |
| Entrenamiento, evaluación y predicción | `NOT IMPLEMENTED` |
| Entorno reproducible | `NOT SELECTED` — pendiente en el issue `ENV-001` |

No hay dependencias declaradas todavía: la elección de un mecanismo único de
entorno es una decisión abierta de G1.

## Contribuir

Lee [`CONTRIBUTING.md`](CONTRIBUTING.md) antes de abrir una rama. Cada artefacto
tiene un autor y un revisor distinto; nadie aprueba su propio PR.
