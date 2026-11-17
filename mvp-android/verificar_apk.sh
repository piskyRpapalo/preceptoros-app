#!/usr/bin/env bash
# Verify the legacy OFFLINE Android shell. This does not certify a functional V1:
# no Android chat backend, model runtime or admission receiver is tested here.
# Fail closed: missing/unusable inspection tools MUST NOT produce green checks.
set -uo pipefail

usage() { echo "Uso: $0 <ruta.apk>" >&2; exit 2; }
[[ $# -eq 1 && -n "${1:-}" ]] || usage
APK="$1"
BT="${ANDROID_BUILD_TOOLS:-$HOME/android-sdk/build-tools/36.0.0}"
AAPT2="$BT/aapt2"
APKSIGNER="$BT/apksigner"
CERT_SHA256="16761a1e61376506acf4abdadfdddeb96ff18b4cc80a3d98205c91648e4c010f"
fallos=0
pass() { printf 'PASS  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1" >&2; fallos=$((fallos+1)); }

if [[ ! -f "$APK" || ! -r "$APK" ]]; then
  fail "APK ausente o ilegible"; exit 1
fi
for tool in "$APKSIGNER" "$AAPT2"; do
  if [[ ! -x "$tool" ]]; then
    fail "herramienta ausente/no ejecutable: $tool"
  fi
done
if ! command -v unzip >/dev/null 2>&1; then
  fail "unzip no disponible"
fi
if (( fallos > 0 )); then
  echo "--- $fallos fallo(s)" >&2
  exit 1
fi

if "$APKSIGNER" verify "$APK" >/dev/null 2>&1; then
  pass "firma APK verificada"
else
  fail "firma APK inválida o sin verificar"
fi

if certs=$("$APKSIGNER" verify --print-certs "$APK" 2>/dev/null); then
  if printf '%s\n' "$certs" | grep -Fqi "$CERT_SHA256"; then
    pass "certificado esperado"
  else
    fail "certificado distinto al esperado"
  fi
else
  fail "certificado sin inspeccionar"
fi

# Inspections must execute successfully and return nonempty, recognizable data.
# Negated grep alone is insufficient: a missing aapt2 must never mean no INTERNET.
if permissions=$("$AAPT2" dump permissions "$APK" 2>/dev/null); then
  if [[ -z "$permissions" ]]; then
    fail "permisos: inspección vacía"
  elif ! printf '%s\n' "$permissions" | grep -Eq '^package: org[.]preceptoros[.]mvp$'; then
    fail "permisos: paquete inesperado o respuesta inválida"
  elif printf '%s\n' "$permissions" | grep -Eqi 'android[.]permission[.]INTERNET'; then
    fail "prototipo offline solicita INTERNET"
  else
    pass "sin permiso INTERNET (prototipo offline)"
  fi
else
  fail "permisos: inspección fallida"
fi

if manifest=$("$AAPT2" dump xmltree "$APK" --file AndroidManifest.xml 2>/dev/null); then
  if ! printf '%s\n' "$manifest" | grep -Eq '^[[:space:]]*E: manifest'; then
    fail "manifiesto: inspección inválida"
  elif printf '%s\n' "$manifest" | grep -Eqi 'android:debuggable|android[.]debuggable'; then
    fail "APK depurable"
  else
    pass "manifiesto no declara debuggable"
  fi
else
  fail "manifiesto: inspección fallida"
fi

if files=$(unzip -Z -1 "$APK" 2>/dev/null); then
  for name in app.html app.js app.css documents.js zonas.js sw.js; do
    if printf '%s\n' "$files" | grep -Fxq "assets/$name"; then
      pass "recurso integrado: $name"
    else
      fail "recurso ausente: $name"
    fi
  done
else
  fail "inventario ZIP ilegible"
fi

echo "--- $fallos fallo(s)"
(( fallos == 0 ))
