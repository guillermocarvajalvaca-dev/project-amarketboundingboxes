# ADR-004 — Registro vivo de decisiones y autorizaciones

- Fecha: 2026-08-18
- Estado: `PROPOSED`
- Propuesta por: ejecución GOV-002 sobre la rama `chore/guillermo/GOV-002-governance-reconciliation`
- Autoridad requerida para aceptarla: Jose Guillermo Carvajal Vaca, coordinador y líder
- Gate: G2/G3 (regularización documental)
- Relacionada: `ADR-002_REPO_VISIBILITY_AND_PROTECTION.md`, `ADR-003_LIVE_LEDGERS_OUTSIDE_FROZEN_PACKAGE.md`; issue #21 (GOV-002)

`PROPOSED` en el sentido del §7 del contrato SDD: especificada, sin aprobación. No
gobierna hasta que el coordinador la acepte expresamente.

Jose Guillermo Carvajal Vaca actúa a la vez como proponente y redactor de esta ADR y como
coordinador con autoridad para aceptarla. Redactarla, commitearla o abrir el PR no
constituye por sí solo la aceptación: el paso de `PROPOSED` a `ACCEPTED` exige una
decisión explícita, fechada y trazable del coordinador.

La revisión independiente de Monserrat Barba, verificadora de GOV-002 en la matriz RACI,
es un control de calidad obligatorio antes del merge. Su aprobación verifica la
conformidad con el SDD, el manual operativo y el RACI; no acepta la ADR ni sustituye la
decisión del coordinador. Recíprocamente, la aceptación del coordinador no reemplaza la
revisión independiente requerida para fusionar el cambio.

Mientras no exista decisión explícita del coordinador, ADR-004 permanece `PROPOSED`. Aun
aceptada, no puede fusionarse ni hacerse operativa sin la revisión independiente
requerida.

## Contexto

`00_GOVERNANCE/DECISION_REGISTER.md` pertenece al paquete FROZEN y está cubierto por
`docs/governance/MANIFEST.sha256`. Registra once decisiones `APPROVED` (D-001 a D-011) y
siete decisiones abiertas (O-001 a O-007) que el equipo debía cerrar.

Entre el 2026-08-16 y el 2026-08-19 el coordinador cerró tres de esas decisiones abiertas
—O-001, O-002 y O-007— mediante comentarios en los issues #4 y #14, y emitió una nueva
autorización de alcance en el issue #21. Ninguna de esas resoluciones quedó registrada en
un documento del repositorio.

El conflicto es el mismo que ADR-003 resolvió para los ledgers, aplicado ahora a las
decisiones. Escribir el cierre de O-001 en `DECISION_REGISTER.md` cambiaría su hash
`eba45eee591ac49472b836a4f6db12b971a889061109c62d83965515df48fab2`, con tres consecuencias:

1. `MANIFEST.sha256` pasaría a validar 29/30 en cualquier clon.
2. Se rompería la cadena de custodia con el origen gobernante y con `06_AUDIT/G0_CLOSURE_20260816.md`.
3. Contravendría la prohibición de modificar documentos FROZEN.

La alternativa que se venía aplicando de hecho —dejar la decisión únicamente en un
comentario de issue— tampoco es sostenible: un comentario no está versionado, no se revisa
en PR, no aparece en un clon del repositorio y no es localizable por quien audite el
proyecto sin acceso a la API de GitHub.

## Decisión

Se instancia un **registro vivo de decisiones y autorizaciones** fuera del paquete
congelado, en:

```
docs/decisions/LIVE_DECISION_REGISTER.md
```

### 1. El paquete FROZEN permanece inmutable

`docs/governance/` no se modifica. `DECISION_REGISTER.md` conserva su hash y sigue siendo
la fuente normativa de qué decisiones existen, cuáles están aprobadas y cuáles quedaron
abiertas. El registro vivo **no reemplaza ni reescribe** el registro congelado: lo
continúa, referenciando los identificadores que aquel definió (`D-nnn`, `O-nnn`).

`MANIFEST.sha256` no se recalcula. Debe seguir validando 30/30 en un clon nuevo.

### 2. Contenido mínimo de una entrada

Toda entrada del registro vivo declara los cinco campos siguientes. Una entrada
incompleta no es una decisión registrada: es una nota.

| Campo | Qué debe contener |
|---|---|
| Autoridad | Persona que decide, con su rol. Para decisiones de fase, el coordinador. |
| Evidencia | Localizador verificable y estable: issue y fecha del comentario, PR, commit SHA o ruta versionada. «Se acordó en la reunión» no es evidencia. |
| Fecha | Fecha de la decisión, no de su registro. Con offset `-04:00` o marca UTC explícita. |
| Alcance | Qué habilita y qué no. Gates afectados, artefactos afectados, límites expresos. |
| Estado | Uno de los estados del §7 del SDD: `PROPOSED`, `APPROVED`, `IMPLEMENTED`, `EXECUTED`, `PASSED`, `BLOCKED`. |

Una decisión sin evidencia localizable se registra como `BLOCKED`, nunca como `APPROVED`.
Aplica la política `ABSTAIN` de `docs/governance/README.md`: sin evidencia no se afirma.

### 3. Vocabulario de estado para los registros vivos

Los registros vivos derivados de plantillas FROZEN (ledgers de evidencia, contribución,
claims y experimentos) usan un vocabulario cerrado, para que un valor no signifique cosas
distintas en dos filas:

- Estados de artefacto: los seis del §7 del SDD.
- Estados epistémicos: los del §4 de `DOCUMENT_AUTHORITY.md` (`OBSERVED`, `EXECUTED`,
  `INFERRED`, `UNKNOWN`, `NOT_RUN`, `BLOCKED`). `NOT RUN` se escribe `NOT_RUN` en CSV.
- `NOT_APPLICABLE` cuando la columna no aplica a esa clase de contribución —por ejemplo,
  un acuse de recibo no tiene comando de ejecución.

Ningún estado inferior puede presentarse como `PASSED`.

### 4. Una contradicción con el nivel superior activa Stop-the-Line

Si una entrada del registro vivo contradice una fuente de nivel superior en la precedencia
del §1 de `DOCUMENT_AUTHORITY.md` —ley y derechos de uso, guía y rúbrica de MCI-509,
aclaraciones del docente, contrato SDD congelado, manual operativo, contratos de módulo—
la entrada **no gobierna**. Se aplica Stop-the-Line: se detiene el avance del gate
afectado, se registra la contradicción con ambos localizadores y la resolución corresponde
al coordinador mediante una ADR con análisis de impacto.

El registro vivo ocupa el nivel 7 de esa precedencia («issues, briefs y decisiones
aprobadas»). No puede convertir una sugerencia en requisito, ni relajar un `MUST NOT` del
contrato, ni habilitar un gate que el contrato bloquea.

## Alternativas descartadas

| Alternativa | Motivo del descarte |
|---|---|
| Escribir los cierres en `00_GOVERNANCE/DECISION_REGISTER.md` | Rompe `MANIFEST.sha256` y la cadena de custodia con G0 |
| Emitir una versión `v1.1.0` del paquete gobernante | Obliga a reejecutar los gates dependientes por un cambio que no altera alcance ni interfaces |
| Dejar las decisiones solo en comentarios de issue | No versionado, no revisable en PR, no presente en un clon, no auditable sin la API |
| Un registro vivo por gate | Fragmenta la trazabilidad; obliga a buscar en varios archivos qué gobierna una decisión |

## Consecuencias

- `MANIFEST.sha256` sigue validando 30/30. El paquete FROZEN no se toca.
- Quien audite encuentra en un único archivo versionado qué se decidió después del
  congelamiento, con qué autoridad y contra qué evidencia.
- Cada decisión futura que cierre una `O-nnn` abierta debe escribirse en el registro vivo
  en el mismo PR que la aplica. Un cierre no registrado no habilita el gate.
- El coste es un archivo más que mantener. Es menor que el coste de reconstruir la
  autoridad de una decisión a partir de hilos de issues.
- Mientras esta ADR permanezca `PROPOSED`, el registro vivo existe como propuesta
  documental y no sustituye ninguna autoridad vigente.

## Riesgo conocido, no resuelto — identidad personal en metadatos de Git

Esta sección registra un riesgo **abierto**. No describe un problema corregido y no debe
leerse como tal.

### El escaneo de contenido y el historial de Git son superficies distintas

ADR-002 declara, en su apartado de verificación, cero coincidencias de correos personales
«en contenido e historial», y lo respalda con `git grep` sobre un clon nuevo. Esa
comprobación es válida para lo que mide: el **contenido** de los archivos versionados.

No es la misma superficie que los **metadatos de commit** —campos `author` y `committer`—,
que `git grep` no inspecciona porque no forman parte del árbol de archivos. Un repositorio
puede pasar limpio un escaneo de contenido y seguir exponiendo direcciones personales en
`git log`. La propia ADR-002 lo reconoce al describir el commit raíz, pero la conclusión se
generalizó a todo el historial, y el historial siguió creciendo después.

Regla derivada: una afirmación sobre datos personales debe declarar **qué superficie**
verificó. «El repositorio está limpio» no es una afirmación verificable; «el contenido
versionado está limpio según `git grep` en un clon nuevo» sí lo es.

### Lo observado

Durante GOV-002 se observaron direcciones de correo personales en los metadatos de autor de
varios commits de merge **posteriores** a la reescritura descrita en ADR-002. El
repositorio es público, de modo que esos metadatos son legibles por cualquiera.

Estado epistémico: `OBSERVED`. No cuantificado exhaustivamente y no remediado.

### Manejo de las direcciones

Las direcciones observadas **no se transcriben** en este documento, ni en el registro vivo,
ni en los ledgers, ni en ningún informe de ejecución. Anotarlas aquí las trasladaría del
historial —donde ya están— al contenido versionado, que es precisamente la superficie que
ADR-002 mantiene limpia, y multiplicaría su exposición en vez de reducirla.

Quien necesite auditarlas las consulta directamente con `git log`, sin copiarlas a un
archivo, a un issue, a un PR ni a un mensaje.

### Mitigación hacia adelante

Los commits futuros deben crearse con una identidad **GitHub noreply**
(`<usuario>@users.noreply.github.com`), configurada **únicamente en este repositorio**
—`git config --local`, nunca `--global`—, para no alterar la configuración personal de
ningún integrante en otros proyectos.

Esta ADR **no aplica ese cambio**: GOV-002 tiene prohibido modificar configuración de Git.
La configuración corresponde a un paso posterior, dirigido por la coordinación técnica
antes del primer commit de esta rama.

La mitigación es prospectiva: no limpia los commits ya publicados.

### Reescritura de historia: prohibida sin decisión expresa

Queda **prohibido** reescribir el historial para eliminar estos metadatos —`filter-branch`,
`filter-repo`, rebase de limpieza, force-push o recreación del remoto— sin una decisión
expresa y documentada del coordinador.

Los motivos:

- Reescribir invalida todos los SHA publicados, y con ellos las referencias de
  `EVIDENCE_LEDGER.csv`, de `CONTRIBUTION_LEDGER.csv` y de las ADR. La trazabilidad que
  sostiene la evaluación colaborativa se rompería entera.
- ADR-002 ya documenta que un force-push no elimina el objeto de los servidores de GitHub:
  la única vía efectiva fue recrear el remoto. Repetir esa operación con PR abiertos
  (#11, #16, #17, #20) destruiría trabajo de otros integrantes.
- El beneficio es bajo: las direcciones ya están publicadas y posiblemente replicadas en
  clones y forks. La eliminación no es retroactiva en la práctica.

Si el coordinador decide abordarlo, exige ADR propia con análisis de impacto, aviso a los
cuatro integrantes y plan de reconciliación de los SHA citados en los ledgers.
