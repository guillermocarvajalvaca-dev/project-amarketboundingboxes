# ADR-002 — Visibilidad del repositorio y protección de `main`

- Fecha: 2026-08-16
- Estado: Accepted
- Autoridad: Jose Guilermo Carvajal Vaca, coordinador y líder
- Gate: G1
- Sustituye: ninguna. Complementa `docs/governance/00_GOVERNANCE/ADR-001_COORDINATOR_GATE_AUTHORITY.md`

## Contexto

`BRANCH_PROTECTION_CHECKLIST.md` exige proteger `main`: prohibir push directo,
exigir pull request con al menos una aprobación, invalidar aprobaciones al
cambiar el PR, exigir revisión CODEOWNERS y resolución de conversaciones, y
bloquear force-push y eliminación.

El repositorio se creó privado. Al aplicar la protección, la API respondió:

```
PUT /repos/.../branches/main/protection
403: "Upgrade to GitHub Pro or make this repository public to enable this feature."
```

La protección de ramas en repositorios privados requiere un plan de pago. Se
intentó contratar GitHub Pro y el pago fue rechazado por la tarjeta, de modo que
esa vía queda descartada por causa ajena al proyecto.

Sin protección activa, `main` admite push directo y el control central de
revisión cruzada del contrato no existe. G1 no puede cerrarse en esas
condiciones.

## Decisión

1. El repositorio pasa a ser **público**, única vía gratuita que habilita la
   protección de ramas.
2. La protección de `main` se aplica con `enforce_admins = true`, de modo que la
   regla alcanza también al coordinador y nadie puede hacer push directo.
3. Antes de publicar se eliminó toda dirección de correo personal del
   repositorio.

Sobre el punto 3, lo verificado en la ejecución:

- Los correos personales del equipo aparecían **0 veces** en el contenido de los
  archivos versionados. No hubo que redactar ningún documento, y por tanto los
  documentos FROZEN conservan intactos los hashes declarados en el origen
  gobernante y en `G0_CLOSURE_20260816.md`. `MANIFEST.sha256` no se modificó.
- Sí había un correo personal en los **metadatos** del commit raíz, que `git grep`
  no detecta. El commit se reescribió con la identidad
  `guillermocarvajalvaca-dev@users.noreply.github.com`, fijada solo en la
  configuración local del repositorio.
- Un force-push no habría bastado: el commit original permanece recuperable por
  SHA en los servidores de GitHub aunque deje de estar referenciado. Se eliminó y
  recreó el repositorio remoto para garantizar que ese objeto no exista. Se
  verificó por API que el SHA antiguo devuelve `422 No commit found`.

## Alternativas descartadas

| Alternativa | Motivo del descarte |
|---|---|
| Contratar GitHub Pro y mantenerlo privado | Pago rechazado por la tarjeta |
| Mantenerlo privado sin protección | Incumple `BRANCH_PROTECTION_CHECKLIST.md`; permite push directo a `main` |
| Debilitar la regla (sin CODEOWNERS o sin aprobación) | Elimina la revisión cruzada, que es el control central del contrato |
| Trasladarlo a una organización | El plan gratuito de organización tiene la misma limitación en repositorios privados |
| Force-push sobre el remoto existente | No elimina el commit antiguo de los servidores de GitHub |

## Consecuencias

- El plan de scraping, los contratos de datos y el trabajo previo a la entrega
  quedan expuestos públicamente antes de la fecha de entrega del 2026-08-19.
- Cualquier persona puede leer, clonar y bifurcar el repositorio. El trabajo es
  atribuible y auditable, pero también copiable por terceros.
- Los briefs de ejecución individuales quedan públicos. No contienen datos
  personales de contacto, pero sí nombres propios y asignaciones.
- A cambio, `main` queda protegido: sin push directo, con revisión obligatoria y
  CODEOWNERS, y la regla alcanza también a quien administra el repositorio.
- La visibilidad **debe revisitarse una vez calificado el proyecto**. Volver a
  privado tras la calificación no requiere una nueva ADR si la protección deja de
  ser necesaria; si se mantiene la necesidad de protección, requerirá plan de pago.

## Verificación

- Clon nuevo del remoto: 30/30 hashes de `MANIFEST.sha256` válidos.
- Clon nuevo: 0 coincidencias de correos personales en contenido e historial.
- SHA del commit original: `422 No commit found`.
