# PreceptorOS · Day D · Make one building draft

**Lisbon Table success (19 November 2026):** open the public world, prepare a local building draft, then **open docs-only Companion and Lab HITL PRs in the room** with human ownership and review. If GitHub access is missing, save drafts and report NO_DATA(GitHub_account_or_PR_not_created). No model or LIVE node is required. See [the one-page Lisbon operator path](LISBON_TABLE_APP_ONEPAGE_20261119.md).

## 1 · In the room: build first

1. Open **https://preceptoros.org/get-the-app/** and enter **OpenWorld**. The world is a map and a tutorial, not the founder's private backend.
2. Use **Create your building** when the public WEB door offers it. Enter the building name and what it will do. Choose **Create my building draft**, then **Download my draft**.
3. Save the `building-draft-<your-name>.md` file locally. The receipt must say **DRAFT_ONLY**. It means one provisional building idea, **not** a reserved identity, admitted Companion, remote deployment, signature, or OpenWorld publication.
4. If the public building button is absent, record **NO_DATA(public_building_draft_not_available)**. Do not pretend that a public page or a personal APP URL returned HTTP 200 when it did not.

**For someone with Ubuntu APP installed:** open **My node → Create your building** (above the advanced node identity form). The same local draft can be prepared there. The browser file is not sent anywhere.

**Room devices:** Windows uses the public browser/PWA; **NO_DATA(Windows_native_install_E2E)**. Android uses OpenWorld PWA or its public APK; **that APK is not the complete personal APP**. The personal Android mini build is a private prototype, not a public release. Apple devices can open the public website; native iOS delivery is **NO_DATA(iOS_release)**.

## 2 · At home: your ship and your brain

On **Ubuntu Linux**, get the published `install.sh` and its SHA-256 from the [v1.3 release](https://github.com/piskyRpapalo/preceptoros-app/releases/tag/v1.3). Verify the download digest with `sha256sum install.sh` against GitHub release metadata. The measured v1.3 digest is `2bd8666979a67ea1ec8b01a01aac240acfc2cef6165b93e558d0b836d3df6e74`. Review the script before executing it. Then:

```sh
bash install.sh
cd ~/preceptoros
bin/preceptoros-servicio arranca
```

Open **http://127.0.0.1:8740/app** on the **same computer**. The installer needs Python 3 and Git; it does not install models or require sudo. Its published `v1.3` asset was SHA-256-verified and tested in a fresh Ubuntu 24.04.5 container: install, desktop launcher and APP HTTP 200 **PASS**; `/api/cerebro.talk_mode=local_gguf`; model inference **NO_DATA(no_GGUF_installed)**.

Hexelion runs **only on the founder's private rack**. It is not bundled with PreceptorOS or available as an implicit fallback. Your personal APP starts in `personal_mvp`. You bring **your own model**.

Current native Talk can use **your GGUF file with compatible llama.cpp**. Installing Ollama alone does not connect its API to Talk: **NO_DATA(user_Ollama_bridge_E2E)**. LAN/Tailscale and paid API backends also remain **NO_DATA(user_endpoint_E2E)** until independently verified. The `v1.3` installer release has older, misleading Ollama help text; do not run an unreviewed `curl | sh` from it. The corrected copy is in later source code; a new release digest is required for a corrected installer download.

## 3 · At the table: Companion HITL proposals; at home: model and feedback

**In the room (Meta 1),** prepare **DECLARATION.md** and **STATE.md** and, if GitHub is available, open a docs-only HITL PR in [preceptoros-companion](https://github.com/piskyRpapalo/preceptoros-companion). Likewise, a Lab PR may contain experiments/<slug>/README.md with observed measurements or NO_DATA(baseline_not_measured). A PR is a **review request**, not an admitted or LIVE node; the Sovereign retains signing decisions. **At home (Meta 2)**, connect your own local model and investigate actual node operation. Do not claim the rack model is a collaborator service.

A node owner's private model, memory and keys remain theirs. **Feedback content belongs on that owner's hardware**, via a future owner-approved pull/export channel; no intermediary inbox on the founder's Beelink. **NO_DATA(feedback_remote_delivery_E2E)** until tested. Human signatures govern real admission, node activation and permissions.

## If the room demo goes wrong

| Symptom | Accurate next step |
|---|---|
| No Create your building button on public WEB | Mark `NO_DATA(public_building_draft_not_available)`. Continue the OpenWorld tour; WEB owner must publish the door. |
| APP asks for a model or says `NO_DATA` | The building draft requires no model. Use **My node**; connect a personal model later at home. |
| `git` or `python3` missing on Ubuntu | Install with the OS package manager; rerun the reviewed installer. |
| `127.0.0.1:8740` unavailable | Run `cd ~/preceptoros && bin/preceptoros-servicio estado`. Do not stop or modify the founder's rack services. |
| Download was interrupted | Regenerate locally; no public owner identity was reserved. |

**Simple room receipt:** `ROOM_META1 · companion_pr=<URL|NO_DATA(cause)> · lab_pr=<URL|NO_DATA(cause)> · building=DRAFT_ONLY|NO_DATA(cause) · owner_review=pending`.

**Not promised in the room:** Windows/iOS full native APP, public Android mini APP, four live nodes, Companion PR merges, automatic building admission, remote feedback delivery, or free access to Hexelion.
