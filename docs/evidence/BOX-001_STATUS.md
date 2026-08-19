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

## PR ABIERTO — BOX-001 formalmente entregado
PR #18: "[BOX-001] Bounding boxes, gate de huérfanos y auditoría (T01-T10 completo)"
https://github.com/guillermocarvajalvaca-dev/project-amarketboundingboxes/pull/18

- Rama: feat/andres/BOX-001-make-boxes -> main
- 7 commits, 8 files changed
- Reviewer: Monserrat Barba (@mbarbacardozo)
- Closes #5
- Estado: Awaiting approval (16/08, ~21:05)

BOX-001 queda formalmente entregado. Próximo trabajo: trasladar
make_splits.py + configs/dataset.yaml a feat/andres/SPL-001-make-splits
(issue #14), cuando retome sesión.

## SCR-001 — Revisión independiente COMPLETADA
Revisión publicada como comentario en PR #11 (16/08, ~23:35).
Los 9 puntos del checklist de Guillermo pasaron:
1. Suite 15/15 ✅
2. rights_status = REDISTRIBUTION_PROHIBITED ✅
3. CLI --output-dir/--manifest ✅
4. Escritura atómica (tempfile + os.replace + limpieza) ✅
5. Smoke test 3/3 ✅
6. Idempotencia (accepted_this_run=0 en 2da corrida) ✅
7. SHA-256 manifest idéntico entre mis 2 corridas (ec114901...) —
   difiere del hash de Monserrat (11fb5036...), esperado por catálogo vivo
8. Inspección visual 3 imágenes: fondo uniforme, aisladas, sin datos
   personales. Nota menor: SKU 0610985012303 es pack de 2 unidades
9. git diff --check limpio, sin modificaciones no declaradas

Decisión: APPROVE

Hallazgos de infraestructura reportados (no bloqueantes para este PR):
- conftest.py no versionado en ninguna rama, incluida main
- requirements.txt vive en chore/env-001, sin mergear a main

Nota: el PR sigue con "Changes requested" de la revisión de coordinación
anterior de Guillermo — pendiente que él la actualice/dismissee para
destrabar el merge. Mi aprobación cubre específicamente los 9 puntos
de revisión independiente que él me asignó.

## SCR-001 — Aprobación formal registrada en GitHub
Además del comentario detallado, se envió "Submit review" con Approve
en la pestaña Files changed del PR #11 (16/08, ~23:55). Queda registrado
formalmente en el sistema de GitHub como aprobación de @andrespoiche,
no solo como comentario de texto.

## Correcciones tras revisión de Monserrat (PR #18) — AMBOS HALLAZGOS RESUELTOS
Monserrat (revisión REQUEST_CHANGES) encontró 2 hallazgos reales:

1. audit_image no integraba make_mask_from_rgb (solo usaba alpha,
   hardcodeado). Relevante porque las imágenes reales de SCR-001 son
   RGB con fondo uniforme, sin alpha real -> audit_image no podía
   procesar el dataset real tal como estaba.
   FIX (commit 8e1746a): fallback automático a make_mask_from_rgb
   cuando alpha falla por estar completamente opaco. mask_method se
   registra correctamente. Nuevo test con imagen RGB de fondo uniforme.

2. Escritura del label .txt no era atómica (usaba open() directo),
   pese a que este mismo .md afirmaba lo contrario ("tanto en labels
   como en CSV"). Esa afirmación era incorrecta y quedó corregida con
   el fix real.
   FIX (commit 1955640): mismo patrón tmp+os.replace+fsync que ya usa
   el CSV, con limpieza ante fallo. Nuevo test simula fallo real
   (mock de os.replace) y confirma que no queda archivo parcial.

19/19 tests en verde tras ambas correcciones. Script de muestra
reproducible sigue funcionando sin cambios de comportamiento.
Pendiente: esperar nueva revisión de Monserrat sobre PR #18.

## BOX-001 — MERGEADO (commit 17c4ac3 en main)
PR #18 aprobado por Monserrat (incluyendo re-aprobación tras el hallazgo
menor de 29->30 columnas) y mergeado exitosamente a main. BOX-001 cerrado
formalmente. Rama feat/andres/BOX-001-make-boxes conservada (no borrada).

## SPL-001 (issue #14) — EN CURSO
Datos confirmados del issue:
- Rama: feat/andres/SPL-001-make-splits
- Reviewer: Monserrat (@mbarbacardozo)
- Alcance: make_splits.py + data/manifests/splits.csv + configs/dataset.yaml
  + evidencia de leakage y reproducibilidad
- Restricción: NO ejecutar split final hasta cerrar O-001/O-002 y recibir
  handoff aceptado de BOX-001 (BOX-001 ya cerrado ✅)

DECISIÓN O-002 YA RESUELTA por Guillermo (16/08/2026):
- fixed_seed = 42
- train = 0.70, validation = 0.15, test = 0.15
- Coincide con los defaults que ya tenía make_splits.py

O-001 (tamaño final del dataset) SIGUE PENDIENTE — depende del crawl
completo de SCR-001. Según secuencia de Guillermo (18/08, WhatsApp):
GOV-002 -> merge PR #11 -> merge PR #18 (ya hecho) -> Monserrat ejecuta
crawl completo -> Andres ejecuta boxes sobre dataset real -> Andres
termina SPL/dataset.yaml/splits.csv/evidencia anti-leakage con datos reales.

PR #11 (SCR-001) sigue bloqueado: Guillermo tiene "Changes requested"
sin actualizar (aunque ya aprobé yo como segundo reviewer). Depende de
que Guillermo revise su propia review — no es acción mía. Existe PR #22
de Guillermo (GOV-002) en curso, probablemente destrabe esto.

Hecho en esta rama (con sintéticos, mientras se espera el dataset real):
- make_splits.py + tests trasladados desde feat/boxes-andres
- Comentario de tests actualizado: O-002 resuelto, ya no PENDING
- Nuevo test con valores reales O-002 (seed=42, ratios 0.70/0.15/0.15)
  sobre manifest de 20 grupos
- 8/8 tests en verde

Pendiente en SPL-001:
- data/manifests/splits.csv (muestra reproducible con sintéticos)
- configs/dataset.yaml
- evidencia de leakage y reproducibilidad (documento explícito)
- Abrir PR independiente, reviewer Monserrat
- CUANDO llegue el dataset real: re-ejecutar split final sobre datos
  reales (bloqueado hasta entonces por diseño)
