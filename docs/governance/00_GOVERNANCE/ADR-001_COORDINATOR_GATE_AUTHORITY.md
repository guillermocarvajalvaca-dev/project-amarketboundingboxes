# ADR-001 — Autoridad del coordinador sobre fases

- Estado: `ACCEPTED`
- Fecha: `2026-08-16`
- Decisor: Jose Guilermo Carvajal Vaca
- GitHub: `guillermocarvajalvaca-dev`
- Afecta: SDD, manual, G0–G6 y registro de decisiones

## Contexto

La propuesta v0.2.0 exigía aceptación de los cuatro integrantes antes de congelar el
contrato. El coordinador declaró que su aprobación es suficiente para continuar cada
paso por su rol de coordinador y líder del proyecto.

## Decisión

La autorización expresa de Guillermo basta para abrir o cerrar una fase. Los
acknowledgements de Monserrat, Andrés y Pablo se registran como evidencia de lectura y
coordinación, pero no bloquean una fase autorizada.

La aceptación del 2026-08-16 cierra G0 y autoriza G1. No constituye autorización
automática para G2–G6; cada transición requiere una decisión expresa del coordinador.

## Límites preservados

- Cada integrante implementa y ejecuta solamente los artefactos asignados.
- La contribución se demuestra mediante issue, rama, commits, PR y evidencia.
- Nadie aprueba su propio PR.
- El coordinador integra, pero no reasigna ni reescribe retroactivamente la autoría.
- Stop-the-Line sigue aplicando ante seguridad, derechos, fuga, contrato roto o prueba
  crítica fallida.

## Consecuencias

G1 puede iniciar sin las otras tres aceptaciones. El riesgo residual es que un
integrante desconozca su brief; se mitiga enviando el brief antes de su primer issue y
registrando su acknowledgement sin detener el bootstrap del repositorio.
