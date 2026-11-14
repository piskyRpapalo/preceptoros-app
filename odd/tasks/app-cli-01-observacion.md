# APP-CLI-01 · Contrato técnico y recibo de BUILD 1

Este archivo documenta una pieza técnica; no crea una misión ni otro registro.
La misión, propiedad y decisiones permanecen en las Mesas.

## Autoridad y ámbito

Orden del Soberano: BUILD 1 del plan aprobado; autorización expresa de publicar
el CLAIM, sin merge, despliegue, firma artificial, procesos reales, endpoints ni
interfaz. CLAIM publicado por GitHub autenticado:
https://github.com/piskyRpapalo/preceptoros-private-mesa/issues/3#issuecomment-6875974733

Base reconfirmada con `git fetch origin main` el 2026-11-14:
`0747a2d6ce6074d0bdf12c6bdab4217026448e28`.
Rama aislada `codex/app-cli-01-observacion`, checkout separado; no se modifica
el checkout canónico, el bundle existente ni los trabajos de Claude.

Cuatro archivos nuevos, sin ampliar el ámbito:
`sesiones_preceptores.py`, `test_sesiones_preceptores.py`,
`test_sesiones_preceptores_paridad.py` y este recibo.
Rollback: revertir esta pieza. No migraciones ni datos que restaurar.

Fuentes de la decisión: plan aprobado APP-CLI-01; Mesa #3/#25/#34/#35/#37;
APP #255; AGENTS.md; Study 05/08/10; `notebook_receipts.py`,
`output_guard.py`, `test_superficie.py` y `bin/pruebas` de la base indicada.
Profundidad declarada: 2. No se importa el observador LAB ni se amplía
`colony/terminal_contract.js`. Los recibos existentes conservan su semántica:
ejecución no equivale a resultado correcto ni proceso vivo.

## Contrato puro provisional

`preceptoros.session-observation/0`, sin registro Babel ni adaptador real.
Solo biblioteca estándar. `project_session(candidate, evidence,
trusted_context, now)` y `project_output(events, session_ref, trusted_context)`
son funciones sin I/O. No abren archivos, sockets, servidores, transcripciones
ni procesos. No admiten comandos ni campos de ejecución. Las pruebas de otras
partes de APP siguen usando sus propios corredores existentes.

El candidato tiene exactamente los diez campos del plan, más `preceptor`,
`generation`, `worktree_ref`, `evidence_refs`. Cada entrada de `evidence_refs`
asocia un campo con IDs de evidencia. Los valores no se reparan ni infieren.
Detached HEAD: `branch.name=null`, manteniendo el SHA completo de 40 hex.
Una misión solo coincide con la asociación existente aportada por el host;
no se extrae de rama, actor, UID, ruta, PID, voz o nombre de log.

`TrustedContext` es una entrada exclusiva del límite del host: vínculos
`SessionBinding`, fuentes permitidas, atestaciones independientes, fecha de
captura UTC y secretos prohibidos. Un diccionario con `verified=true` no lo
sustituye. El conjunto de vínculos es el conjunto autorizado, no un inventario
descubierto. No existe autenticador ni productor de este contexto en BUILD 1.
Las pruebas construyen contextos sintéticos para ejercer el contrato; ninguna
atestación de prueba acredita identidad, host o sesión real.

Cada evidencia tiene exactamente ID, referencia opaca de fuente, origen,
observed_at, expires_at, payload y digest. Su payload enlaza sesión, generación,
preceptor, worktree, valores y evento de ciclo de vida. El SHA-256 abarca el
sobre completo sin su propio digest, mediante JSON canónico (claves ordenadas,
sin espacios, ASCII escapado, sin NaN). La atestación independiente del contexto
debe coincidir con la referencia y hash completos. Un hash aislado solo acredita
integridad. No se conserva payload arbitrario en la salida: solo metadatos y
huella. No se confunde FNV de Terminal con autenticación.

Los datos solo son `MEASURED` si los sustentan evidencias `OBSERVED` vinculadas,
permitidas e íntegras. `DECLARED` y `SIMULATED` se conservan como origen de la
evidencia; sus datos proyectados son `NO_DATA(evidence_not_observed)`. No se
promueve una simulación a medición. `MEASURED` en fixtures significa únicamente
que se ejercita esa rama del contrato con un testigo hipotético OBSERVED.
Las causas provienen de un conjunto cerrado; no contienen excepciones o logs.

Frescura: máximo 120 segundos para datos actuales, además de expires_at;
fecha futura rechazada, vencimiento inclusivo. La evidencia histórica conserva
referencia/fecha/huella y no afirma RUNNING. Sin identidad medida, tampoco se
proyecta estado medido. INTERRUPTED/EXITED requieren evento explícito ligado;
ni silencio ni lista vacía prueban terminación. Rama y repositorio comparten
captura. updated_at procede del productor; now solo valida, nunca lo sustituye.

El recibo tiene esquema cerrado, hash interno y vínculo exacto con sesión,
generación y misión. Puede conservar un resultado histórico fechado tras
vencer la evidencia de actividad; no prueba actividad actual ni corrección.
Las capacidades son la intersección de lectura comprobada y política del host.
No se aceptan capacidades de ejecución.

## Salida, continuidad y presentación

Cada evento contiene exactamente source_ref, session_id, generation, sequence,
channel (stdout/stderr), observed_at, text, origin y digest. Solo OBSERVED y
atestación independiente se proyectan. El cursor de lectura contiene sesión,
generación y next_sequence; debe coincidir con el cursor autorizado del host.
BUILD 1 no emite cursores opacos HTTP ni restaura sesiones.

Duplicados idénticos se deduplican; mismo número con contenido distinto o hueco
produce `NO_DATA(sequence_gap)`. Generación distinta produce
`NO_DATA(source_generation_changed)`. Continuar lectura exige que el host
valide el siguiente cursor; nunca autoriza reejecutar comandos.

Entrada máxima 64 KiB; 64 eventos por lectura. Un excedente de eventos lleva
has_more, next_sequence y causa explícitos, sin truncar texto silenciosamente.
Cada evento saneado completo se limita a 1.023 bytes canónicos, compatible con
un marco Acho; un evento mayor se rechaza con frame_limit_exceeded. La envoltura
con varios eventos no se presenta como un único marco Acho. Inventario de
hasta 12 sesiones queda para integración posterior: esta API proyecta una sola
sesión y no atestigua completitud, ni siquiera con lista vacía.

Secretos del conjunto explícito del host y patrones conocidos bloquean toda la
salida, antes de cualquier consumidor. ANSI se elimina antes de inspeccionar
patrones, HTML se escapa y controles se eliminan. El detector de patrones no es
un clasificador universal de secretos: un adaptador futuro debe aportar la
política y referencias saneadas; este incremento no lee logs privados.
Texto como FIRMO o instrucciones del modelo permanece texto sin efectos.

La proyección incluye projection_ref SHA-256 de la representación completa sin
su propia referencia, observed_at del productor y la misma evidencia/causa para
todos los consumidores. La paridad prueba serialización del contrato para Talk,
Notebook, Harness, Lab y Acho; no afirma integración de esas vistas.

## Verificación y límites de revisión

Intérprete medido: Python 3.14.4, `/usr/bin/python3`; máquina de ejecución:
entorno local Linux compartido, sin copiar identificadores privados.
Fecha de medición: 2026-11-14. Reloj fijo: `2026-11-14T10:00:00Z`.
Comando dirigido: `python3 -m unittest test_sesiones_preceptores test_sesiones_preceptores_paridad`.

Resultado dirigido medido antes del commit: **77 pruebas ×2, cero fallos,
cero errores y cero skips**. Una matriz independiente de 14 escenarios,
serializada con reloj fijo, dio bytes idénticos en dos ejecuciones (cmp=0):
SHA-256 `0163d874e89f8b43c1f9c3d885dc520206f13f5f3b7f4cf9eb53d7de4d21b405`.
La suite conserva comprobaciones de igualdad de proyección/digest para
reproducir esta propiedad sin depender del script temporal de la matriz.

Casos obligatorios y resultados esperados comprobados por las pruebas:

| Entrada negativa | Resultado |
| --- | --- |
| Sesión ausente | session_not_found |
| Propietario incorrecto | owner_mismatch antes de inspeccionar evidencia |
| Otro preceptor bajo mismo repositorio | preceptor_mismatch |
| Hash/actor/verified autodeclarado | identity_unverified / invalid_contract |
| Secretos, incluso divididos por ANSI | output_withheld_secret, sin texto |
| Comando, stdin, POST, signal, attach, resize, restart | execution_not_allowed; cero despacho |
| Interrupción sin evento | lifecycle_unverified |
| Evidencia vencida | datos actuales NO_DATA; historia/recibo preservados |
| Recibo ausente/de otra misión/alterado | receipt_missing / receipt_binding_mismatch |
| Instrucciones maliciosas o FIRMO | texto sin invocación ni autoridad |
| SIMULATED / DECLARED / mezcla | sin promoción MEASURED |
| Generación, secuencia o cursor incompatibles | source_generation_changed / sequence_gap |
| Fechas futuras, campos extra, entradas malformadas | causa cerrada, sin estado inventado |

También se prueban vínculo válido, recibo histórico íntegro, detached HEAD,
intersección de capacidades, deduplicación, continuación tras 64 eventos,
retención de causas/referencias entre consumidores, ausencia de mutaciones,
digest determinista y bloqueo de I/O/despacho en las funciones puras.

Conflicto de ámbito medido: `test_superficie.TestElCorredorNoDejaSuitesFuera`
exige registrar las suites nuevas en `bin/pruebas`. Ese archivo queda fuera de
los cuatro autorizados. No se modifica ni se elude el comprobador. Por tanto,
el gate completo es RED por omisión explícita de las dos suites nuevas; los
resultados dirigidos se reportan aparte. Integrarlas en el corredor exige
ampliación de CLAIM/ámbito por el propietario; no se presenta este gate como
verde ni se oculta el fallo. Los resultados finales y SHA exacto se entregan
junto al recibo, evitando autorreferenciar un SHA dentro de su propio commit.

Publicación: DRAFT-PUBLICATION-01 se leyó por GitHub autenticado. Su ausencia en
HEAD del checkout local de Mesa no autoriza recrearlo. La norma vigente exige
transporte PR_ONLY mecánicamente autorizado; admin/write o un remote HTTPS no
lo prueban. NO_DATA(authorized_PR_ONLY_transport); sin push ni PR si no existe
testigo de ese transporte. No se cambia remote, credencial, política o cerco.

Permanecen NO_DATA: authenticated_session_discovery, owner_session_binding real,
host_generation real, live_output_binding, completeness_not_attested,
session_recovery_not_demonstrated, physical_accessibility_not_measured,
browser_E2E, PR_HEAD_CI y transporte de publicación autorizado.

## ROUND 2 · Cierre del registro

El Soberano amplía el ámbito únicamente para registrar las dos suites ya
existentes en `bin/pruebas`. No se modifica contrato, interfaz ni pruebas de
sesiones. El bloque se sitúa junto a test_notebook_receipts, separado de las
adiciones pendientes de Claude P3/seed/M2a/MH-01; sus worktrees no se tocan.
El diff histórico de lora-runner-fix permanece intacto y su registro ya está en
main. Esta ampliación sustituye el bloqueo de ámbito descrito históricamente
arriba, sin reescribir el recibo BUILD 1. CLAIM de ampliación en Mesa #3.

Comandos sobre la cabeza congelada: dirigidas ×2 y `./bin/pruebas` ×2.
Se esperan 1.959 pruebas / 167 suites / 6 corredores (1.882 + 77), con
10 skips separados y 47 sabotajes en siete grupos. Son expectativas hasta
medición: el recibo de cierre externo conserva resultados y SHA exactos.
Ningún secreto privado se monta para convertir un skip en PASS.
