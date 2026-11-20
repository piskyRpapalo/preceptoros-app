# Android Capability Ledger · APP 1.0 to APP 1.1

**Lane:** APP only. **Coordinator:** Mesa privada #51, Codex GPT-6 Central.
**Implementation base:** APP main 1c58b39df9cc36093268c6ff1c57c349d9c0e3e8
after merged PR #369. This task does not alter WEB, LAB, Android
installations, personal documents, keystores or models.

## Problem and source

A marketing name, a Gradle source default, a built signed APK, an installed
Android package and a demonstrated model turn are distinct objects. A release
can silently drop mathematical gates, JNI, model bytes, screen reader controls,
six panels, node consent or Documents features unless each layer is checked.

The existing source witnesses are in mvp-android/native-mini/mini_quality.h,
mini_jni.cpp, mvp-android/app/build.gradle, interface/app.html,
interface/audio_accessibility.js, interface/acho_sonido.js, Android native
bridge files and interface/notebook.js. The existing release policy remains
mvp-android/docs/ONE_APP_UPGRADE_POLICY.md. Do not replace it.

## Product names vs technical identities

- APP 1.0 is the owner-defined Android distribution of approximately 156 MB.
  A 2026-11-19 signed candidate was recorded in
  mvp-android/docs/ROUND2_RELEASE_CANDIDATE.md as package
  org.preceptoros.app, versionCode 7, versionName 0.3.0-mvp. Its assets
  include JNI and a GGUF, but installed inferencing needs physical proof.
- APP 1.1 is the owner-defined future release with working local inference.
  The current build.gradle has default versionCode 8 and versionName
  0.3.1-mini-recovery. These values prove neither an APK nor an installed
  upgrade. The historical root RELEASE_v1.1.md refers to another era.
- org.preceptoros.mvp is a legacy applicationId, distinct from
  org.preceptoros.app even when signed by the same owner certificate.
  Never silently replace, uninstall or clear data to change ID.

## Contract and measured benefits

The read-only, stdlib mvp-android/capability_ledger.py emits four disjoint
layers and a cause for every unverified step:

| Layer | Evidence | Limit |
| --- | --- | --- |
| source | Seven checked capability categories with required files, symbols and SHA-256 | Static code is not an executed behaviour |
| apk | ZIP CRC, required GGUF/JNI/voice/panels/bridge assets, aapt2 package and apksigner owner certificate | Signed ZIP is not an installed version |
| installed | Read-only ADB dumpsys of canonical and legacy package IDs, without logging serial | Installed metadata is not certificate or turn proof |
| runtime | Defaults to NO_DATA until independently witnessed local/remote turn, TalkBack and consent tests | Never infer from model existence or connection |

The candidate APK gate enforces canonical package ID, versionCode at least
8 and the existing owner certificate. Historical v7 or legacy v6 cannot be
misreported as newly signed APP 1.1. The script never executes Android writes.

Measured prevention target: all seven source capability groups present,
mandatory assets packaged, no unknown/changed certificate accepted, no
silent downgrade, and no runtime PASS without physical evidence. Static
file tokens cannot detect all semantic regressions; the mathematical native
tests and device E2E remain separate mandatory gates.

## Reproducible use

From the isolated APP worktree:

    python3 mvp-android/capability_ledger.py --strict-source
    python3 -m unittest -v test_android_capability_ledger
    ANDROID_BUILD_TOOLS=/path/to/build-tools/36.0.0 python3 mvp-android/capability_ledger.py --apk /path/to/new.apk
    ANDROID_ADB=/path/to/adb python3 mvp-android/capability_ledger.py --serial YOUR_CONNECTED_SERIAL

Never paste a serial or full local path into a public PR. The output omits
the ADB serial, does not pull APK contents or synchronize data, and leaves
unmeasured certificate/byte identity explicitly NO_DATA. Check owner signing
configuration out-of-band; never commit APK/GGUF/JNI binaries or private
environment secrets.

## Release gates before any merge or distribution

1. Re-check main SHA, Mesa ownership and standing signatures. Run ledger
   and directed synthetic negative cases twice, then ./bin/pruebas twice.
   Retain failing receipts rather than claiming a partial suite PASS.
2. Build a fresh signed APK in an isolated worktree with an exact source
   commit. Record APK hash, size, package ID, versionCode, versionName,
   certificate and mandatory ZIP assets. Inspect JNI and GGUF presence.
3. Inspect each Android package read-only. If legacy is installed, obtain
   a separately owner-approved export/import and rollback strategy that
   preserves preferences; Android allowBackup=false makes any assumed ADB
   backup insufficient. A different applicationId is NOT an in-place update.
4. Repeat ×2 on each device: launch offline, mathematical edge cases,
   an arbitrary free-text JNI turn, six-panel navigation, TalkBack/voice/Acho
   and machine text parity, data persistence after reopen, consent/revoke
   and a signed owner-granted rack turn. No tailnet-only authorization.
5. Record host and device witness sources privately, sanitize public
   receipts, obtain exact-head human FIRMO before merge and publication.

## Outstanding measurements

- NO_DATA(APP_1_1_signed_candidate_build): Gradle configuration is not an APK.
- NO_DATA(physical_inference_a11y_rack_turn): no two-pass E2E witness in
  this ledger's source test.
- NO_DATA(installed_certificate_and_byte_identity): ADB dumpsys cannot
  establish exact signed installed APK bytes on its own.
- NO_DATA(owner_data_migration): independent consent, export/import,
  equality checks and rollback remain to be demonstrated.
- NO_DATA(private_authenticated_model_turn_E2E): signed scoped grants,
  expiry/replay/revocation and effect receipts remain future gates.

**Work discipline:** no second APP, no new LAB store, no silent capability
removal. A negative test is evidence to preserve, never a reason to erase
previous model/APP data.
