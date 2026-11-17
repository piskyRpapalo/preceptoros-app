#!/usr/bin/env bash
# Verifica una APK de PreceptorOS MVP. Sale con 1 si cualquier comprobacion falla.
# Uso: verificar_apk.sh <ruta.apk>
set -u
APK="${1:?uso: verificar_apk.sh <apk>}"
BT="${ANDROID_BUILD_TOOLS:-$HOME/android-sdk/build-tools/36.0.0}"
CERT_SHA256="16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f"  # certificado publico de la clave 'preceptoros'
fallos=0
check() { if eval "$2"; then echo "PASS  $1"; else echo "FAIL  $1"; fallos=$((fallos+1)); fi; }
check "firma v2 valida"                "\"$BT/apksigner\" verify \"$APK\" >/dev/null 2>&1"
check "certificado esperado"           "\"$BT/apksigner\" verify --print-certs \"$APK\" 2>/dev/null | grep -q '$CERT_SHA256'"
check "sin permiso INTERNET"           "! \"$BT/aapt2\" dump permissions \"$APK\" 2>/dev/null | grep -q INTERNET"
check "no depurable"                   "! \"$BT/aapt2\" dump xmltree \"$APK\" --file AndroidManifest.xml 2>/dev/null | grep -qi debuggable"
check "paneles dentro (app.html)"      "unzip -l \"$APK\" assets/app.html 2>/dev/null | grep -q assets/app.html"
check "paneles dentro (app.js)"        "unzip -l \"$APK\" assets/app.js 2>/dev/null | grep -q assets/app.js"
check "paneles dentro (app.css)"       "unzip -l \"$APK\" assets/app.css 2>/dev/null | grep -q assets/app.css"
echo "--- $fallos fallo(s)"
[ "$fallos" -eq 0 ]
