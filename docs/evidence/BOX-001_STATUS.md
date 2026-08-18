
## BOX-001 — Aprobado por Monserrat, con ajuste post-aprobación
PR #18 fue aprobado (Changes approved) por Monserrat tras resolver sus
2 hallazgos (RGB + atomicidad de labels). Se corrigió además su hallazgo
menor (test renombrado 29->30 columnas, commit 1863900) — esto invalidó
la aprobación por protección de rama (dismiss automático de stale
review). Se comentó en el PR pidiendo nueva aprobación rápida (cambio
trivial, sin lógica nueva). PENDIENTE: re-aprobación de Monserrat y merge.

## SPL-001 (issue #14) — INICIADO
Datos confirmados del issue:
- Rama: feat/andres/SPL-001-make-splits (creada, commit be1e4ec)
- Reviewer: Monserrat (@mbarbacardozo)
- Alcance: make_splits.py + data/manifests/splits.csv + configs/dataset.yaml
  + evidencia de leakage y reproducibilidad
- Restricción: NO ejecutar split final hasta cerrar O-001/O-002 y recibir
  handoff aceptado de BOX-001

DECISIÓN O-002 YA RESUELTA por Guillermo (16/08/2026):
- fixed_seed = 42
- train = 0.70, validation = 0.15, test = 0.15
- Coincide con los defaults que ya tenía make_splits.py

O-001 (tamaño final del dataset) SIGUE PENDIENTE — depende del crawl
completo de SCR-001 (que sigue bloqueado, solo se autorizó smoke test).
No es tarea mía resolverlo, solo esperar.

Hecho en esta rama:
- make_splits.py + tests trasladados desde feat/boxes-andres (con
  conftest.py, __init__.py de soporte)
- Comentario de tests actualizado: ya no dice PENDING_O_002
- Nuevo test test_ratios_reales_O_002_reparto_proporcional con los
  valores reales aprobados (seed=42, ratios 0.70/0.15/0.15) sobre
  manifest de 20 grupos
- 8/8 tests en verde

Pendiente en SPL-001:
- data/manifests/splits.csv (generar muestra reproducible con sintéticos,
  igual patrón que box_audit.csv en BOX-001)
- configs/dataset.yaml (retomar, había quedado pausado por Guillermo)
- evidencia de leakage y reproducibilidad (documento explícito)
- Abrir PR independiente con reviewer Monserrat
