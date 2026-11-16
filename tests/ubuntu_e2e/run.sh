#!/usr/bin/env bash
# Ubuntu end-to-end install, update and uninstall in a throwaway container. Manual; not part of bin/pruebas.
#   tests/ubuntu_e2e/run.sh [ubuntu:24.04]
#   HEXELION_ENDPOINT=http://127.0.0.1:<port> tests/ubuntu_e2e/run.sh   # + a real model turn and a browser walk
# With HEXELION_ENDPOINT (a loopback door to an authorized node, e.g. the rack's SSH tunnel) the container joins the
# host network so its loopback reaches that door, and the host drives Chromium over every panel of the installed APP
# (NODE_PATH with playwright-core and CHROME_PATH are then required). Without it the model turn is NO_DATA.
# Needs docker and network (apt + github.com). The host only provides: the installer the website links to (downloaded
# here, checked against GitHub's published digest), and a bare mirror of this repository for the update step.
# No host directory is writable from the container; nothing under the host HOME is read except this tree.
set -eu
IMG="${1:-ubuntu:24.04}"
HERE="$(cd "$(dirname "$0")/../.." && pwd)"
W="$(mktemp -d)"; trap 'rm -rf "$W"' EXIT
URL="https://github.com/piskyRpapalo/PreceptorOS/releases/download/v1.3/install.sh"
curl -fsSL -o "$W/install.sh" "$URL"
EXPECTED="$(gh release view v1.3 -R piskyRpapalo/preceptoros-app --json assets -q '.assets[]|select(.name=="install.sh")|.digest' | sed 's/^sha256://')"
[ -n "$EXPECTED" ] || { echo "NO_DATA: published digest unreadable"; exit 2; }
git clone -q --bare --no-local "$HERE" "$W/mirror.git"
git -C "$W/mirror.git" update-ref refs/heads/main "$(git -C "$HERE" rev-parse HEAD)"
git -C "$W/mirror.git" symbolic-ref HEAD refs/heads/main
mkdir -m 777 "$W/sync"
NET=(); [ -n "${HEXELION_ENDPOINT:-}" ] && NET=(--network host)
docker run --rm "${NET[@]}" -e EXPECTED_SHA="$EXPECTED" -e HEXELION_ENDPOINT="${HEXELION_ENDPOINT:-}" \
  -v "$W/install.sh:/in/install.sh:ro" -v "$W/mirror.git:/mirror.git:ro" -v "$W/sync:/sync" \
  -v "$HERE/tests/ubuntu_e2e/inside.sh:/in/inside.sh:ro" "$IMG" bash -c '
  set -e; export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null && apt-get install -y -qq python3 git curl ca-certificates desktop-file-utils procps >/dev/null
  useradd -m persona; su persona -c "HEXELION_ENDPOINT=$HEXELION_ENDPOINT bash /in/inside.sh"' &
DOCKER=$!
if [ -n "${HEXELION_ENDPOINT:-}" ]; then
  for _ in $(seq 1 900); do [ -f "$W/sync/ready" ] && break; kill -0 $DOCKER 2>/dev/null || break; sleep 1; done
  if [ -f "$W/sync/ready" ]; then
    node "$HERE/tests/ubuntu_e2e/panels.browser.cjs" "${SHOTS:-$W/shots}" > "$W/sync/walk.json" 2>"$W/sync/walk.err" \
      && echo "PASS:$(python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));print(d["panels"],"panels",d["talk"])' "$W/sync/walk.json")" > "$W/sync/go" \
      || echo "FAIL:$(head -c 120 "$W/sync/walk.err" | tr -d '\n')" > "$W/sync/go"
    cat "$W/sync/walk.json" >&2
  fi
fi
wait $DOCKER
