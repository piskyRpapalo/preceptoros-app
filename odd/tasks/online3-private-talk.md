# ONLINE3 · Talk privado

## Contrato para interfaz

- Web OWNER usa el `POST /api/hexelion/chat` existente, con su propio Origin, JSON `{"texto":"…"}` y hasta 1.023 bytes. La configuración de APP requiere un origen exacto `PRECEPTOROS_HEXELION_SERVE_ORIGIN` y el login OWNER exacto `PRECEPTOROS_HEXELION_SERVE_OWNER`. Mantener estos valores fuera de Git.
- Usar el listener loopback exclusivo de APP y Tailscale Serve como único proxy al listener. Serve retira las cabeceras de identidad aportadas por el cliente. Funnel y otros proxies deben quedar fuera de este trayecto.
- Android OWNER expone `PreceptorPrivateTalkNative` en el documento empaquetado. La UI envía JSON por `postMessage` con `id` hexadecimal de 32 caracteres y `op` igual a `status`, `configure` o `send`. Solo `send` incluye `texto`. La respuesta a cada mensaje es `{"id":"…","result":{…}}`. `configure` abre una confirmación del sistema para guardar u olvidar el origen privado y puede esperar una decisión humana.
- `result.estado: "MEASURED"` requiere un turno atribuido a Hexelion, con modelo, tiempo y fuentes. `NO_DATA` trae `causa` y, cuando corresponda, `stage` con `connection`, `authentication`, `model`, `context` o `request`. Un origen guardado sigue en `NO_DATA(private_talk_auth_unverified)` hasta un turno verificado. Para `send`, esperar al menos 145 s antes de declarar timeout del cliente. El timeout se representa como falta de respuesta confirmada.
- La elección local sigue usando el puente offline existente. Una acción explícita del usuario elige Talk privado. El servidor deja los comandos y lecturas especiales en el carril local.

## Comprobaciones

- [x] Medir rechazo del endpoint servido antes del cambio.
- [x] Implementar autorización en la ruta existente y puente Android OWNER.
- [x] Ejercitar origen, proxy, login, voces, comandos y estados de estación en el manejador real con dobles de transporte.
- [ ] Revisión e integración con FIRMO de la cabeza exacta.
- [ ] Validar la interfaz y el intercambio HTTPS ×2 en ambos Android fuera del Wi-Fi, en coordinación con Central.

Cobertura de construcción y preparación de revisión en el mandato ONLINE3 de la Mesa del 21-11-2026 y THE MARCH. La configuración operativa y las firmas quedan en la ceremonia del Soberano.
