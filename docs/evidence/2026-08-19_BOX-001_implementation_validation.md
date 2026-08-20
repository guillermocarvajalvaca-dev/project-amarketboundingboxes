# Evidencia BOX-001 — Implementación y validación (fixtures sintéticos)

**Fecha:** 2026-08-19
**Autor:** Andres Poiche (@andrespoiche)
**Revisor independiente:** Monserrat Barba (@mbarbacardozo)
**Gate:** G3 — Dataset Construction
**Issue:** #5 (cerrado por merge de PR #18)
**PR:** #18
**Merge commit:** `17c4ac3ecdf0dd660e0255a30602d00e621f73e7`

## Alcance de esta evidencia

Este documento registra la implementación y validación de BOX-001
(`src/data/make_boxes.py`) contra `BOUNDING_BOX_ALGORITHM_CONTRACT.md`,
**exclusivamente sobre fixtures sintéticos**. No cubre la ejecución
sobre el dataset real de Amarket.

- `implementation_status`: `PASSED_ON_SYNTHETIC_FIXTURE`
- `real_dataset_execution`: `NOT_RUN`
- `overall_G3_status`: `PARTIAL`

**No se declara G3 completo.** La ejecución sobre el dataset real está
bloqueada hasta que Monserrat complete el crawl completo de SCR-001 y
se congele el manifest.

## Funciones implementadas

- `compute_yolo_box`: extremos + bordes semiabiertos + formato YOLO (§5-6)
- `make_mask_from_alpha`: máscara desde canal alpha RGBA (§4)
- `make_mask_from_rgb`: máscara desde fondo uniforme RGB (§4)
- `load_and_validate_image`: carga/valida imagen decodificable (§3)
- `check_no_orphans` (T10): gate de huérfanos label/imagen (§8)
- `audit_image` (§7): fila de auditoría de 30 columnas, con fallback
  automático alpha→rgb según corresponda

## Ejecución

```text
pytest tests/test_make_boxes.py tests/test_box_audit.py -v
```

- **Exit code:** 0
- **Resultado:** 19/19 tests PASSED (13 de T01-T10, 6 de auditoría)
- **Muestra reproducible:** `scripts/generate_box_audit_sample.py` genera
  5 imágenes sintéticas (3 aceptadas, 2 rechazadas, cada rechazo con
  motivo trazable), `outputs/box_audit.csv` (30 columnas) y
  `outputs/box_audit_grid.png` (QA visual)

## Revisión independiente (Monserrat)

Tres submissions de revisión registradas:

1. **CHANGES_REQUESTED:** 2 hallazgos —
   (a) `audit_image` no integraba `make_mask_from_rgb` para el caso RGB
   con fondo uniforme; (b) escritura del label `.txt` no era atómica.
   Ambos corregidos (commits `8e1746a` y `1955640`).
2. **APPROVED sobre commit `0f95d71`:** reproducción completa, 19/19
   tests, QA visual confirmado, reproducibilidad por SHA-256 verificada.
   Esta aprobación quedó posteriormente DISMISSED de forma automática
   al cambiar el head (protección de rama: dismiss_stale_reviews).
3. **APPROVED final sobre commit `1863900`:** commit que corrigió
   nomenclatura de test (29→30 columnas); Monserrat re-aprobó sobre
   ese commit tras confirmar que el delta no afectaba lógica.

## Bloqueantes de contrato aún abiertos (no afectan esta evidencia)

- `BOUNDING_BOX_ALGORITHM_CONTRACT.md` §3: `alpha_threshold`,
  `background_uniformity_tolerance`, `foreground_delta`,
  `min_foreground_pixels` — `PENDING_G3_PILOT`

## Próximos pasos (fuera de alcance de esta evidencia)

- Ejecutar `audit_image` sobre el dataset real de Amarket, una vez que
  Monserrat complete el crawl completo y congele el manifest (SCR-001)
- Generar `outputs/box_audit.csv` real y su grilla de QA visual
- Declarar `overall_G3_status = COMPLETE` solo después de esa ejecución
