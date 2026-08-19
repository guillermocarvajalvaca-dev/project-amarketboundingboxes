# Evidencia — Prueba de la protección de `main`

- Evidence ID: `EV-G1-001`
- Gate: G1
- Requisito: GOV-001 (issue #1)
- Fecha: 2026-08-16
- Ejecutor: Jose Guilermo Carvajal Vaca (`@guillermocarvajalvaca-dev`), coordinador
- Commit de `main` bajo prueba: `eb01b2c9236b6f7ce8abc457e71d880aae153dae`

Cierra los puntos 9 y 10 de
[`docs/governance/03_GITHUB/BRANCH_PROTECTION_CHECKLIST.md`](../governance/03_GITHUB/BRANCH_PROTECTION_CHECKLIST.md):
*"Probar la regla con un PR pequeño de documentación"* y *"Registrar evidencia"*.

El checklist establece que **no se declara protección activa hasta observar la
configuración o probarla**. La lectura de API por sí sola no basta; por eso este PR
existe.

## 1. Configuración observada por API en G1

Comando:

```
gh api repos/guillermocarvajalvaca-dev/project-amarketboundingboxes/branches/main/protection
```

Respuesta HTTP 200. Valores observados:

| Control | Valor observado | Punto del checklist |
|---|---|---|
| `enforce_admins` | `true` | 3 — prohibir push directo, sin excepción para administradores |
| `required_pull_request_reviews` | presente | 4 — exigir pull request antes de merge |
| `required_approving_review_count` | `1` | 5 — al menos una aprobación |
| `dismiss_stale_reviews` | `true` | 6 — invalidar aprobaciones al cambiar el PR |
| `required_conversation_resolution` | `true` | 7 — exigir resolución de conversaciones |
| `require_code_owner_reviews` | `true` | 8 — exigir revisión CODEOWNERS |
| `allow_force_pushes` | `false` | 9 — bloquear force-push |
| `allow_deletions` | `false` | 9 — bloquear eliminación |
| `required_status_checks` | `null` | 10 — sin checks, no existe CI real todavía |

Verificación complementaria:

```
gh api repos/.../branches/main  ->  {"name": "main", "protected": true}
```

## 2. Prueba activa

Este mismo PR es la prueba. Es un cambio pequeño y exclusivamente documental
(`docs/evidence/`), diseñado para comprobar el comportamiento real de la regla sin
alterar contratos ni código de módulo.

**Resultado esperado:** GitHub debe **bloquear el merge** mientras no exista la
aprobación requerida, y debe exigir la revisión del code owner de `docs/`
(`@mbarbacardozo`, según `.github/CODEOWNERS`). El autor del PR es el administrador del
repositorio; con `enforce_admins = true` tampoco él puede fusionarlo por su cuenta.

La observación de ese bloqueo se registra en la sección 3 y en
`docs/evidence/EVIDENCE_LEDGER.csv`.

## 3. Resultado observado

Observado el 2026-08-16 sobre el PR #8, **antes de cualquier aprobación**.

Comando:

```
gh pr view 8 --json mergeable,mergeStateStatus,reviewDecision,reviewRequests
gh api repos/.../pulls/8 --jq '.mergeable_state'
```

| Campo | Valor observado | Lectura |
|---|---|---|
| `mergeable` | `MERGEABLE` | no hay conflictos de contenido |
| `mergeStateStatus` | **`BLOCKED`** | la protección impide la fusión |
| `mergeable_state` (REST) | **`blocked`** | confirma lo anterior por la otra API |
| `reviewDecision` | **`REVIEW_REQUIRED`** | falta la aprobación exigida |
| `reviewRequests` | `mbarbacardozo` | revisión del code owner solicitada |

**Conclusión: la regla se comporta según lo configurado.** El PR no es fusionable pese a
no tener conflictos y pese a que su autor administra el repositorio. `enforce_admins = true`
se comporta como se esperaba: el coordinador no puede saltarse la revisión.

No se intentó forzar la fusión. El merge ocurrirá cuando `@mbarbacardozo` apruebe.

Puntos 9 y 10 del checklist: **cerrados**.

## 4. Nota sobre el ledger

`docs/governance/05_TEMPLATES/EVIDENCE_LEDGER.csv` es una **plantilla** (solo cabecera)
y forma parte del paquete gobernante validado por `docs/governance/MANIFEST.sha256`.
Escribir filas en ella rompería esos hashes y contravendría la prohibición de modificar
documentos FROZEN. El ledger vivo se instancia por tanto en
`docs/evidence/EVIDENCE_LEDGER.csv`, con el mismo esquema de trece columnas.
