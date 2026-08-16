# Estado BOX-001 — Andrés Poiche
Última actualización: 2026-08-16, commit 41aade9 en rama feat/boxes-andres
(rama legacy, conservada como evidencia — ver resolución oficial abajo)

## RESOLUCIÓN OFICIAL DE GUILLERMO (16/08, ~18:10) — leer primero
Respuesta a mis 3 preguntas + creación de SPL-001:

1. **Rama:** BOX-001 se trabaja en `feat/andres/BOX-001-make-boxes`
   (nueva rama, creada desde `main` actualizado).
2. **Reviewer:** Monserrat (@mbarbacardozo) — para BOX-001 y SPL-001.
   Pablo NO es reviewer de ninguno de los dos.
3. **Scope:** `make_splits.py` y `configs/dataset.yaml` NO van en BOX-001.
   Van en `feat/andres/SPL-001-make-splits`, bajo el issue **SPL-001 (#14)**,
   ya creado: https://github.com/guillermocarvajalvaca-dev/project-amarketboundingboxes/issues/14
4. **`requirements-boxes.txt`:** no se incluye en NINGUNO de los 2 PR.
   El proyecto usa un único `requirements.txt` aprobado.
5. **`feat/boxes-andres` (esta rama actual) se conserva intacta** — no
   borrar, no force-push. Es evidencia de trabajo, no se descarta.

## Plan de ejecución (en curso)
- [ ] Actualizar main localmente
- [ ] Crear `feat/andres/BOX-001-make-boxes` desde main
- [ ] Trasladar SOLO: src/data/make_boxes.py + tests/test_make_boxes.py
- [ ] Resolver dependencias en requirements.txt único (no crear uno propio)
- [ ] Producir outputs/box_audit.csv + grilla visual (AÚN NO EMPEZADO)
- [ ] Verificar checklist completo antes de abrir PR (ver abajo)
- [ ] Abrir PR de BOX-001, reviewer: Monserrat
- [ ] Crear `feat/andres/SPL-001-make-splits` desde main
- [ ] Trasladar: src/data/make_splits.py + tests/test_make_splits.py +
      configs/dataset.yaml (pendiente de crear)
- [ ] Abrir PR de SPL-001, reviewer: Monserrat

## Checklist de verificación antes de abrir PR de BOX-001 (exigido por Guillermo)
Además de 13/13 tests en verde, verificar explícitamente:
- [ ] Una etiqueta válida por cada imagen aceptada
- [ ] Clase exclusivamente 0
- [ ] Seis decimales en coordenadas YOLO
- [ ] Cero huérfanos (cubierto por check_no_orphans / T10)
- [ ] Cero cajas inválidas
- [ ] Extremos auditados
- [ ] Escritura atómica
- [ ] Grilla visual generada

## Hecho (trabajo técnico ya validado, a trasladar a las ramas nuevas)
- Entorno: .venv con pytest 9.1.1, numpy 2.5.2, pillow 12.3.0, pandas
- src/data/make_boxes.py — T01-T10 COMPLETO (§8 contrato):
  - compute_yolo_box, make_mask_from_alpha, make_mask_from_rgb,
    load_and_validate_image, check_no_orphans (T10)
- tests/test_make_boxes.py: 13/13 tests pasan (T01-T10 completo, sin skips)
- src/data/make_splits.py — cobertura completa de §split_policy:
  - group_exclusivity (union-find), derivative_rule, class_rule, gate de
    grupos insuficientes, ratios/seed como parámetros
- tests/test_make_splits.py: 7/7 tests pasan
- Acuse formal posteado en issue #3 (ACK-001) — los 4 integrantes completaron
- Confirmado acceso al repo

## Pendiente
- outputs/box_audit.csv + grilla visual (bloqueante para abrir PR de BOX-001)
- CLI/orquestador sobre manifest real de Monserrat (SCR-001 aún no entregado,
  sin PR abierto todavía) — bloquea auditoría del dataset REAL completo
- configs/dataset.yaml — detenido, se retoma bajo SPL-001/integración
- notebooks/eda.ipynb — aún no empezado

## Seguimiento SCR-001 (Monserrat, issue #4) — como reviewer asignado
- S01-S10 y smoke test ejecutados con EXIT CODE 0 según comentario de
  Monserrat en el issue. Aún sin PR abierto.
- Ambigüedad de contrato levantada por Monserrat: §4.7 exige validar "tamaño
  máximo" de imagen, §3 no define límite de bytes — pendiente que el equipo
  defina el valor o difiera la validación.
- Guillermo mencionó por chat (18:07) estar revisando "el tema del tamaño
  de los archivos de Monse" — probablemente relacionado a esta ambigüedad.
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
git checkout feat/boxes-andres   # rama legacy, NO tocar/force-push
source .venv/bin/activate
# Trabajo activo ahora en feat/andres/BOX-001-make-boxes (ver plan arriba)
```
