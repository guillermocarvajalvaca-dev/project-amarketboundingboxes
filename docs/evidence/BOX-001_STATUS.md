# Estado BOX-001 — Andres Poiche
Última actualización: 2026-08-16, commit 1cea4f3 en rama feat/andres/BOX-001-make-boxes
(rama contractual activa — feat/boxes-andres conservada intacta como evidencia legacy)

## RESOLUCIÓN OFICIAL DE GUILLERMO (16/08, ~18:10-18:20)
1. **Rama:** `feat/andres/BOX-001-make-boxes` — HECHO
2. **Reviewer:** Monserrat (@mbarbacardozo) para BOX-001 y SPL-001
3. **Scope:** make_splits.py y dataset.yaml van en SPL-001 (#14):
   https://github.com/guillermocarvajalvaca-dev/project-amarketboundingboxes/issues/14
4. **requirements-boxes.txt:** no se incluye en ningún PR. Único
   requirements.txt del proyecto (pillow==12.3.0, numpy==2.4.6,
   ultralytics==8.4.120, PyYAML==6.0.3)
5. **feat/boxes-andres se conserva intacta** — no borrar, no force-push

## Checklist de verificación antes de abrir PR de BOX-001 — COMPLETO
- [x] 16/16 tests en verde (13 T01-T10 + 3 audit_image)
- [x] Una etiqueta válida por cada imagen aceptada
- [x] Clase exclusivamente 0
- [x] Seis decimales en coordenadas YOLO
- [x] Cero huérfanos (check_no_orphans / T10)
- [x] Cero cajas inválidas
- [x] outputs/box_audit.csv — generado vía script reproducible
- [x] Grilla visual — generada, QA visual clara (ACCEPTED/REJECTED)
- [x] Extremos auditados (x_min/y_min/x_max/y_max en CSV)
- [x] Escritura atómica (.tmp + os.replace, tanto en labels como en CSV)

**BOX-001 listo para abrir PR.**

## Hecho (código y tests, en la rama contractual)
- src/data/make_boxes.py — T01-T10 COMPLETO (§8 contrato):
  - compute_yolo_box, make_mask_from_alpha, make_mask_from_rgb,
    load_and_validate_image, check_no_orphans (T10), audit_image (§7)
- tests/test_make_boxes.py: 13/13 | tests/test_box_audit.py: 3/3
- scripts/generate_box_audit_sample.py: genera muestra reproducible de
  5 imágenes sintéticas -> outputs/box_audit.csv + outputs/box_audit_grid.png
  (outputs/ no se commitea, gitignored, va a Google Drive por contrato)
- Acuse formal posteado en issue #3 (ACK-001)
- Confirmado acceso al repo

## Bugs encontrados y corregidos durante la generación de la muestra
1. **make_mask_from_alpha:** condición `np.all(alpha == alpha.max())` era
   redundante e incorrecta — siempre verdadera si alpha es uniforme, sin
   importar si es 0 (transparente) o 255 (opaco). Causaba que una imagen
   100% transparente se rechazara con el mensaje incorrecto de "completamente
   opaco". Fix: se quitó esa condición, solo queda `alpha == 255`.
2. **audit_image:** al calcular extremos manualmente con mask.nonzero(),
   una máscara vacía causaba un error técnico de numpy (`zero-size array to
   reduction operation minimum`) en vez del mensaje de negocio esperado.
   Fix: chequeo explícito `if not mask.any()` antes de calcular extremos,
   con el mismo mensaje que usa compute_yolo_box.
3. Ninguno de estos bugs lo detectaban los tests unitarios existentes
   (T04 testea compute_yolo_box directo, sin pasar por make_mask_from_alpha)
   — solo se detectaron al generar datos reales con el script de muestra.
   Lección: correr el pipeline end-to-end con datos sintéticos variados
   destapa bugs que los tests aislados no cubren.

## Pendiente (fuera de alcance de BOX-001, va en SPL-001 o después)
- CLI/orquestador sobre manifest real de Monserrat (SCR-001 aún sin
  merge) — bloquea auditoría del dataset REAL completo
- make_splits.py + configs/dataset.yaml — pendiente trasladar a
  feat/andres/SPL-001-make-splits (después de cerrar BOX-001)
- notebooks/eda.ipynb — aún no empezado

## Tarea asignada — Revisión independiente de SCR-001 (PENDIENTE, no iniciada)
Guillermo (16/08, 19:48) asignó revisión independiente sobre PR #11, commit
exacto: d63f152c6c9a3578533c5bf54ec8861c7537baeb

Checklist a verificar:
1. Suite completa: 15/15 tests
2. rights_status = REDISTRIBUTION_PROHIBITED (fix de Monserrat ya aplicado)
3. CLI con --output-dir y --manifest
4. Escritura atómica y limpieza ante fallo
5. Smoke test de 3 productos
6. Segunda ejecución idempotente
7. SHA-256 del manifest sin cambios
8. Inspección visual de las 3 imágenes
9. git diff --check + ausencia de modificaciones locales no declaradas

Restricción: NO ejecutar crawl completo, solo smoke test contractual.
Entregable: registrar en el PR #11 comando reproducido, resultados,
diferencias, y decisión APPROVE / REQUEST_CHANGES.

Equipo pausó la sesión del 16/08 (~20:00); retoman en horario de clases,
foco fuerte el martes.

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
pytest tests/test_make_boxes.py tests/test_box_audit.py -v
# Siguiente paso: abrir PR de BOX-001 (reviewer: Monserrat) usando la
# plantilla del repo (Identidad, Contrato, Ejecución, Checklist, etc.)
```
