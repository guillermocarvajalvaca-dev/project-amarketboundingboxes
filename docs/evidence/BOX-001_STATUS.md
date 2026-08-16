# Estado BOX-001 — Andres Poiche
Última actualización: 2026-08-16, commit a2f3132 en rama feat/andres/BOX-001-make-boxes
(rama contractual activa — feat/boxes-andres conservada intacta como evidencia legacy)

## RESOLUCIÓN OFICIAL DE GUILLERMO (16/08, ~18:10-18:20)
Respuesta a mis 3 preguntas + creación de SPL-001:

1. **Rama:** BOX-001 se trabaja en `feat/andres/BOX-001-make-boxes` — HECHO,
   creada desde main actualizado.
2. **Reviewer:** Monserrat (@mbarbacardozo) — para BOX-001 y SPL-001.
   Pablo NO es reviewer de ninguno de los dos.
3. **Scope:** `make_splits.py` y `configs/dataset.yaml` van en
   `feat/andres/SPL-001-make-splits`, bajo issue **SPL-001 (#14)**, ya creado:
   https://github.com/guillermocarvajalvaca-dev/project-amarketboundingboxes/issues/14
4. **`requirements-boxes.txt`:** NO se incluye en ningún PR. El proyecto
   usa un único `requirements.txt` (ya en main, con pillow==12.3.0,
   numpy==2.4.6, ultralytics==8.4.120, PyYAML==6.0.3 — pandas es transitiva
   de ultralytics, no hace falta declararla para BOX-001).
5. **`feat/boxes-andres` se conserva intacta** — no borrar, no force-push.

## Plan de ejecución
- [x] Actualizar main localmente (trajo trabajo de Pablo: train.py, evaluate.py,
      requirements.txt, docs/ENVIRONMENT.md, etc.)
- [x] Crear `feat/andres/BOX-001-make-boxes` desde main
- [x] Trasladar SOLO: src/data/make_boxes.py + tests/test_make_boxes.py +
      conftest.py + src/__init__.py + src/data/__init__.py (necesarios para
      que pytest resuelva el import de src como paquete)
- [x] Verificado: 13/13 tests en verde en la rama nueva, sin requirements-boxes.txt
- [x] Commit y push de la rama contractual (a2f3132)
- [ ] Producir outputs/box_audit.csv + grilla visual (PENDIENTE — no empezado)
- [ ] Verificar checklist completo antes de abrir PR (ver abajo)
- [ ] Abrir PR de BOX-001, reviewer: Monserrat
- [ ] Crear `feat/andres/SPL-001-make-splits` desde main (pendiente, después de BOX-001)
- [ ] Trasladar: src/data/make_splits.py + tests/test_make_splits.py +
      configs/dataset.yaml (aún sin crear)
- [ ] Abrir PR de SPL-001, reviewer: Monserrat

## Checklist de verificación antes de abrir PR de BOX-001 (exigido por Guillermo)
- [x] 13/13 tests en verde
- [x] Una etiqueta válida por cada imagen aceptada (cubierto por diseño de
      compute_yolo_box + tests)
- [x] Clase exclusivamente 0 (T08 lo verifica)
- [x] Seis decimales en coordenadas YOLO (T01-T03 lo verifican)
- [x] Cero huérfanos (check_no_orphans / T10)
- [x] Cero cajas inválidas (T04 rechaza máscara vacía)
- [ ] **outputs/box_audit.csv** — FALTA CREAR
- [ ] **Grilla visual** — FALTA CREAR
- [ ] Extremos auditados — depende del CSV
- [ ] Escritura atómica — a verificar/implementar explícitamente

## Hecho (código y tests, ya en la rama contractual)
- src/data/make_boxes.py — T01-T10 COMPLETO (§8 contrato):
  - compute_yolo_box: extremos + bordes semiabiertos + formato YOLO (§5-6)
  - make_mask_from_alpha: máscara desde canal alpha RGBA (§4)
  - make_mask_from_rgb: máscara desde fondo uniforme RGB (§4)
  - load_and_validate_image: carga/valida imagen decodificable (§3)
  - check_no_orphans (T10): gate de huérfanos, ValueError si hay al menos uno
- tests/test_make_boxes.py: 13/13 tests pasan (T01-T10, sin skips)
- Acuse formal posteado en issue #3 (ACK-001) — los 4 integrantes completaron
- Confirmado acceso al repo

## Pendiente
- **outputs/box_audit.csv + grilla visual** — bloqueante directo para abrir
  el PR de BOX-001, es el siguiente paso a encarar
- CLI/orquestador sobre manifest real de Monserrat (SCR-001 aún sin PR
  abierto) — bloquea auditoría del dataset REAL completo
- configs/dataset.yaml — se retoma bajo SPL-001/integración
- notebooks/eda.ipynb — aún no empezado
- make_splits.py sigue en feat/boxes-andres, sin trasladar todavía a
  feat/andres/SPL-001-make-splits (se hará después de cerrar BOX-001)

## Seguimiento SCR-001 (Monserrat, issue #4) — como reviewer asignado
- S01-S10 y smoke test ejecutados con EXIT CODE 0 según comentario de
  Monserrat en el issue. Aún sin PR abierto.
- Ambigüedad de contrato levantada por Monserrat: §4.7 exige validar "tamaño
  máximo" de imagen, §3 no define límite de bytes — Guillermo mencionó
  (18:07) estar revisando "el tema del tamaño de los archivos de Monse",
  probablemente resolviendo esta ambigüedad.
- Acción mía cuando abra PR: revisión cruzada obligatoria.

## Bloqueantes de contrato aún abiertos
- BOUNDING_BOX_ALGORITHM_CONTRACT.md §3: alpha_threshold,
  background_uniformity_tolerance, foreground_delta, min_foreground_pixels
  → PENDING_G3_PILOT
- DATA_AND_SPLIT_CONTRACT.yaml:
  - split_policy.fixed_seed y ratios → PENDING_O_002
  - quality_rules.final_dataset_size → PENDING_O_001
  - publication.redistribution → PENDING_O_007
- split_policy.test_lock: true — interpretación aún no confirmada

## Cómo retomar
```bash
cd ~/proyectos/project-amarketboundingboxes
git checkout feat/andres/BOX-001-make-boxes
source .venv/bin/activate
pytest tests/test_make_boxes.py -v
# Siguiente paso: crear outputs/box_audit.csv + grilla visual
```

## Acción futura asignada — reproducción independiente de SCR-001
Guillermo (18:xx) le pidió a Monserrat corregir 2 fixtures en
tests/test_scraper_extraction.py: "rights_status": "PILOT_PRIVATE" no
pertenece al enum FROZEN, debe ser "REDISTRIBUTION_PROHIBITED". Cuando
Monserrat publique el nuevo commit con los 15 tests corriendo:
- Me toca reproducir su suite de forma INDEPENDIENTE en mi máquina
  (clonar/pull su rama, correr los 15 tests, confirmar mismo resultado)
- Esto es requisito explícito antes de aprobar y mergear su PR
- Aún no ocurrió — solo Guillermo le pidió el fix a ella, esperando su commit
