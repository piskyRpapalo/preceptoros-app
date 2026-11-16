#!/usr/bin/env bash
# Ubuntu end-to-end install, update and uninstall in a throwaway container. Manual; not part of bin/pruebas.
#   tests/ubuntu_e2e/run.sh [ubuntu:24.04]
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
docker run --rm -e EXPECTED_SHA="$EXPECTED" -v "$W/install.sh:/in/install.sh:ro" -v "$W/mirror.git:/mirror.git:ro" \
  -v "$HERE/tests/ubuntu_e2e/inside.sh:/in/inside.sh:ro" "$IMG" bash -c '
  set -e; export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq >/dev/null && apt-get install -y -qq python3 git curl ca-certificates desktop-file-utils procps >/dev/null
  useradd -m persona; su persona -c "bash /in/inside.sh"'
