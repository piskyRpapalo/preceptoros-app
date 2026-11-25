#!/usr/bin/env bash
# On-phone Talk runner (libllama_server.so) for -PlocalRunner, built for EVERY arm64 phone we ship to.
# Measured 2026-11-25: the previous runner (sha 18f14e79…) carried 260 i8mm instructions (smmla) and died
# with SIGILL on the Doogee S110 (MT6789, ARMv8.2 + dotprod, no i8mm) the moment Talk sent a message.
# Baseline here: armv8.2-a+dotprod+fp16, GGML_NATIVE=OFF. Same pinned llama.cpp revision as build-android.sh.
# The embedded web UI is never served (--no-webui), so its asset download is skipped with local stubs.
set -euo pipefail
SRC="${LLAMA_CPP_SRC:?Set LLAMA_CPP_SRC to a locally verified checkout}"
NDK="${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to an installed NDK}"
CMAKE="${ANDROID_CMAKE:-cmake}"
NINJA="${ANDROID_NINJA:-$(dirname "$CMAKE")/ninja}"
OUT="${1:?Usage: build-runner-android.sh <out/libllama_server.so>}"
EXPECTED="f2cc7282ce0042641df55e0e563b75e824e2b647"
ACTUAL="$(git -C "$SRC" rev-parse HEAD)"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then echo "NO_DATA(llama_source_revision_mismatch): $ACTUAL" >&2; exit 2; fi
BIN="${RUNNER_BUILD_DIR:-$(mktemp -d)}"
"$CMAKE" -S "$SRC" -B "$BIN" -G Ninja -DCMAKE_MAKE_PROGRAM="$NINJA" \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-26 -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16 -DGGML_OPENMP=OFF \
  -DLLAMA_CURL=OFF -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_SERVER=ON \
  -DLLAMA_BUILD_UI=OFF -DLLAMA_USE_PREBUILT_UI=OFF -DLLAMA_BUILD_HTML=OFF
DIST="$BIN/tools/ui/dist"; mkdir -p "$DIST"
for f in index.html manifest.webmanifest sw.js build.json version.json bundle.stub.js bundle.stub.css workbox-stub.js; do
  [[ -e "$DIST/$f" ]] || echo '{}' > "$DIST/$f"
done
"$CMAKE" --build "$BIN" --target llama-server -j "${JOBS:-8}"
STRIP="$(ls "$NDK"/toolchains/llvm/prebuilt/*/bin/llvm-strip | head -1)"
OBJDUMP="$(dirname "$STRIP")/llvm-objdump"
"$STRIP" -o "$OUT" "$BIN/bin/llama-server"
bad="$("$OBJDUMP" -d "$OUT" | grep -cE '\s(smmla|ummla|usmmla|bfmmla|ptrue|whilelo)\s' || true)"
if [[ "$bad" != "0" ]]; then echo "FAIL runner carries $bad i8mm/SVE instructions" >&2; exit 1; fi
echo "runner built for armv8.2-a+dotprod: $(sha256sum "$OUT")"
