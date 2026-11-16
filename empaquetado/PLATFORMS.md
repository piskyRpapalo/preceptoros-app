# PreceptorOS · platforms (APP-MESA-06)

One APP, one sovereign identity, one OpenWorld building per person. The APP is the **console**. It becomes an
**execution node** too when the device has the resources. The model may run on another, authorized computer.
Nothing here adds a second APP, router, building system or Harness. Every cell names its evidence. A cell with
no evidence is `NO_DATA` with its cause.

Read on 2026-11-16. Words: **VERIFIED** (checked by tool), **PASS** (E2E step ran and passed), **OBSERVED** (seen
running), **DECLARED** (written, never run), **NO_DATA** (no evidence).

## Capability matrix

| Capability | Android | Ubuntu | Windows | Any browser |
|---|---|---|---|---|
| Download integrity | APK signer VERIFIED (see Android) | install.sh = GitHub release digest, PASS ×2 | install.ps1 digest published; run NO_DATA | — |
| Install | OpenWorld APK: signed, assetlinks match (VERIFIED). APP: PWA/WebAPK of a node (OBSERVED on one phone via tunnel) | PASS ×2 (Ubuntu 24.04 container, no root) | DECLARED · NO_DATA pending external test | PWA install where the browser offers it |
| Launcher / app window | WebAPK icon (OBSERVED) | .desktop validates + launcher starts the app: PASS ×2; opening a window (xdg-open, needs a display) NO_DATA | install.ps1 creates no shortcut: NO_DATA | standalone window when installed |
| Console: talk to Hexelion | through a node's door over a tunnel (OBSERVED) | station door answers honestly with no model: `NO_DATA:memory_index_unavailable` PASS ×2 | NO_DATA | — |
| Console: shared thread (rack CLIs) | via node | DELIVERED_TO_THREAD + read back: PASS ×2 | NO_DATA | — |
| Model discovery | via node | `/api/cerebro` READ: PASS ×2 | NO_DATA | — |
| Local inference | NO_DATA (no local model runtime on Android) | NO_DATA in the container (no model); OBSERVED on the rack node (see Models) | NO_DATA | never |
| Update | APK: needs a higher versionCode signed with the same key (none newer than 2 exists) | re-run installer = `git pull --ff-only`: fast-forward PASS ×2, data hash unchanged PASS ×2, rewritten history refused PASS ×2 | same mechanism, NO_DATA | PWA: service worker swap, data kept (APP #307 walk) |
| Signed update | APK signature (yes) | NO_DATA: commits are not signed; integrity = HTTPS + fast-forward only | NO_DATA | — |
| Data kept | Android app data untouched by an APK update with the same key (platform rule; not exercised) | `~/.preceptoros` hash unchanged across update and uninstall: PASS ×2 | NO_DATA | — |
| Uninstall without losing data | Android system uninstall removes app data: say so before | `empaquetado/uninstall.sh`: removes menu, launcher, icon, clean clone; keeps data; refuses a tree with your changes: PASS ×2 | `empaquetado/uninstall.ps1` DECLARED, parses (pwsh), NO_DATA | — |
| Node identity | via node | `/api/nodo/identity` reads `NO_DATA:identidad_no_provisionada` before provisioning (honest) | NO_DATA | — |
| Building in OpenWorld | — | `node_building.py` declares a building to Aduana `/api/v1/edificios` (existing; not exercised here) | NO_DATA | visitors see buildings |

## Android: what the published APK is

Audited 2026-11-16 with apksigner and aapt2 (build-tools 36.1.0):

- File `PreceptorOS-android-1.0.1.apk`, 1,340,742 B, sha256 `8db3176a20ed973dab1f28642972bb97ab1ccd70ddbc7cf95f7a44affc7c4d8b`.
- Package `org.preceptoros.app`, versionCode 2, versionName empty, targetSdk 36.
- Signed v1+v2+v3, one signer `CN=PreceptorOS, O=PreceptorOS`, RSA 2048. Cert SHA-256 `16:76:1A:1E:…:4C:01:0F`. It equals the fingerprint in `https://preceptoros.org/.well-known/assetlinks.json` (VERIFIED).
- It is a **Trusted Web Activity**. Launch URL `https://preceptoros.org/openworld/`, host `preceptoros.org`. It holds no permissions beyond the TWA receiver one, no model and no local server.

**It is the OpenWorld wrapper, not the Hexelion APP.** The APP on a phone today is a Chrome WebAPK of a node's loopback origin, reached through a tunnel (how TANK 3 runs it). That WebAPK has a Chrome-minted package, distinct from `org.preceptoros.app`, so neither replaces the other.

**Decision for the Sovereign:** shipping the APP as an APK under `org.preceptoros.app` would replace the OpenWorld wrapper on every phone that has it. A new package id means a new install, not an update. Until decided, the website's Android choice offers the OpenWorld APK (as what it is) plus "use your node from the phone's browser".

## Models: what each word means

| Word | Evidence that earns it | This node today |
|---|---|---|
| available | the runtime lists it (`ollama /api/tags`, `/api/cerebro` `disponible`) | 12+ Ollama models; the APP base gguf file present (OBSERVED) |
| connected | the APP's door reached the runtime in this reading | NO_DATA: the APP has no door to Ollama; Hexelion's station has its own |
| running | the runtime says it is loaded (`ollama /api/ps`) | none loaded at reading time (OBSERVED) |
| no answer | a request timed out or the runtime is down | Aduana says `nodo_dormido` when the classroom node is unreachable |
| not compatible | the device lacks the runtime or memory | phones: no local runtime (NO_DATA, not tested) |

OneXStation and other nodes: no source in the APP lists them. NO_DATA. Probing them would mean writing private addresses here; not done.

## Building ↔ model: what exists and what is missing

Exists (reused, not rebuilt):
- `node_building.py`: node identity `preceptoros.pwa-node-identity/1`, building declaration `preceptoros.edificio-declaracion/1` to Aduana `/api/v1/edificios` with the node's heartbeat key, signed receipt.
- `nodo_app.py` + Aduana `/api/v1/cedulas`: the node card `preceptoros.cedula-nodo/1`, devices with public keys and states `solicitado / linkeado / revocado` (revocation exists).
- Companion `AGENT_CARD.md` (#31): a card declares and never grants; grants are signed and private.
- OpenWorld `classroom_chat.js` → Aduana `/api/v1/chat`. Visitors talk to Hexelion through the classroom, with per-visit and per-network limits. The tunnel is never shown.

Missing (proposed in Mesa #47, owner: Codex/Aduana, not built here):
- `/api/v1/chat` routes to **one** node (Worker env `AULA_URL`, `AULA_MODEL`). A building cannot yet route visitors to *its owner's* model. Proposal: the building declaration names a capability `talk.visitors`. A grant signed by the owner binds building → node door. Aduana routes by building id and refuses when the grant is absent, revoked or expired. Revoking the grant disconnects the model and leaves the building.
- E2E "install → link remote model → authorize → activate building → visitor talks → reply → revoke": install is PASS on Ubuntu; link, authorize, route and revoke are NO_DATA until that piece exists.

## Files

- `empaquetado/install.sh` (existing, v1.3 published), `empaquetado/uninstall.sh` (new, tested)
- `empaquetado/install.ps1` (existing), `empaquetado/uninstall.ps1` and `empaquetado/windows/` (new, untested)
- `tests/ubuntu_e2e/run.sh` + `inside.sh`: the container E2E (manual, needs docker and network)
