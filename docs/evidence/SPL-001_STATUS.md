# Estado SPL-001 — Andres Poiche

Evidencia y seguimiento de SPL-001 (issue #14), separado de
docs/evidence/BOX-001_STATUS.md por pedido explicito de Guillermo
(code owner, revision del PR #23).

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

## SPL-001 — Alcance técnico completo (commit 450681c)
Los 4 requisitos del issue #14 están cubiertos con datos sintéticos:
- src/data/make_splits.py: ✅ (union-find, class_rule, gate)
- data/manifests/splits.csv: ✅ (generado con scripts/generate_splits_sample.py,
  seed=42, ratios reales O-002, 36 filas sintéticas, split 25/6/5)
- configs/dataset.yaml: ✅ (split_policy con valores reales O-002;
  algorithm/quality_rules/publication siguen con PENDING_* explícitos
  donde corresponde: PENDING_G3_PILOT, PENDING_O_001, PENDING_O_007)
- Evidencia de leakage y reproducibilidad: ✅
  (outputs/splits_leakage_evidence.json, no versionado por gitignore,
  cero violaciones sku_id/duplicate_group_id, 2 corridas idénticas)

27/27 tests en verde (13+6 de BOX-001 + 8 de SPL-001).

PENDIENTE antes de abrir PR de SPL-001:
- Confirmar que no hace falta nada más del checklist de Guillermo
  (comparar contra BOX-001: escritura atómica ya cubierta en
  generate_splits_sample.py con tmp+os.replace)
- Abrir PR independiente, reviewer Monserrat, plantilla oficial

BLOQUEADO hasta que se resuelva O-001 y Monserrat ejecute el crawl
completo: re-ejecutar split FINAL sobre dataset real (no sintético).
Esto es esperado por diseño, no es un pendiente de acción mía.

## PR ABIERTO — SPL-001 formalmente entregado
PR #23: "[SPL-001] Splits reproducibles con exclusividad de grupo (seed=42, ratios O-002)"
https://github.com/guillermocarvajalvaca-dev/project-amarketboundingboxes/pull/23

- Rama: feat/andres/SPL-001-make-splits -> main
- 6 commits, 6 files changed
- Reviewers: Monserrat (@mbarbacardozo, correcta según issue #14) +
  Pablo y Guillermo (forzados por CODEOWNERS del repo, no se pueden
  quitar — Guillermo mencionó que GOV-002 corrige CODEOWNERS)
- Closes #14
- Estado: Awaiting approval (18/08, ~22:19)

SPL-001 queda formalmente entregado con alcance técnico completo
(sintéticos). Pendiente: aprobación de Monserrat, y más adelante,
cuando O-001 se resuelva y Monserrat ejecute el crawl completo,
re-ejecutar el split final sobre el dataset real.

## SPL-001 — Hallazgos de Monserrat resueltos (commit b39bb02)
Monserrat encontró 2 hallazgos reales en PR #23:
1. _build_groups no incluía source_asset_id explícitamente en la
   unión de grupos (dependía implícitamente de sku_id). FIX: unión
   explícita + 2 tests nuevos (exclusividad directa de source_asset_id,
   y caso borde de sku_id con distinto duplicate_group_id).
2. configs/dataset.yaml tenía PENDING_O_007 desactualizado. FIX:
   actualizado con LIVE_DECISION_REGISTER.md — redistribution =
   REDISTRIBUTION_PROHIBITED (LD-003), final_dataset_size =
   UNKNOWN_PENDING_CRAWL_COMPLETION (LD-001, política cerrada,
   número real pendiente del crawl).

10/10 tests en verde. Comentario publicado en PR #23, esperando nueva
revisión de Monserrat.

DATO IMPORTANTE descubierto al buscar O-007: LIVE_DECISION_REGISTER.md
(fusionado via GOV-002/PR#22) confirma que O-001 TAMBIÉN está resuelto
como política (LD-001: "todos los activos únicos ACCEPTED"), aunque
el número real de imágenes sigue UNKNOWN hasta el crawl completo.

## Nueva tarea asignada — issue #24 (BOX-EV-001)
Guillermo asignó registro de evidencia de BOX-001 en el ledger vivo
(ADR-003). Rama: docs/andres/BOX-EV-001-register-evidence (desde main
actualizado). Alcance SOLO documental:
- crear docs/evidence/2026-08-19_BOX-001_implementation_validation.md
- añadir fila EV-G3-BOX-001 en docs/evidence/EVIDENCE_LEDGER.csv
- registrar PR #18, commit final, merge commit, revisión de Monserrat,
  19/19 tests
- declarar EXPLÍCITAMENTE real_dataset_execution = NOT_RUN y
  overall_G3_status = PARTIAL (NO declarar G3 completo)
- NO modificar código, tests, configs, ni documentos FROZEN
Reviewer: Monserrat. Estado: NO INICIADO — próximo paso al retomar.

## PR #23 — Revisión de Guillermo (code owner), 7 puntos pendientes
Tras la aprobación de Monserrat, Guillermo (code owner) dejó
REQUEST_CHANGES con 7 puntos adicionales sobre gobernanza/estructura
(no lógica de negocio). Progreso:

### ✅ Punto 4 — Ampliar verify_no_leakage con source_asset_id
scripts/generate_splits_sample.py: agregado source_asset_id_cross_split_violations
al JSON de evidencia, incluido en cero_leakage. Nuevo test aislado
(mismo source_asset_id, sku_id Y duplicate_group_id ambos distintos).

### ✅ Punto 5 — Validaciones contractuales
src/data/make_splits.py: nuevas funciones _validate_manifest_contract
y _validate_ratios, llamadas al inicio de make_splits:
- columnas obligatorias (sku_id, source_asset_id, duplicate_group_id)
- sin nulos en identificadores de grupo
- class_id == 0 si la columna está presente (no se exige como
  obligatoria para no romper manifiestos existentes sin esa columna)
- ratios: exactamente 3, numéricos, no negativos, suman 1.0
- 7 tests nuevos, cada uno verificando un error claro y específico

18/18 tests en verde. Script de muestra sigue funcionando igual
(25/6/5, cero leakage en las 3 dimensiones).

### ⏳ Pendientes
1. Reviewers/estado del PR (Closes→Refs, declarar status explícito)
2. Mover CSV sintético a data/sample/splits_synthetic.csv
3. ✅ COMPLETO — Separar evidencia: creado SPL-001_STATUS.md propio; BOX-001_STATUS.md revertido a la version de main (sin contenido de SPL-001)
6. Pandas como dependencia — depende de ENV-002 (issue #25), no es acción mía
7. Re-ejecutar checklist completo al final

## ✅ Punto 1 completo — Reviewers y estado del PR
Descripción del PR #23 actualizada:
- Reviewer SPL-001: @guillermocarvajalvaca-dev
- Reviewer CFG-001: @pablolinares1801
- Monserrat queda como revisora independiente adicional
- Issue: Closes #14 -> Refs #14 (issue permanece abierto)
- Declarado explícitamente: implementation_status=PASSED_ON_SYNTHETIC_FIXTURE,
  real_dataset_execution=NOT_RUN, overall_G3_status=PARTIAL

Puntos 1-5 completos. Punto 6 (pandas como dependencia) depende de
ENV-002 (issue #25), no es acción propia. Falta punto 7: re-ejecutar
checklist completo y publicar evidencia final en el PR.
