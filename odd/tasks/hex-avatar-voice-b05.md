# HEX-AVATAR-VOICE-WEB-B-05 · APP Talk ↔ STT local · 22-11-2026
Codex GPT-6 Web, carril B · Owner: Soberano · coordinación Mesa #51.
Continuidad: B-04, APP #415/#419 fusionadas; Claude #416 y A/Train-02 #417 fusionadas.

## Problema y fuente
La interfaz Talk ya dispone de avatar, STOP/MUTE y lectura española por eSpeak-NG;
pero Chrome no acredita SpeechRecognition español on-device. El adaptador
`voz_stt_local.py` reutiliza `oido.py`/Whisper.cpp Tiny, en main tras APP #419,
sin ruta HTTP ni cliente navegador. No crear segundo cerebro ni APP.

## Adaptación
- POST /api/voz/stt en servidor PWA ya existente, con origen exacto
  loopback y misma autoridad que TTS nativo, método/body/headers acotados.
  Se niegan Host/Origin duplicados, proxy, Transfer-Encoding, Content-Encoding,
  comando distinto, contenido fuera de presupuesto y orígenes remotos.
- WAV 16kHz mono PCM16 0.5–5 s, hasta 161024 B, capturado por permiso
  explícito navegador, sin subida a proveedor externo. Si Chrome no tiene
  reconocimiento on-device acreditado, se ofrece el motor local existente.
- Camino único posterior: el texto de STT llena el formulario Talk EXISTENTE;
  el formulario decide permisos y modelo. No se confunde transcripción con
  respuesta de Hexelion ni con permiso administrativo.
- STOP y MUTE abortan permiso/captura/fetch desde navegador; sin promesa de
  cancelar un proceso de servidor que haya comenzado.
- Se conservan estados hexelion.avatar-state/1 para visual/ARIA/voz;
  `lastSTT()` expone a máquina hashes y tiempos, sin audio crudo.
- Cache APP sube v247→v248 y URL de avatar_voice.js v2→v3 con pines
  exactos reconciliados, sin reescribir relatos históricos B-03.

## Seguridad térmica
Beelink power-saver desde 20:59Z: k10temp Tctl
21:03:36Z 60.5°C; ventana 21:04Z 61.0→59.75°C;
21:10:04Z 87.75°C. **HOLD prueba física/STT/inferencia**.
Guardia existente no inicia STT >=75°C; se conserva.
Swap 8/8 GiB; Chrome y ChatGPT OWNER cargan CPU, no detenidos.

## Evidencia y límites
LOCAL branch codex/avatar-b05-local-stt-20261122 desde main 70daf731.
- Backend voz 26/26 pruebas sintéticas ×2 PASS (incluye 4/4 HTTP B05).
- Avatar anterior 43/43; fallback local extendido con STT/STOP/
  térmica/huellas, sin micrófono real; test JS de fixture.
- Version pins reconciliados con SW v248. CI exact-head pendiente.
- Motor físico Whisper **NO_DATA(thermal_hold_fluctuations)**.
- Micrófono/latencia/TER/word accuracy físico:
  **NO_DATA(physical_microphone_capture_unperformed)**.
- E0 cerebro autenticado **NO_DATA(OWNER_model_identity_and_deployment_pending)**;
  #417 en MAIN solo representa una selección digest catalog-match.
- Respuesta y TTS audible E2E **NO_DATA(authenticated_dialogue_not_tested)**.
- TTS anterior audible por Soberano en Mesa #51 #7085336056,
  STOP/MUTE físico **NO_DATA(owner_witness_pending)**.
- Verificación de cero egress: el código usa fetch relativo loopback;
  paquete/red física **NO_DATA(packet_capture_not_performed)**.

## Riesgos y siguiente pieza
Backend y cliente requieren deploy exact-head y recarga SW; autorización
OWNER al cerebro TRAIN-02 y comprobación térmica sostenida <75°C.
Si el equipo se enfría, medir secuencia mic real → transcripción (CER/WER,
latencia) → Talk autenticado → TTS altavoz → STOP/MUTE físico con testigo.
No afirmar LIVE por HTTP200, hashes o fixtures. No apagar sesiones activas.
