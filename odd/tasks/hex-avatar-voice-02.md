# Hexelion · Avatar y voz nativos en Talk (22 noviembre 2026)

**Alcance:** módulo opcional del panel Talk existente. No crea APP, cerebro, ruta Ollama, juez ni autoridad nueva. No toca CineK.

## Reutilización
- Talk `#form-chat/#dicho` y controles de perfil/ruta de `app.js`.
- Voz/cancelación local de `native_voice.js`; lectura y sonido accesible de `audio_accessibility.js`; Acho existente.
- Ilustración ya servida `/assets/avatar-github.png` (106255 B). El GLB físico (~48 MB, una malla sin rig/animaciones) y el pixel-art de cuarentena no se empaquetan.
- El rostro presenta estados `listening/thinking/speaking/interrupted/awaiting_authorization/error` con movimiento reducido y texto/ARIA/JSON generados desde un solo registro.

## Privacidad y autorización
- Solo `SpeechRecognition.available({langs:['es-ES'],processLocally:true}) === 'available'` permite captura. Sin llamada `install()`, sin reconocimiento remoto ni acceso autónomo al cerebro.
- Texto reconocido → formulario Talk existente; ese servidor conserva el control de perfil, modelo, S1/OS y permisos.
- Silenciar e interrumpir cancelan únicamente captura y lectura locales. Cancelación de una inferencia remota: `NO_DATA(server_cancel_not_supported)`.
- `awaiting_authorization` expresa únicamente una causa publicada por Talk; jamás concede autorización.
- `speaking` significa solicitud de síntesis, no audición atestiguada. La frase reproducible incluye estado, causa y procedencia.

## Verificación y puertas
- Test dirigido: `node tests/avatar_voice_cases.cjs` → 39/39 ×2 en DOM simulado; nunca cuenta como micrófono/lector físico.
- Revisar `./bin/pruebas` ×2 y el CI de la PR; cache SW v244, `version.py` y assets alineados.
- Estado físico: Whisper tiny local, sin STT real; Piper APP `puede=false`; Chrome headless sin voces españolas locales y STT español instalable pero no verificado. ONEX responde GET de estado, seis modelos catalogados, cero residentes en la sonda; sin turno E2E.
- Entrada autorizada de OWNER para primer turno: micrófono consentido, STT local, Talk con perfil válido, respuesta atribuida, TTS local, audio escuchado, teclado/lector, interrupción; n representativo para p50/p95 E2E y memoria. Sin testigo = `NO_DATA(causa)`.

## Marcha y rollback
Rama aislada y PR HITL; no merge ni despliegue sin firma exact-head del Soberano. Revertir la PR restaura el armazón anterior. No descarga de pesos, carga GPU, claves, ni reinicios.
