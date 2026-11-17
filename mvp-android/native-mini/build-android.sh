#!/usr/bin/env bash
# Reproducible local-only arm64 build; never download or publish model weights.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${LLAMA_CPP_SRC:?Set LLAMA_CPP_SRC to a locally verified checkout}"
NDK="${ANDROID_NDK_HOME:?Set ANDROID_NDK_HOME to an installed NDK}"
CMAKE="${ANDROID_CMAKE:-cmake}"
EXPECTED="f2cc7282ce0042641df55e0e563b75e824e2b647"
ACTUAL="$(git -C "$SRC" rev-parse HEAD)"
if [[ "$ACTUAL" != "$EXPECTED" ]]; then echo "NO_DATA(llama_source_revision_mismatch): $ACTUAL" >&2; exit 2; fi
BIN="$ROOT/.native-build/arm64-v8a"
"$CMAKE" -S "$ROOT/native-mini" -B "$BIN" \
  -DCMAKE_TOOLCHAIN_FILE="$NDK/build/cmake/android.toolchain.cmake" \
  -DANDROID_ABI=arm64-v8a -DANDROID_PLATFORM=android-28 \
  -DANDROID_STL=c++_static -DCMAKE_BUILD_TYPE=Release \
  -DLLAMA_CPP_SRC="$SRC" -DCMAKE_POSITION_INDEPENDENT_CODE=ON
"$CMAKE" --build "$BIN" -j 6 --target mini_llama
install -Dm755 "$BIN/libmini_llama.so" "$ROOT/app/src/main/jniLibs/arm64-v8a/libmini_llama.so"
echo "arm64 native runtime built: $(sha256sum "$ROOT/app/src/main/jniLibs/arm64-v8a/libmini_llama.so")"
