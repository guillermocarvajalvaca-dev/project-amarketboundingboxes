# ADR-006 — Alcance de dos etapas: localización monoclase + identificación por retrieval

- Fecha: 2026-08-24
- Estado: `ACCEPTED`
- Propuesta y aceptada por: Guillermo Carvajal, coordinador y líder, en esta sesión de
  ejecución (mensaje "DECISIÓN DEL COORDINADOR — CORRECCIÓN DEL OBJETIVO SEGÚN
  REPLANTEO DOCENTE").
- Gate: posterior a P2-G4 (Experimento B), previo a P2-G5/G6 (evaluación y entrega).
- Relacionada: `01_CONTRACT_SDD_PHASE2_v2_0_0_FROZEN.md`, `03_ADR-005_...md`,
  `docs/governance/00_GOVERNANCE/CONTRACT_SDD_v1_0_0_FROZEN.md`.
- Documento NO-FROZEN: no reescribe ni sustituye ningún contrato congelado. Los
  contratos FROZEN permanecen exactamente como están; esta ADR añade una etapa
  posterior a su salida, sin modificar `class_id=0`/`class_name=product` como
  contrato de entrenamiento YOLO.

## Contexto

El coordinador comunicó en esta sesión que el docente replanteó oralmente el
proyecto para simular una caja de supermercado: en una escena multiproducto, el
sistema debe localizar cada artículo **e identificar qué producto es**.
**Nota de procedencia:** este replanteo se registra tal como fue comunicado por el
coordinador en el chat de esta sesión; es una comunicación oral/verbal del docente,
no verificada de forma independiente por esta ejecución (no existe un correo, acta o
documento del docente adjunto). Se documenta como afirmación atribuida al
coordinador, no como hecho verificado por evidencia externa.

El contrato interno vigente (`CONTRACT_SDD_v1_0_0_FROZEN.md`, reafirmado por
`01_CONTRACT_SDD_PHASE2_v2_0_0_FROZEN.md`) fija el alcance de YOLO exclusivamente
como localización monoclase: `class_id=0`, `class_name=product`, con SKU/nombre
como metadato y **prohibición explícita** de tratar SKU o nombre de producto como
clase YOLO (`CONTRACT_SDD_v1_0_0_FROZEN.md` L49). Auditoría de esta sesión confirmó
que el 100% de las labels reales y sintéticas (459+98+98 reales, 481 boxes
sintéticos) usan exclusivamente `class_id=0`, y que el catálogo scrapeado no tiene
`category`/`product_type` utilizable (0/655 no vacío) ni `sku_id` viable como clase
supervisada (459-655 clases con ~1 muestra cada una).

Ese contrato monoclase, cumplido correctamente por el detector, **describe un
alcance inferior** al que ahora exige el replanteo docente: localizar es necesario
pero no suficiente: hace falta identidad por producto.

## Decisión

1. **YOLO permanece exactamente como está contractualmente definido**: detector de
   una sola clase, `class_id=0`/`class_name=product`. No se crean 459 ni 655 clases
   YOLO — una muestra por SKU hace estadísticamente inviable la clasificación
   supervisada a ese nivel (no hay forma de construir train/val/test con n≈1).
2. Se autoriza una **segunda etapa, posterior y desacoplada del entrenamiento
   YOLO**: identificación de producto por **retrieval/matching visual** contra un
   catálogo de referencia (`catalog_identity.csv`), no por clasificación
   supervisada.
3. La etapa de identificación opera sobre el *crop* de cada bounding box que YOLO
   ya localizó; no reentrena ni modifica el detector.
4. La salida funcional final combina ambas etapas: bounding box + nombre/SKU
   (vía retrieval) + confianza de detección (YOLO) + score de similitud de
   identidad (retrieval).
5. Se documenta explícitamente como limitación: las escenas sintéticas usadas para
   evaluar esta segunda etapa derivan de los mismos cutouts que forman el catálogo
   de referencia, por lo que la medición de identidad sobre ellas es una evaluación
   cerrada/optimista, no una prueba de generalización a fotografías nuevas de caja.

## Consecuencias

Positivas:
- responde al replanteo docente sin violar ni reescribir el contrato monoclase
  congelado;
- evita el error estadístico de crear cientos de clases YOLO con ~1 muestra cada
  una;
- desacopla localización (ya entrenada y validada, B0/T1) de identificación
  (nueva, basada en retrieval), permitiendo iterar la segunda sin retocar la
  primera.

Trade-offs:
- el retrieval depende de la calidad/cobertura del catálogo de referencia
  (`catalog_identity.csv`) y de qué backend de embeddings/matching esté realmente
  disponible sin instalar nada nuevo (ver Fase 3 de esta sesión);
- la evaluación de identidad sobre las 197 escenas sintéticas es cerrada/optimista
  por construcción (ver limitación arriba);
- introduce una segunda fuente de error (identificación) sobre la salida final,
  además del error de detección.

## Rechazado

- crear una clase YOLO por SKU o por producto (459-655 clases, ~1 muestra cada
  una: inviable);
- reentrenar o modificar el detector YOLO para que prediga identidad directamente;
- reabrir la generación sintética completa (655 escenas) para esta corrección de
  alcance — fuera de foco, ya resuelto como limitación documentada 197/655.
