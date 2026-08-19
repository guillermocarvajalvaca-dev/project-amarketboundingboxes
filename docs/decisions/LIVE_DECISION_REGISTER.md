# Registro vivo de decisiones y autorizaciones

Instancia viva prevista por `ADR-004_LIVE_DECISION_AND_AUTHORIZATION_REGISTER.md`, ubicada
fuera del paquete FROZEN según el principio fijado en
`ADR-003_LIVE_LEDGERS_OUTSIDE_FROZEN_PACKAGE.md`.

- `docs/governance/00_GOVERNANCE/DECISION_REGISTER.md` sigue siendo la fuente normativa de
  qué decisiones existen. Este archivo registra **cómo se cerraron** las que quedaron
  abiertas, y las autorizaciones emitidas después del congelamiento.
- El paquete FROZEN no se modifica. `MANIFEST.sha256` valida 30/30.
- Toda entrada declara autoridad, evidencia, fecha, alcance y estado. Sin los cinco campos
  no es una decisión registrada.
- Una contradicción con una fuente de nivel superior de `DOCUMENT_AUTHORITY.md` §1 activa
  Stop-the-Line y no gobierna.

Las marcas de tiempo se toman de la API de GitHub en UTC. La zona del proyecto es
`-04:00`; donde la diferencia cambia la fecha civil se anotan ambas.

## Índice

| ID | Decisión o autorización | Cierra | Autoridad | Fecha | Estado |
|---|---|---|---|---|---|
| LD-001 | Conformación del dataset: todos los productos únicos aceptados | `O-001` | Coordinador | 2026-08-16 | `APPROVED` |
| LD-002 | Seed 42 y splits 70/15/15 | `O-002` | Coordinador | 2026-08-16 | `APPROVED` |
| LD-003 | Redistribución prohibida; imágenes solo en Drive privado | `O-007` | Coordinador | 2026-08-16 | `APPROVED` |
| LD-004 | Visibilidad pública del repositorio y su relación con los derechos | — | Coordinador vía ADR-002 | 2026-08-16 | `APPROVED` |
| LD-005 | Autorización de regularización documental y cierre controlado de G2/G3 | — | Coordinador | 2026-08-18 | `APPROVED` |
| LD-006 | G4 y fases posteriores permanecen bloqueadas | — | Coordinador | 2026-08-18 | `BLOCKED` |
| LD-007 | El issue #7 (INT-001) debe permanecer abierto hasta la integración final | — | Coordinador | 2026-08-18 | `BLOCKED` |

---

## LD-001 — Conformación del dataset aceptado

Cierra `O-001` («Tamaño final del dataset aceptado»).

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: issue #4, comentario del coordinador «Decision del coordinador - O-001 y
  O-007», `2026-08-16T23:03:44Z`.
- **Fecha**: 2026-08-16.
- **Alcance**: G2 (adquisición y procedencia). Habilita el crawl completo en cuanto a
  tamaño objetivo. No crea Quality Gates adicionales ni altera el contrato de scraping.
- **Estado**: `APPROVED`.

Contenido decidido:

- Procesar todos los productos encontrados en el snapshot autorizado de Amarket.
- Máximo una imagen por producto.
- El dataset final lo forman **todos los activos únicos** que resulten `ACCEPTED` tras
  aplicar los Quality Gates FROZEN.
- No se fija anticipadamente un número final sin evidencia.
- Al terminar el crawl se registran los conteos reales de aceptados, rechazados y
  duplicados, junto con el SHA-256 del manifest congelado.

Consecuencia sobre `O-001`: queda cerrada como criterio. El conteo real sigue siendo
`UNKNOWN` hasta que exista el manifest del crawl.

## LD-002 — Semilla y proporciones de split

Cierra `O-002` («Proporción `train/val/test` y seed fija»).

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: issue #14, comentario del coordinador «Decision del coordinador - O-002»,
  `2026-08-16T23:03:45Z`.
- **Fecha**: 2026-08-16.
- **Alcance**: G3 (bounding boxes y dataset), artefacto SPL-001. No modifica los Quality
  Gates FROZEN ni el `DATA_AND_SPLIT_CONTRACT.yaml`.
- **Estado**: `APPROVED`.

Contenido decidido:

- `fixed_seed = 42`
- `train = 0.70`, `validation = 0.15`, `test = 0.15`
- La asignación respeta la exclusividad por `sku_id`, `source_asset_id` y
  `duplicate_group_id` establecida en `02_CONTRACTS/DATA_AND_SPLIT_CONTRACT.yaml`.
- El test queda bloqueado tras su creación.
- Los mismos inputs, configuración y seed deben producir el mismo `splits.csv`.

Coherencia con el nivel superior: el §6 del SDD exige que la clase única exista en los
tres splits y prohíbe crear independencia artificial. Si el número de grupos SKU no
alcanza para tres splits con estas proporciones, gobierna el §6 y G3 se detiene; esta
decisión no autoriza duplicar ni aumentar para completar los ratios.

## LD-003 — Derechos, almacenamiento y redistribución

Cierra `O-007` («Estado de derechos para distribuir las imágenes»).

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: issue #4, comentario del coordinador «Decision del coordinador - O-001 y
  O-007», `2026-08-16T23:03:44Z`.
- **Fecha**: 2026-08-16.
- **Alcance**: G2 y G6 (publicación). Determina dónde viven las imágenes; no autoriza
  ninguna publicación.
- **Estado**: `APPROVED`.

Contenido decidido:

- `rights_status = REDISTRIBUTION_PROHIBITED`.
- Las imágenes se almacenan **exclusivamente en el Google Drive privado del proyecto**.
- Acceso limitado al equipo y al docente, para evaluación académica.
- Prohibido publicar el dataset completo en GitHub.
- GitHub conserva solamente código, configuraciones, manifests permitidos y evidencia sin
  material restringido.

Coherencia con el nivel superior: refuerza la resolución del §3 de `DOCUMENT_AUTHORITY.md`
—`robots.txt` permite leer el catálogo público pero no constituye licencia de
redistribución— y el `MUST` del §3 del SDD de mantener datasets grandes fuera de GitHub.

## LD-004 — Visibilidad pública del repositorio

No cierra ninguna `O-nnn`. Registra la decisión ya adoptada en ADR-002 y su relación con
las decisiones de derechos y de entrega.

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: `docs/decisions/ADR-002_REPO_VISIBILITY_AND_PROTECTION.md`, estado
  `Accepted`, gate G1. Prueba en vivo de la protección resultante: fila `EV-G1-001` de
  `docs/evidence/EVIDENCE_LEDGER.csv` y `docs/evidence/2026-08-16_main_protection_test.md`.
- **Fecha**: 2026-08-16.
- **Alcance**: visibilidad del repositorio y protección de `main` durante G1 y siguientes.
- **Estado**: `APPROVED`.

Relación que este registro fija expresamente:

1. El repositorio es público **como único medio gratuito de habilitar la protección de
   `main`** con `enforce_admins = true`, tras el rechazo del pago de GitHub Pro. La
   visibilidad es un efecto del control de revisión cruzada, no un objetivo del proyecto.
2. **La visibilidad pública no habilita redistribución.** LD-003 mantiene
   `rights_status = REDISTRIBUTION_PROHIBITED`: que el repositorio sea legible por
   cualquiera no autoriza publicar en él las imágenes del catálogo. Ambas decisiones son
   compatibles porque recaen sobre objetos distintos —el repositorio de código y el
   dataset— y quien las lea junto debe aplicar la más restrictiva a las imágenes.
3. `O-005` («Visibilidad final del repo y acceso del docente») **permanece abierta** en
   `DECISION_REGISTER.md`. ADR-002 exige revisitar la visibilidad una vez calificado el
   proyecto. LD-004 no la cierra.
4. Lo publicado incluye el plan de scraping, los contratos de datos y los briefs
   individuales con nombres propios y asignaciones, sin datos de contacto. Es una
   consecuencia aceptada y registrada en ADR-002, no un descuido.

## LD-005 — Autorización de regularización documental y cierre controlado de G2/G3

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: issue #21, «[GOV-002] Reconcile live decisions, ledgers and gate
  authorization», creado `2026-08-19T01:23:37Z` (`2026-08-18T21:23:37-04:00`), autor
  `guillermocarvajalvaca-dev`.
- **Fecha**: 2026-08-18 (hora local del proyecto).
- **Alcance**: autoriza **únicamente** la regularización documental descrita en el issue
  #21 y el cierre controlado del G2/G3 ya iniciado. Sin retroactividad: no convalida
  trabajo no ejecutado ni cierra gates cuyas condiciones carezcan de evidencia.
- **Estado**: `APPROVED`.

Lo que la autorización habilita:

- Crear, fuera del paquete FROZEN, esta ADR y este registro vivo de decisiones.
- Crear el ledger vivo de contribución en `docs/evidence/CONTRIBUTION_LEDGER.csv`.
- Corregir CODEOWNERS para asegurar revisión independiente del informe y del notebook de
  análisis de errores, alineado con la matriz RACI.
- Documentar la restricción de dispositivo previa a G4.

Lo que la autorización **no** habilita, por declaración expresa del propio issue:

- Modificar documentos FROZEN.
- Implementar o modificar scraper, bounding boxes, splits, entrenamiento o evaluación.
- Ejecutar scraping, descargar imágenes o entrenar modelos.
- Fusionar PR técnicos como parte de este issue.
- Crear evidencia ficticia o retroactiva.

## LD-006 — G4 y fases posteriores permanecen bloqueadas

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: issue #21, sección «Autoridad y autorización», `2026-08-19T01:23:37Z`.
  Concordante con el §11 del SDD FROZEN y con ADR-001, que exigen decisión expresa del
  coordinador para cada transición de fase.
- **Fecha**: 2026-08-18 (hora local del proyecto).
- **Alcance**: G4 (baseline y entrenamiento final), G5 (evaluación e inferencia CPU) y G6
  (informe, README y defensa).
- **Estado**: `BLOCKED`.

`O-003` (baseline preentrenado y versión exacta) y `O-004` (inventario de hardware y
presupuesto de épocas) siguen abiertas en `DECISION_REGISTER.md` y bloquean G4 por sí
mismas, con independencia de esta entrada. `O-006` (política institucional de uso y
atribución de IA) sigue abierta y bloquea el merge final y G6.

La existencia de `src/train.py` y `src/evaluate.py` en `main` —fusionados por el PR #12
contra un dataset de fixture— **no abre G4**. El §7 del SDD es explícito: solo `PASSED`
permite continuar a una fase dependiente, y un archivo existente no prueba ejecución.

## LD-007 — El issue #7 (INT-001) debe permanecer abierto

- **Autoridad**: Jose Guillermo Carvajal Vaca, coordinador y líder.
- **Evidencia**: issue #21, alcance obligatorio, `2026-08-19T01:23:37Z`. Estado observado
  del issue #7: `CLOSED`, `closedAt = 2026-08-16T19:23:52Z`.
- **Fecha**: 2026-08-18 (hora local del proyecto).
- **Alcance**: INT-001 (integración y reproducibilidad); artefactos REP-001, REP-002 e
  INF-001.
- **Estado**: `BLOCKED` — desalineación observada, pendiente de acción del coordinador.

INT-001 declara como criterios de aceptación el README reproducible,
`src/common/reproducibility.py` con tests, la interfaz acordada de `predict.py` y los
handoffs documentados. Ninguno de esos artefactos existe todavía en `main`:
`src/common/` y `src/predict.py` no están implementados, y el README sigue declarando
`G1_BOOTSTRAP`. El issue se cerró el 2026-08-16 sin que esas condiciones tuvieran
evidencia.

Acción pendiente, que corresponde al coordinador y **no** se ejecuta en GOV-002: reabrir
el issue #7 y mantenerlo abierto hasta la integración final. La ejecución GOV-002 tiene
prohibido modificar issues.
