# ONLINE3 · Solicitud de nodo desde APP Beelink

La APP de Beelink reutiliza el mismo formulario My node y el mismo contrato de Aduana que Android OWNER. Tras el gesto de consentimiento, la UI local envía POST a `/api/nodo/identity` con JSON `{"esquema":"preceptoros.pwa-node-deployment-request/1","node":"nodo.42.fixture","nonce":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","consent":true}`. Usar un nonce criptográfico de 16 bytes por intento consentido y conservarlo para reintentar ese intento. El propósito del formulario queda local.

Para `requestDeploymentReview`, pasar un adaptador `requestPreliminary` que use esa ruta en el origen loopback de la APP. HTTP 200/202 con `preliminaryReceiptValidated:true` y `trackingId` correlacionado acredita PENDING. Sin recibo, pintar la causa de NO_DATA. El digest de instalación representa una alegación y queda fuera de la respuesta al navegador.

El operador contrasta el gesto de APP y el request ID en la bandeja privada de Aduana. Usar decisión SSHSIG, plan firmado, cédula, admisión y latido ya existentes. Cada etapa requiere su propia prueba. La ruta heredada de provisión local conserva su esquema.

- [x] Reutilizar el intake existente con contrato exacto, consentimiento y recibo pendiente.
- [ ] Observar consentimiento real de APP con testigo; no acreditar origen con un POST manual.
- [ ] Observar firma humana, admisión, emisión física e inclusión independiente en producción ×2.
