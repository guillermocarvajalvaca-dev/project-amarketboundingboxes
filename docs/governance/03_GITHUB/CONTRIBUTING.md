# Contribuir a Project AmarketBoundingBoxes

## Antes de empezar

Lee el SDD, el manual, el contrato del módulo y tu brief. No programes una tarea sin
issue, owner, reviewer, entradas, salidas y `done_when` definidos.

## Flujo

1. Actualiza `main`.
2. Crea rama `<tipo>/<owner>/<task-id>-descripcion`.
3. Modifica solo artefactos de tu issue.
4. Agrega pruebas y documentación afectada.
5. Ejecuta y registra comandos/exit codes.
6. Abre PR y completa toda la plantilla.
7. Solicita revisión al reviewer asignado.
8. Atiende cambios; no hagas self-merge ni self-approval.

## Commits

```text
feat: implement smoke scraper manifest
test: cover corrupt image rejection
fix: preserve inclusive right border
docs: record dataset limitation
```

Configura identidad Git propia. No compartas una misma cuenta para aparentar
contribución.

## Reglas

- Sin rutas absolutas.
- Sin secretos, cookies, tokens o `.env`.
- Sin datasets/pesos grandes.
- Sin outputs generados innecesarios.
- Sin cambios de contrato ocultos.
- Sin métricas o afirmaciones sin evidencia.
- Asistencia de IA declarada en el PR según política institucional.

## Revisión

El reviewer ejecuta el caso mínimo y registra el resultado. Revisa contrato,
comportamiento, errores, reproducibilidad, seguridad, documentación y ownership. No
reescribe el módulo para aprobarlo.
