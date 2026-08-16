# Estado BOX-001 — Andrés Poiche
Última actualización: 2026-08-16, commit 0001ff1 en rama feat/boxes-andres

## Hecho
- Entorno: .venv con pytest 9.1.1, numpy 2.5.2, pillow 12.3.0, pandas (requirements-boxes.txt)
- src/data/make_boxes.py implementado:
  - compute_yolo_box: extremos + bordes semiabiertos + formato YOLO (§5-6 contrato)
  - make_mask_from_alpha: máscara desde canal alpha RGBA (§4 contrato)
  - make_mask_from_rgb: máscara desde fondo uniforme RGB (§4 contrato)
  - load_and_validate_image: carga/valida imagen decodificable (§3 contrato)
- tests/test_make_boxes.py: 10/11 tests pasan (T01-T09 + T09b control)
- src/data/make_splits.py implementado:
  - Union-find agrupa sku_id + duplicate_group_id en componentes conexas
    (exclusividad de grupo, ningún SKU/duplicado cruza splits)
  - Gate: detiene con ValueError si hay menos de 3 grupos independientes
  - ratios y seed como parámetros (no hardcodeados, ver PENDING_O_002)
- tests/test_make_splits.py: 6/6 tests pasan
- Acuse formal posteado en issue #3 (ACK-001)
- Mensaje enviado al equipo con 2 preguntas (rama, reviewer) + 2 bloqueantes
  de contrato — pendiente respuesta

## Pendiente
- T10 (huérfanos label/imagen): requiere pipeline completo de auditoría a nivel
  dataset, no es una función unitaria — se implementa junto con el CLI principal
- Falta el CLI/orquestador que use estas funciones sobre el manifest real de
  Monserrat (handoff SCR-001 aún no entregado)
- Falta configs/dataset.yaml y notebooks/eda.ipynb (aún no empezados)
- Falta box_audit.csv + grilla visual (aún no empezado)

## Bloqueantes de equipo (no bloquean tests unitarios, sí el dataset real)
- BOUNDING_BOX_ALGORITHM_CONTRACT.md §3: alpha_threshold,
  background_uniformity_tolerance, foreground_delta, min_foreground_pixels
  están en PENDING_G3_PILOT
- DATA_AND_SPLIT_CONTRACT.yaml: fixed_seed y ratios en PENDING_O_002

## Discrepancias a confirmar con Guillermo
- Nombre de rama: se usó "feat/boxes-andres" (indicado por Guillermo en chat),
  pero el manual operativo §3 especifica "feat/andres/box-001-..."
- Reviewer: issue #5 y manual §5 dicen Monserrat; un mensaje de chat de
  Guillermo dijo Pablo — se toma Monserrat como correcto (coincide en 2 fuentes)

## Cómo retomar
```bash
cd ~/proyectos/project-amarketboundingboxes
git checkout feat/boxes-andres
source .venv/bin/activate
pytest tests/test_make_boxes.py tests/test_make_splits.py -v
```
