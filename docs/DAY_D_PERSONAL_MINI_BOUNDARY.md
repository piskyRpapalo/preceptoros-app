# Day D · personal mini security boundary

**Scope:** one PreceptorOS APP, two operator-controlled profiles. The downloadable
personal MVP has a deterministic mini door. It is **not a large language
model**, not the founder's private rack brain, and not a model deployment.

## What is installed versus what is available

- **Personal MVP (default):** local UI, local-first memory, closed deterministic
  routes, building drafts. Chat generation is available only if **the owner**
  explicitly provides and verifies a compatible runtime and model.
- **No model:** the request fails as `NO_DATA` with a reason. The deterministic
  mini can still navigate and prepare a plan. A canned greeting or local
  navigation receipt is not a model answer.
- **Private rack profile:** an explicit operator preference *and* an observed
  local installation marker *and* a declared private station mode are required
  before the client displays that profile. The installation marker is a
  pseudonym, **not authentication** and never a permission grant. The
  server alone authorizes access.
- **Neither LoRA nor GGUF weights are included as a general desktop promise.**
  Device-specific native inference is a separate measurable capability.
- **Feedback and RAG belong to each node owner.** A visitor does not acquire
  LAN, model, memory, or tool grants by submitting a message. The founder's
  rack is never the default feedback destination.

## Entrypoints and measured behavior

| Entry / boundary | Existing source | Measured / limitation |
|---|---|---|
| Local model selection | `bin/preceptoros-pwa::_talk_mode` | Empty explicit station endpoint selects `local_gguf`. Configured station selects the private mode. |
| Personal profile | `interface/app.js`, `interface/conversacion.js` | Real Chrome test: personal profile submits zero POSTs to private chat and zero GETs/POSTs to the private shared thread even when the server advertises private mode. |
| Missing model | `mvp-android/offline_mini.js`, `test_talk_local.py` | Unverified inference yields `NO_DATA`; no synthetic model answer is accepted as measured. |
| Closed intent envelope | `orquestador.py` | Four INTENTS; unknown, duplicate JSON keys and UTF-8 envelopes >=1024 bytes rejected. `UPDATE_RAG` from chat has no write adapter. |
| Mobile offline mini | `mvp-android/app/src/main/AndroidManifest.xml` | This APK source declares no `INTERNET` permission. Distribution to external devices and runtime inference are separate acceptance gates. |
| Fresh Linux install | `tests/test_distribution_smoke.py` | Temporary HOME, isolated loopback runtime, local memory retained across reinstall. Test does not intercept every network syscall on an external device. |
| Feedback journal | Junie's unmerged `feedback_link.py` | Explicit journal path and signed owner policy; no configured relay. Remote authenticated delivery: `NO_DATA`. |

**Synthetic web proof:** `NODE_PATH=<local-playwright-node_modules> node
tests/dayd_personal_no_rack.browser.cjs` on the development host. The test
starts a separate loopback-only fake server. Its four cases are:

1. Fresh personal profile + server advertises private mode: **0** private
   chat POSTs; no shared thread traffic; editable unsent message + visible
   `NO_DATA(personal_profile_private_route_denied)`.
2. Fresh personal profile + local mode: one local model-door attempt, with the
   fake backend refusing and no invented response.
3. Private preference, missing identity: downgraded to personal mode,
   **0** private chat POSTs.
4. Private preference, real-shape local identity and declared private mode:
   private route remains selectable. **This is not a server authorization test.**

The same result is projected as visible status text and machine-readable
`data-state` / `data-acho`. No audio- or screen-reader-device end-to-end
result is claimed.

## Known limitations and stop rules

- **B2 block:** the existing JavaScript mini trims input to 600 characters
  before intent recognition. An overlong prefixed navigation request can
  therefore still trigger local navigation. The owner of the mini JS file must
  reject oversized raw input *before* truncation; do not label the B2 mini
  oversize gate PASS until a negative test turns green.
- Client routing checks **do not** replace server-side authentication or
  permission checks. The current private profile marker is not a secret.
- Actual external-device network capture, model deployment to a collaborator,
  authenticated feedback relay, remote server authority and user-specific
  RAG writing remain `NO_DATA` until separately exercised.
- Do not add a second APP, silent model fallback, a central feedback inbox,
  an unattended merge or new remote privileges to pass a demo.

## Acceptance and handoff

Run `python3 -B -m unittest -q test_dayd_personal_no_rack_contract`,
the real Chrome proof above, and the canonical APP `./bin/pruebas --rapido`.
Run each twice before requesting review. The owner APP must reconcile service
worker and asset version changes with the other Day D worktree **before**
shipping to any cached browser. Do not deploy this isolated branch directly.
