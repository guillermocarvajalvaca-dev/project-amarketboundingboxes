# Estado BOX-001 — Andrés Poiche
Última actualización: 2026-08-16, commit e9c99fd en rama feat/boxes-andres

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
- Acuse formal posteado en issue #3 (ACK-001)
- Mensaje enviado al equipo con 2 preguntas (rama, reviewer) + 2 bloqueantes
  de contrato — pendiente respuesta
- Confirmado acceso al repo (push exitoso + username clickeable en issues)

## Pendiente
- CLI/orquestador que use check_no_orphans + demás funciones sobre el
  manifest real de Monserrat (handoff SCR-001 aún no entregado) — la
  auditoría del dataset REAL completo sigue bloqueada, aunque la función
  unitaria T10 ya está lista y testeada
- Falta configs/dataset.yaml (contrato no define schema interno — sección
  outputs solo lo lista como entregable; se arma con parámetros conocidos +
  PENDING_* explícitos)
- Falta notebooks/eda.ipynb (aún no empezado)
- Falta box_audit.csv + grilla visual (aún no empezado)

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

## Discrepancias a confirmar con Guillermo
- Nombre de rama: se usó "feat/boxes-andres" (indicado por Guillermo en chat),
  pero el manual operativo §3 especifica "feat/andres/box-001-..."
- Reviewer: el chat directo de Guillermo a Andrés dice explícitamente
  "tu revisor es Pablo" — pero issue #5 y manual §5 dicen Monserrat.
  Ya no es un mensaje ambiguo: es instrucción directa en conflicto con
  la documentación formal. A confirmar en la reunión de las 5.
- SCR-001: Monserrat dijo por chat "estoy en S4", issue reporta gate G2 y
  ejecución S01-S10 completa — confirmar estado real

## Cómo retomar
```bash
cd ~/proyectos/project-amarketboundingboxes
git checkout feat/boxes-andres
source .venv/bin/activate
pytest tests/test_make_boxes.py tests/test_make_splits.py -v
```
