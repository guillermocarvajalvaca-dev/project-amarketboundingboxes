# Estado BOX-001 — Andrés Poiche
Última actualización: 2026-08-16, commit 6be2496 en rama feat/boxes-andres

## Hecho
- Entorno: .venv con pytest 9.1.1, numpy 2.5.2, pillow 12.3.0, pandas (requirements-boxes.txt)
- src/data/make_boxes.py implementado, T01-T10 COMPLETO (§8 contrato):
  - compute_yolo_box: extremos + bordes semiabiertos + formato YOLO (§5-6 contrato)
  - make_mask_from_alpha: máscara desde canal alpha RGBA (§4 contrato)
  - make_mask_from_rgb: máscara desde fondo uniforme RGB (§4 contrato)
  - load_and_validate_image: carga/valida imagen decodificable (§3 contrato)
  - check_no_orphans (T10): gate de huérfanos label/imagen, ValueError si
    hay al menos uno; testeado con carpetas sintéticas (tmp_path), no
    depende del scraper real de Monserrat
- tests/test_make_boxes.py: 13/13 tests pasan (T01-T10 completo, sin skips)
- src/data/make_splits.py implementado, cobertura completa de §split_policy:
  - group_exclusivity (sku_id, source_asset_id, duplicate_group_id): union-find
  - derivative_rule: grupos completos, nunca se parten entre splits
  - class_rule (ningún split vacío con grupos suficientes): verificado con test
  - Gate: detiene con ValueError si hay menos de 3 grupos independientes
  - ratios y seed como parámetros (no hardcodeados, ver PENDING_O_002)
- tests/test_make_splits.py: 7/7 tests pasan
- Acuse formal posteado en issue #3 (ACK-001) — confirmado: los 4 integrantes
  ya comentaron, issue listo para cerrar de parte de Guillermo
- Mensaje enviado al equipo con 2 preguntas (rama, reviewer) + 2 bloqueantes
  de contrato — pendiente respuesta
- Confirmado acceso al repo (push exitoso + username clickeable en issues)
- PR: preparado para abrir (rama limpia, 11 commits, "Able to merge" en
  GitHub) — EN PAUSA, ver "Antes de abrir el PR" abajo

## Pendiente
- CLI/orquestador que use check_no_orphans + demás funciones sobre el
  manifest real de Monserrat (handoff SCR-001 aún no entregado) — la
  auditoría del dataset REAL completo sigue bloqueada, aunque la función
  unitaria T10 ya está lista y testeada
- Falta configs/dataset.yaml (contrato no define schema interno — sección
  outputs solo lo lista como entregable; se arma con parámetros conocidos +
  PENDING_* explícitos)
- Falta notebooks/eda.ipynb (aún no empezado)
- Falta outputs/box_audit.csv + grilla visual (aún no empezado, es parte
  del alcance formal de BOX-001 según issue #5)

## Antes de abrir el PR — hallazgos del issue oficial #5 (BOX-001)
Se leyó el issue formal completo (no solo el chat) y aparecen 3 discrepancias
nuevas que conviene resolver antes de abrir el PR, no después:

1. **Nombre de rama:** el issue #5 fija `feat/andres/BOX-001-make-boxes`.
   Se usó `feat/boxes-andres` (indicado por Guillermo en chat). Coincide
   con lo que ya decía el manual operativo §3 — ahora confirmado también
   por el issue oficial. 2 fuentes formales vs 1 mensaje de chat.
2. **Reviewer:** el issue #5 dice explícitamente "Reviewer: @mbarbacardozo
   (RACI BOX-001)" — Monserrat. Coincide con el manual §5. El chat de
   Guillermo dirigido a mí decía Pablo. 2 fuentes formales (issue + RACI)
   vs 1 instrucción directa de chat más reciente.
3. **Alcance — SPL-001 no existe:** el issue #5 dice textualmente "Los
   splits van en un issue aparte (SPL-001)". Se revisaron los 7 issues
   del repo (#1-#7): SPL-001 NO fue creado. make_splits.py se desarrolló
   igual porque es parte del brief general (bounding boxes, splits, EDA),
   pero formalmente el issue #5 solo cubre make_boxes.py + box_audit.csv.
   Pendiente decidir: ¿todo en un solo PR, o separar cuando exista SPL-001?

Decisión: NO se abre el PR todavía sobre estos 3 puntos. Se llevan a la
reunión de las 5 para confirmar con Guillermo antes de formalizar.

## Seguimiento SCR-001 (Monserrat, issue #4) — como reviewer asignado
- Estado real: S01-S10 y smoke test (--limit 3) ejecutados con EXIT CODE 0,
  según comentario de Monserrat en el issue. Aún sin PR abierto.
- Discrepancia detectada: Monserrat dijo por chat "estoy en S4", pero el issue
  reporta gate G2 y ejecución ya completa — a confirmar estado real.
- Ambigüedad de contrato levantada por Monserrat: §4.7 exige validar "tamaño
  máximo" de imagen, pero §3 (configuración explícita) no define límite de
  bytes/tamaño, y el contrato prohíbe defaults ocultos. Pendiente que el
  equipo defina el valor/criterio o difiera la validación a otra tarea.
- Acción mía cuando abra PR: revisión cruzada obligatoria (no self-merge/
  self-approval permitido en main).

## Bloqueantes de equipo (no bloquean tests unitarios, sí el dataset real)
- BOUNDING_BOX_ALGORITHM_CONTRACT.md §3: alpha_threshold,
  background_uniformity_tolerance, foreground_delta, min_foreground_pixels
  están en PENDING_G3_PILOT
- DATA_AND_SPLIT_CONTRACT.yaml:
  - split_policy.fixed_seed y ratios → PENDING_O_002
  - quality_rules.final_dataset_size → PENDING_O_001
  - publication.redistribution → PENDING_O_007

## Dudas de contrato a confirmar
- split_policy.test_lock: true — no está claro qué implica exactamente
  (¿el split test queda inmutable entre corridas? ¿no se puede regenerar?)

## Discrepancias a confirmar con Guillermo (llevar a reunión de las 5)
1. Nombre de rama: usé "feat/boxes-andres"; manual §3 E issue oficial #5
   dicen "feat/andres/BOX-001-make-boxes" (2 fuentes formales vs chat)
2. Reviewer: manual §5 E issue oficial #5 dicen Monserrat (RACI BOX-001);
   chat directo de Guillermo a mí dijo Pablo (2 fuentes formales vs chat
   más reciente)
3. Alcance de make_splits.py: issue #5 dice que va en SPL-001, que no
   existe. ¿Incluir en este PR o esperar a que se cree el issue?
4. SCR-001: Monserrat dijo por chat "estoy en S4", issue reporta gate G2
   y ejecución S01-S10 completa — confirmar estado real

## Cómo retomar
```bash
cd ~/proyectos/project-amarketboundingboxes
git checkout feat/boxes-andres
source .venv/bin/activate
pytest tests/test_make_boxes.py tests/test_make_splits.py -v
```
