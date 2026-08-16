# ADR-003 — Los ledgers vivos se instancian fuera del paquete FROZEN

- Fecha: 2026-08-16
- Estado: Accepted
- Autoridad: Jose Guilermo Carvajal Vaca, coordinador y líder
- Gate: G1
- Relacionada: `ADR-002_REPO_VISIBILITY_AND_PROTECTION.md`; issue #1 (GOV-001)

## Contexto

`docs/governance/05_TEMPLATES/` contiene cuatro ledgers en CSV:

- `EVIDENCE_LEDGER.csv`
- `CONTRIBUTION_LEDGER.csv`
- `CLAIMS_LEDGER.csv`
- `EXPERIMENT_LEDGER.csv`

Los cuatro forman parte del paquete gobernante y están cubiertos por
`docs/governance/MANIFEST.sha256`, que declara los hashes SHA-256 congelados de los 30
archivos del paquete. Esos mismos hashes están registrados en el origen gobernante y en
`06_AUDIT/G0_CLOSURE_20260816.md`.

Los cuatro archivos contienen **únicamente la fila de cabecera**: son plantillas de
esquema, no registros vivos.

El conflicto se observó al ejecutar GOV-001. El punto 10 de
`03_GITHUB/BRANCH_PROTECTION_CHECKLIST.md` exige *"Registrar evidencia en
`EVIDENCE_LEDGER.csv`"*. Escribir la fila en la plantilla habría cambiado su hash, con
tres consecuencias inmediatas:

1. `MANIFEST.sha256` pasaría a validar 29/30 en cualquier clon.
2. Se rompería la cadena de custodia con el origen gobernante y con el cierre de G0.
3. Contravendría la prohibición de modificar documentos FROZEN, vigente en todas las
   fases autorizadas hasta la fecha.

Es decir: cumplir el punto 10 al pie de la letra habría invalidado el control de
integridad que el punto 10 existe para respaldar.

## Decisión

Los **ledgers vivos se instancian fuera del paquete congelado**, conservando exactamente
el esquema de columnas de su plantilla. Las plantillas permanecen intactas y siguen
siendo la fuente del esquema.

Ubicación para la evidencia de gates:

```
docs/evidence/EVIDENCE_LEDGER.csv
```

Reglas derivadas:

- El ledger vivo replica la cabecera de la plantilla sin alterar nombres ni orden de
  columnas. Cambiar el esquema exige modificar la plantilla, y eso es un cambio del
  paquete gobernante con su propia autorización.
- Cada gate escribe su evidencia en el ledger vivo, nunca en la plantilla.
- Los artefactos de evidencia que acompañan a cada fila viven junto al ledger, en
  `docs/evidence/`.
- Si en el futuro se necesitan los otros tres ledgers, se instancian con el mismo
  criterio y en la ubicación que corresponda a su naturaleza; esta ADR fija el principio,
  no solo el caso de la evidencia.

## Alternativas descartadas

| Alternativa | Motivo del descarte |
|---|---|
| Escribir filas en la plantilla dentro de `05_TEMPLATES/` | Rompe `MANIFEST.sha256` y la cadena de custodia con G0 |
| Recalcular el manifiesto tras cada escritura | Vacía de sentido el congelado: los hashes dejarían de probar nada |
| Excluir los ledgers del manifiesto | Reduce la cobertura del paquete gobernante para resolver un problema de ubicación |
| Mantener la evidencia fuera del repositorio | La evidencia dejaría de ser versionada, revisable en PR y auditable |

## Consecuencias

- `MANIFEST.sha256` no cambia y sigue validando **30/30** en clones nuevos.
- Las plantillas de `05_TEMPLATES/` quedan como referencia de esquema, no como registros.
- Todo gate futuro escribe su evidencia en `docs/evidence/`.
- GOV-001 ya aplicó esta decisión: la fila `EV-G1-001` documenta la prueba en vivo de la
  protección de `main` y reside en `docs/evidence/EVIDENCE_LEDGER.csv`.
- Quien audite el proyecto encontrará la evidencia en un único lugar previsible, separado
  del paquete normativo que la gobierna.
