# HEX-AVATAR-VOICE-WEB-B-04 · Propuesta de integración STT local (guardia, no ruta publicada)

**Fecha:** 2026-11-22 · **Responsable:** Codex GPT-6 Web / Avatar-Acho · **Autoridad:** Soberano.

## Fuentes verificadas y reutilización

- APP existente :8742, `avatar_voice.js` y Talk; no se crea otro avatar o Mini.
- `oido.py` ya encapsula `whisper.cpp` de Beelink; CLI `/home/pisky/whisper.cpp/build/bin/whisper-cli` y modelo `ggml-tiny.bin` de 77.691.713 B medidos. Fuente local CLI admite `--no-gpu` y `--threads`. No se descargan modelos.
- Usuario confirma que **«Leer último mensaje visible» suena** (Mesa #51 comentario 7085336056), pero no hay testigo de STOP/MUTE ni de entrada STT. Chrome reportó `NO_DATA(local_stt_pack_missing)`.
- CineK impone su gate legado de salud 80 °C; no es máximo global del Beelink ni de ONEX. El **75 °C** de este prototipo es un umbral provisional y conservador de **admisión de una nueva carga CPU para B-04**, no especificación de hardware; se debe revisar con OWNER y sensores independientes antes de activar. El límite histórico 92 °C carece de contrato fuente verificable.

## Qué implementa esta rama (inert)

`voz_stt_local.py` reutiliza `oido.transcribir` y rechaza de forma tipada:
- solicitudes sin origen local acreditado por la APP y comando exacto `transcribe_es_pcm16_v1`;
- `PRECEPTOROS_SIN_HARDWARE`, sensor CPU Tctl ausente, temperatura >=75 °C, motor/modelo ausentes y concurrencia de dos intentos;
- audio distinto de WAV PCM16, mono, 16 kHz, duración inferior a 0,5 s o superior a 5 s, cuerpo mayor de 161.024 B;
- transcripción vacía, excesiva, anomalías de motor, subida térmica o respuesta JSON fuera de 1023 B.

No inicia micrófono en el servidor. **El navegador** deberá solicitar el micrófono tras gesto voluntario, detener las pistas con STOP, generar WAV PCM16 y enviar al PWA solo en loopback y mismo origen. La guardia consume el WAV en directorio temporal con permisos 0600, llama a `oido.transcribir(..., cpu_only=True,threads=2,timeout_sec=25)`, elimina audio y devuelve sólo transcripción con SHA-256 de audio/texto/modelo, idioma, tiempo de inferencia y `cause=not_authenticated_brain_reply`. No concede permisos ni copia el texto a Mesa. Toda inferencia sigue HOLD.

`oido.py` gana **opciones adicionales** CPU-only, presupuesto de hilos y timeout para este consumidor; la invocación histórica de otros llamantes no cambia.

## Pruebas

- **`test_voz_lectura.py` ya registrada en `bin/pruebas`** incorpora los 13 casos de `LocalSTT` y 3 casos `STTConstraints` (antes pruebas temporales separadas). Total real **22/22 ×2 PASS** en Beelink con `PRECEPTOROS_SIN_HARDWARE=1`: 6 casos TTS existentes, 13 negativos+positivos STT y 3 sobre límites CPU/compatibilidad. No se crea suite sin registrar, no se modifica `bin/pruebas`.
- CI de rama rebasada después del merge APP #415 requiere comprobar HEAD final; el CI #1966 falló por el antiguo caché v246 heredado y dos suites no inscritas. Ninguna aserción de seguridad se eliminó.
- B-03 TTS ya servida; ninguna afirmación de E2E voz o de servicio B04.

## Integración posterior con propietario de rutas

Claude NODE3-07 ha reclamado `bin/preceptoros-pwa` y parte de `interface/app.html` en #416. **Este PR NO modifica esas rutas, ni `avatar_voice.js`, ni service worker**. Coordinar un único cambio compatible: el handler `POST /api/voz/stt` en PWA verificará `_nodo_local_autorizado`, esquema/longitud y pasará WAV a `voz_stt_local.transcribe_once`. Cliente del avatar solo podrá usarlo en Beelink loopback y tras consentimiento de micrófono; no se activará fallback remoto silencioso. Parada física y tab de Talk se probarán después de una ventana térmica segura. No abrir dos routers.

## E0/E1
El catálogo Ollama de Onex puede responder pero no acredita Hexelion. Soberano/Train-02 deben aportar endpoint autentificado, digest y S1/cadena de autorización antes de enviar la transcripción al cerebro real; **NO_DATA(authenticated_hexelion_endpoint_unverified)**.

## Riesgos/ROLLBACK
No hay deploy, servicio, captura, modificación de claves, GPU ni escritura fuera de rama. Revertir este PR retira el guardia/propuesta; los otros usuarios de `oido.transcribir` siguen funcionando en su firma histórica.
