# System Check · contrato técnico del primer incremento

Este documento es contrato/recibo de la pieza B autorizada, no una misión nueva.
La coordinación permanece en Mesa #3 / Community Toolbox, fuentes #6876325544 y
#6876400453; CLAIM BUILD #6876560433. El Soberano conserva integración/firma.

## Propósito y límites

Un informe útil en el ordenador propio, sin cuenta, modelo, Internet ni rack.
El núcleo `system_check.diagnose(observations, now)` es puro. El adaptador
`system_check_local.run_check()` observa únicamente la máquina local y expone
una función consumible por el propietario de Harness; la CLI nativa funciona con
`python3 -B -m system_check_local`. No se modifica Harness visual ni su endpoint.
El botón «Check my computer» queda para integración de Claude, no se afirma
haberlo instalado en la interfaz. En modo fuente se necesita el Python que
está ejecutando APP; no un segundo Python en PATH. El empaquetado puede llamar
la misma función desde su runtime. Un instalador/binario sin Python todavía
requiere validación de distribución independiente.

No procesos externos, sockets, barrido de red, instalación, descarga, permisos
privilegiados, conexión de servicios, credenciales, autenticación o telemetría.
No se lee registro del rack ni se confunde membresía con permiso. Un diagnóstico
no concede autoridad ni reserva recursos; `authority=NOT_AUTHORIZED` siempre.

Base independiente APP origin/main `0747a2d6ce6074d0bdf12c6bdab4217026448e28`,
rama `codex/system-check-20261114`. No se apila APP-CLI-01. Ningún worktree de
Claude se modifica. Ámbito: núcleo, adaptador, suite dirigida, propuesta de
pruebas adversariales aislada integrada tras revisión, este contrato y un
registro de las suites en `bin/pruebas`, en bloque distinto de A/Claude.

## Reutilización y decisiones medidas

- `consola.modelos_pc`: contrato y pruebas de manifiesto/blob presente; no
  inferencia disponible. `console_models` adapta esa forma sin copiar rutas,
  errores libres ni configuración. Se cruza con el lector real y almacenes
  sintéticos. La raíz configurada proviene de `consola.raiz_ollama`, sin ruta
  de navegador/modelo ni nuevo catálogo de dispositivos.
- La auditoría SWARM-01 detectó que el lector original recorre con rglob antes
  del límite, acepta metadatos permisivos y sigue enlaces de blob. No se cambia
  `consola.py`: el adaptador nativo usa lectura acotada por descriptor. Conserva
  el esquema de catálogo y la adaptación pura; su fuente se distingue como
  `system_check_local.model_store`, no se atribuye esa captura a otra función.
- `estado_app.py`: reutiliza esquema, validación, semántica compartida y techo
  1.024 B para una envoltura Harness enlazada por projection_ref. Sin Proof of
  Tick, la superficie conserva tick=null y NO_DATA de frescura semántica. Una
  fecha UTC no se promueve a tick. No nueva paleta ni interfaz.
- `guardrails.PATRONES_CORE`: solo patrones inmutables, para bloquear IDs con
  forma de credencial y comprobar reglas nativas. No llama a redactar_salida
  ni ruta_politicas: esas funciones pueden sembrar policies.json. El diagnóstico
  no crea configuración ni abre memoria de usuario.
- INSTALL_PC.md / pyproject: Python >=3.10, biblioteca estándar; sqlite3 se
  comprueba por importación fija. Importar sqlite no prueba escritura de disco.
- LAB resource_admission / host_witness: observación y disponibilidad jamás
  sustituyen testigo de identidad, consentimiento, lease o permiso. No se
  importan callbacks LAB ni se crea otro ejecutor/MCP.

## Datos, procedencia y frescura

Contrato provisional `preceptoros.system-check/0`, sin registro Babel.
`Observation(value, source, observed_at, origin, cause)` la aporta el adaptador
local de confianza. Un diccionario verified=true no se acepta como observación.
Esto no es una autenticación criptográfica para un futuro navegador remoto.
Cada dato conserva fuente permitida y UTC; cuatro estados distintos:
MEASURED / DECLARED / SIMULATED / NO_DATA. Solo MEASURED fresco contribuye a
capacidades o conexión. Una causa procede de códigos acotados, sin excepción,
mensaje de servicio, hostname, IP, serial, token ni ruta personal.

Se proyectan SO, arquitectura, versión del runtime actual, presencia de un
Python auxiliar en PATH (no ejecutado ni requisito extra), importación sqlite,
CPU lógicas del sistema, MemAvailable Linux y disco libre del volumen de APP.
CPU del sistema no equivale a cuota cgroup; memoria no es presupuesto concedido
para tareas. GPU, recursos por proceso y plataformas sin medida segura quedan
NO_DATA. No se recomienda un tamaño de modelo desde RAM parcial.

Frescura máxima 120 segundos; el límite exacto 120 es vigente, >120 caduca.
Fechas futuras o tipos inválidos se rechazan. run_check valida contra reloj de
finalización, para que una captura lenta no conserve frescura falsa. Un dato
caducado conserva fuente/fecha y STALE, sin valor actual inventado.

Estados del informe:

- LOCAL: diagnóstico ejecutable con el runtime local compatible; no implica
  que Internet esté caído ni que todos los recursos estén disponibles.
- CONNECTED: además, un testigo fresco de servicio disponible. No equivale a
  servicio autorizado, acceso al rack, inferencia o Internet. El adaptador local
  no genera ese testigo ni sondea servicios; lo ejercitan fixtures del contrato.
- UNKNOWN: runtime insuficientemente medido o no compatible. Los datos válidos
  parciales se conservan. Contrato/entrada malformados usan NO_DATA con causa.

status_evidence conserva fuentes de derivación, fecha y frescura. Internet y los
servicios opcionales por defecto son NO_DATA(connectivity_not_measured /
service_not_probed), no OFFLINE inventado. Un servicio medido inaccesible lleva
service_unreachable; una declaración no se convierte en conexión o permiso.

Las acciones sin modelo son informativas: revisar diagnóstico/requisitos,
reglas locales de privacidad y archivos de modelos cuando estén medidos. No
contienen comandos, URLs, callbacks de instalación/conexión ni concesiones.

## Modelos: presencia acotada, nunca inferencia o procedencia de release

El almacén configurado es un alcance, no todos los motores de la máquina.
Sin almacén legible, NO_DATA; un catálogo completo vacío sí prueba cero archivos
presentes en ese alcance. Se exigen metadatos de modelo: SHA-256 sintáctico
completo, tamaño entero positivo (no bool), una capa de modelo inequívoca y blob
regular de tamaño coincidente. Un manifiesto sin blob no se muestra instalado.
Los bytes no se rehashean: la presencia no prueba integridad del contenido,
formato válido, carga, velocidad o inferencia utilizable. Servicios siguen sin
atestación. Un modelo listado no autoriza su ejecución.

Lector nativo: raíz elegida por el host; O_NOFOLLOW, O_NONBLOCK y operaciones
relativas a descriptores dentro del almacén. Se rechazan enlaces simbólicos,
FIFO y tipos no regulares. Se valida sobre el descriptor que se utiliza, sin
reabrir rutas aportadas por datos. 64 manifiestos máximo, 256 entradas recorridas,
profundidad 8; se cuenta antes de leer manifiestos. 64 KiB por manifiesto y 1 MiB
agregado. Duplicados JSON/metadatos inválidos provocan abstención. No se trunca ni
se presenta un inventario parcial como cero. Si faltan APIs seguras del sistema,
NO_DATA; no hay fallback que siga enlaces. La raíz configurada es una decisión
local del host; no se acepta desde un navegador/modelo. No se leen blobs de
configuración ni texto privado del almacén para el informe.

El informe puro limita entrada a 64 KiB y listas a 64 IDs, valida etiquetas y
filtra patrones de credenciales reutilizados. No es un detector universal de
secretos: nunca exporta nada ni incluye payloads arbitrarios. Todos los
consumidores conservan el mismo SHA-256 canónico (projection_ref); Harness
valida esa huella antes de construir su envoltura existente.

## Medición, pruebas y revisión paralela

Reloj fijo de fixtures: 2026-11-14T12:00:00Z. Python 3.14.4, entorno local Linux
compartido, fecha 2026-11-14. Dirigidas: test_system_check y la suite adversarial
independiente, dos ejecuciones tras congelar fuente. Gate APP completo ×2 sobre
la cabeza final, skips y sabotajes separados. No se añade otra plataforma de test.

La revisión independiente de seguridad detectó, con reproducción, traversal sin
límite previo, ID con forma de credencial, SHA/tamaño inválidos, blob enlazado
fuera del almacén y booleano no estricto en la métrica. El constructor integra
las correcciones solo en su ámbito y las somete de nuevo a revisión y pruebas.
La suite independiente cubre los ocho negativos encargados por SWARM-01 más
regresiones. Ningún colaborador edita el código productivo o la suite activa del
constructor. Los recibos detallados y resultados por SHA se conservan en el
paquete externo de revisión y en Mesa; no se autorreferencia SHA dentro del commit.

Casos: cero modelos, Internet ausente, Python auxiliar ausente, servicio local
caído, modelo sin blob, permisos insuficientes, evidencia caducada/futura,
hardware parcial, servicio remoto declarado sin conexión, credenciales en IDs,
límites de fuentes y metadatos inválidos. Se conservan pruebas de no sockets /
no procesos externos / no política creada / núcleo sin E/S / no promociones.

Beneficio medible: first_use_metric usa dos tiempos monotónicos del mismo proceso
para la primera operación útil (obtener informe local); completed debe ser bool.
Se prueba ejecución con HOME temporal, almacén ausente o vacío, PATH sin Python
auxiliar y red/procesos bloqueados. Esa medida NO es instalación limpia real ni
recorrido físico de Harness. NO_DATA(clean_install_to_first_use_E2E,
Harness_button_E2E, packaged_runtime_E2E, physical_accessibility).

Publicación: PR draft preparada solo por transporte autorizado. Se mantiene el
bloqueo único de Mesa #6876556295: NO_DATA(authorized_PR_ONLY_transport,
PR_HEAD_CI). Sin push alternativo, cambios de credenciales, release, merge,
despliegue o firma. Rollback: revertir esta pieza independiente, sin migración
ni datos de usuario que restaurar.

## Cierre de revisión antes de congelar

47 pruebas propias + 25 adversariales integradas = 72 pruebas dirigidas.
Reauditoría independiente ×2: hallazgos originales rechazados con NO_DATA y
límite agregado sin sobrelectura (1.048.576 bytes máximo); 65 manifiestos se
rechazan antes de leer contenido. El constructor integra únicamente el archivo
propuesto, elimina su fallback de ruta absoluta y conserva imports normales.
Agrega regresión permanente del presupuesto agregado agotado.

La captura de seguridad final identifica núcleo SHA-256
`e3a69d410fff30fc7e712cb56cef6bdfcf1e17e9ac4476a3961b259406231b9c` y adaptador
`b0985f92a28f2def7464da4d70574f83e447d1f774d3f67c48ac793000b28e81`.
Son hashes de código, no autenticación de una máquina. No se ocultó ningún RED
inicial de auditoría ni se atribuye un RED previo a pruebas escritas después.

Se ejecutarán dirigidas ×2 y gate ×2 tras congelar HEAD; el paquete externo
retiene logs, counts/skips/sabotajes y el SHA exacto. La rama B parte de main,
por lo que sus totales no incluyen las 77 pruebas de A: se esperan 1.954 pruebas
y 167 suites (expectativa, no resultado hasta ejecutar).
