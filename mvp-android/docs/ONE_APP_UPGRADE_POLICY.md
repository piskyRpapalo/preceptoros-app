# Android · Una única APP por dispositivo

**Contrato de empaquetado, no instrucción de instalación.** La identidad Android canónica del propietario es `org.preceptoros.app`. El paquete `org.preceptoros.mvp` es histórico y **no** debe aparecer como segunda APP tras una compilación normal.

## Construcción y actualización

- `mvp-android/app/build.gradle` utiliza `org.preceptoros.app` por defecto. La clase Java permanece en `org.preceptoros.mvp`: namespace de código y applicationId instalado no son equivalentes.
- La única excepción se reserva a una **exportación/migración del paquete antiguo**, con `-PmvpAppId=org.preceptoros.mvp -PlegacyMigrationOnly=true`, worktree independiente y autorización específica. No presentar esa APK como una nueva release ordinaria.
- Los códigos de versión de la APP canónica deben crecer para actualizar en el mismo package ID y conservar el certificado del propietario. No instalar APK DEBUG ni cambiar firmas durante la actualización.
- **Un certificado común no permite cambiar el applicationId in-place.** Si un teléfono tiene solo el paquete legacy, primero debe poder exportar su estado local, importar el archivo en la APP canónica y demostrar integridad con consentimiento; no desinstalar el antiguo antes de conservar y verificar los datos. Android `allowBackup=false` prohíbe asumir que ADB guardó sus preferencias.
- Una duplicación ya instalada puede **deshabilitarse reversiblemente**, manteniendo los datos, mientras se valida la migración. Eso deja una sola APP habilitada, pero no equivale a eliminar todos los paquetes legacy.

## Testigo antes de cualquier operación

Ejecutar `lab/bin/android_app_witness.py --serial <ADB_SERIAL> --alias <ALIAS>` desde Lab actualizado. El número de serie no aparece en el recibo. Comprobar:

1. Un único paquete PreceptorOS **habilitado** y canónico.
2. Certificado declarado en bloque firmado y versión, más comprobación del instalador Android al aplicar una nueva APK.
3. Motor JNI y GGUF empaquetados, sin afirmar que generan respuestas hasta medir una pregunta libre.
4. Sin modificación ni pérdida de datos locales; el release firmado y su rollback están disponibles.
5. Pruebas físicas en cada dispositivo, incluido arranque sin red y cambio de conexión.

## Hexelion remoto sin crear un segundo nodo

El Beelink conserva la autoridad del nodo. La APP instalada en Android controla **sus propios modelos locales**, pero solo puede solicitar inferencia de Hexelion remoto tras una autorización verificable.

Tailscale o una IP de loopback **no son credenciales**. La ruta privada deberá verificar identidad efectiva, alcance limitado, expiración, nonce, protección de replay y revocación, con recibos de un turno real y sin exponer los endpoints administrativos de APP al público. Hasta entonces, `NO_DATA(private_authenticated_model_turn_E2E)`.

MCP stdio local no constituye por sí solo un servidor remoto; no extenderlo a Internet por conveniencia. El selector `owner_model_slots.js` es todavía una preferencia `DRAFT_ONLY`, no una prueba de conexión ni una concesión de permisos.

La APP visible, los lectores de pantalla y Acho deben declarar el mismo estado: **LOCAL_READY / REMOTE_UNAVAILABLE** solo si la inferencia local está medida y el remoto no; ninguna interfaz puede afirmar que Hexelion está hablando antes de un turno privado autenticado.
