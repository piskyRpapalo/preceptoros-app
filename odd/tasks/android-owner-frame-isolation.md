# Android · aislar capacidades OWNER del iframe público

`addJavascriptInterface` exponía las fachadas Mini y Review a todos los frames del WebView. Las dos pasan a un puerto AndroidX restringido al origen del APK. Los puertos de admisión, latido y Talk privado aplican la misma regla nativa. Cada callback comprueba el frame principal, el origen exacto, el documento exacto y su estado de carga antes de interpretar mensajes. MINI conserva la huella del modelo y mueve la ejecución a un hilo de trabajo acotado a un turno. Review conserva su política de URLs y el gesto de la interfaz. Un WebView sin soporte para el puerto o la inyección de inicio queda sin estas capacidades.

El probe de instrumentación usa el Activity real y un iframe aislado con `srcdoc` en un Android de laboratorio. Usa valores inertes y realiza cero solicitudes de admisión, latido, chat privado o publicación. No sustituye la medición JNI arm64 en los teléfonos.

Comandos desde `mvp-android`, con Android SDK configurado y un **emulador aislado** de destino:

```sh
./gradlew :app:assembleDebug :app:assembleDebugAndroidTest -PappProfile=OWNER -PunsignedRelease=true --offline
adb -s "<emulador>" install -r app/build/outputs/apk/debug/app-debug.apk
adb -s "<emulador>" install -r app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
adb -s "<emulador>" shell am instrument -w org.preceptoros.app.test/org.preceptoros.mvp.OwnerFrameProbe
```

Para producción, construir `assembleRelease` OWNER con el modelo fijado, exigir certificado legítimo y comparar con v7. La aprobación de instalación se aplica primero al S110 y después al Tank 3, previa comprobación del primero.
