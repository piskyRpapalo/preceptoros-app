# Ronda 2 · Envío de cédula OWNER desde la APP

Tras el consentimiento y la aprobación de la solicitud existente, My node entrega la cédula firmada al POST local `/api/nodo/export` con JSON `{"cedula":{…}}`. Solo el origen local OWNER alcanza el exportador. El proceso verifica SSHSIG con la confianza local existente y remite a Aduana por el único destino configurado en código.

HTTP 202 corresponde a `pendiente`. HTTP 200 corresponde a `verificado`. El cuerpo contiene `estado`, `codigo`, `causa`, `recibidos` y `recibo` correlacionado por cédula, plan y nodo. La interfaz nunca recibe el paquete reflejado del Worker. Ambos estados requieren evidencia separada para latido y presencia pública.

- [x] Ejercitar el manejador real con una firma OpenSSH efímera y un recibo sintético.
- [x] Rechazar origen visitante y proxy antes de leer credenciales.
- [ ] Recibir la firma OWNER y el recibo de Aduana de una alta física originada en la APP.
