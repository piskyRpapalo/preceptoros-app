#!/usr/bin/env bash
# PreceptorOS · desinstalador de escritorio. Linux.
#
# QUITA, y solo esto, lo que crearon install.sh y bin/instalar-pc:
#   ~/.local/share/applications/preceptoros.desktop      (la entrada del menú)
#   ~/.local/bin/preceptoros-abrir                        (el lanzador)
#   ~/.local/share/icons/hicolor/256x256/apps/preceptoros.png
#   el árbol clonado ($PRECEPTOROS_DESTINO, por defecto ~/preceptoros), solo si es un clon de PreceptorOS
#     sin cambios propios (si tiene ficheros modificados o commits sin subir, NO lo borra y lo dice).
#
# NO QUITA tus datos: ~/.preceptoros (memoria, conversaciones, identidad, ajustes) se queda donde está.
# Para borrarlos también hace falta --borrar-datos Y escribir la frase que se pide. Sin terminal no se borra nada.
#
# No usa sudo. Para el servidor solo si está corriendo desde ESTE árbol.
#
# ESTADO DE PRUEBAS: Linux · PROBADO en un contenedor Ubuntu 24.04 aislado (tests/ubuntu_e2e). macOS · NO PROBADO.
set -u

DESTINO="${PRECEPTOROS_DESTINO:-$HOME/preceptoros}"
DATOS="$HOME/.preceptoros"
APPS="$HOME/.local/share/applications"
BORRAR_DATOS=0
SIN_PREGUNTAR=0
for a in "$@"; do
  case "$a" in
    --borrar-datos) BORRAR_DATOS=1 ;;
    --si) SIN_PREGUNTAR=1 ;;
    -h|--help) sed -n 2,16p "$0"; exit 0 ;;
    *) echo "opción desconocida: $a" >&2; exit 2 ;;
  esac
done

ok() { printf '  ok  %s\n' "$*"; }
nd() { printf '  --  %s\n' "$*"; }
no() { printf '  NO  %s\n' "$*" >&2; }

echo "PreceptorOS · desinstalar"
echo "  árbol: $DESTINO"
echo "  datos: $DATOS (se conservan$( [ $BORRAR_DATOS = 1 ] && echo ' salvo confirmación' ))"
if [ $SIN_PREGUNTAR = 0 ]; then
  [ -t 0 ] || { no "sin terminal: repite con --si para quitar la aplicación (los datos nunca se borran sin terminal)"; exit 2; }
  printf '¿Quitar la aplicación? [s/N] '; read -r r; case "$r" in s|S|si|sí|y|Y) ;; *) echo "nada cambiado"; exit 0 ;; esac
fi

# 1 · el servidor de este árbol (si lo hay)
if command -v pgrep >/dev/null 2>&1; then
  for pid in $(pgrep -f "preceptoros-pwa" 2>/dev/null); do
    cwd="$(readlink "/proc/$pid/cwd" 2>/dev/null || true)"
    if [ -n "$cwd" ] && [ "$cwd" = "$(cd "$DESTINO" 2>/dev/null && pwd -P)" ]; then kill "$pid" 2>/dev/null && ok "servidor parado (pid $pid)"; fi
  done
fi

# 2 · menú, lanzador, icono
for f in "$APPS/preceptoros.desktop" "$HOME/.local/bin/preceptoros-abrir" "$HOME/.local/share/icons/hicolor/256x256/apps/preceptoros.png"; do
  if [ -e "$f" ]; then rm -f "$f" && ok "quitado $f"; else nd "no estaba $f"; fi
done
command -v update-desktop-database >/dev/null 2>&1 && update-desktop-database "$APPS" 2>/dev/null || true

# 3 · el árbol: solo un clon limpio de PreceptorOS
if [ -d "$DESTINO/.git" ]; then
  url="$(git -C "$DESTINO" remote get-url origin 2>/dev/null || true)"
  sucio="$(git -C "$DESTINO" status --porcelain 2>/dev/null | head -1)"
  propios="$(git -C "$DESTINO" log --oneline '@{u}..' 2>/dev/null | head -1)"
  if [ ! -x "$DESTINO/bin/preceptoros-pwa" ]; then
    no "$DESTINO no parece PreceptorOS (falta bin/preceptoros-pwa): no lo toco"
  elif [ -n "$sucio" ] || [ -n "$propios" ]; then
    no "$DESTINO tiene cambios tuyos: no lo borro. Guárdalos y bórralo a mano si quieres"
  else
    rm -rf -- "$DESTINO" && ok "árbol quitado ($url)"
  fi
elif [ -e "$DESTINO" ]; then
  no "$DESTINO existe pero no es un clon: no lo toco"
else
  nd "no había árbol en $DESTINO"
fi

# 4 · los datos
if [ $BORRAR_DATOS = 1 ] && [ -d "$DATOS" ]; then
  [ -t 0 ] || { no "borrar datos exige terminal: los datos se conservan"; exit 0; }
  echo "Vas a borrar $DATOS: memoria, conversaciones, identidad y ajustes. No se puede deshacer."
  printf 'Escribe exactamente  borrar mis datos  para seguir: '; read -r frase
  if [ "$frase" = "borrar mis datos" ]; then rm -rf -- "$DATOS" && ok "datos borrados"; else ok "frase distinta: datos conservados"; fi
else
  [ -d "$DATOS" ] && ok "datos conservados en $DATOS" || nd "no había datos en $DATOS"
fi
echo "listo."
