# PreceptorOS · Day D quickstart · 4 collaborators

**15-minute goal:** open PreceptorOS, keep your own data, prepare **DECLARATION.md** and **STATE.md**, and submit them for human review. Installing the APP does **not** create a live node.

## 1 · Choose your door

Go to **https://preceptoros.org/get-the-app/**. On Ubuntu Linux, obtain `install.sh` from its published release and compare its SHA-256 with the digest shown by the release before running it. Read the script first; do not pipe an unreviewed download into a shell.

```sh
bash install.sh
cd ~/preceptoros
bin/preceptoros-servicio arranca
```

Open **http://127.0.0.1:8740/app** on **that same computer**. The installer needs Python 3 and Git; it does not request sudo or install a model. Tested in an isolated **Ubuntu 24.04.5** container: installation, desktop launcher, APP HTTP 200, and `/api/cerebro` `local_gguf`. The runtime was **not** tested with a real model in that container.

On Windows: native installation is **NO_DATA(Windows_install_E2E)**; use OpenWorld + Create Companion from the browser. On Android: the **public OpenWorld APK is not the full PreceptorOS APP**. A private Android mini prototype exists but is not a public release. On iOS: native app **NO_DATA(iOS_release)**.

## 2 · Understand your own brain

Hexelion runs **only on the founder's private rack**. It is not in your download, not a fallback and not a shared cloud model. Your machine can display Chat, Documents, Lab and My node without installing a model.

Today the native local Talk adapter uses **your GGUF + a compatible llama.cpp executable**. The default candidate file is `~/.preceptoros/modelos/qwen3-4b-instruct-2507-Q4_K_M.gguf`; no model is downloaded by the installer. The mere presence of Ollama does **not** connect its API to Talk: **NO_DATA(user_Ollama_bridge_E2E)**. LAN/Tailscale and paid API connectors are likewise **NO_DATA(user_endpoint_E2E)** until explicitly tested. Keep API keys out of forms, GitHub, public declaration files and browser preferences.

`/api/cerebro` saying `local_gguf` describes the chosen **route**, not evidence that a model answered. A missing model should produce `NO_DATA`, never invented text or a silent jump to Hexelion.

## 3 · Create your Companion

In the public site, open **Create Companion**. Choose your own public slug and press **Prepare my two drafts**. Save the resulting **DECLARATION.md** and **STATE.md** on your device; inspect both for paths, passwords and personal information before sharing.

Submit a **documentation-only PR** to **https://github.com/piskyRpapalo/preceptoros-companion**, following its CONTRIBUTING guidance. If GitHub is unavailable, prepare a ZIP of the two reviewed files and give it to the Soberano for manual intake; mark **NO_DATA(pr_pending_account)** until recorded.

A generated draft is **not sent**. A PR is a request for review, **not an admitted Companion, signed execution grant, working node or live territory**. Nothing is published to OpenWorld merely because you clicked Create Companion.

## 4 · Help without sharing secrets

| What you see | What to do |
|---|---|
| `git` or `python3` missing | Install the named package with your OS package manager, then rerun `bash install.sh`. |
| `127.0.0.1:8740` unavailable | Run `cd ~/preceptoros && bin/preceptoros-servicio estado`; inspect the local log. Never kill the owner's rack processes. |
| Chat says `NO_DATA` | UI may still work. Connect a verified **personal** model later; do not put the rack's Tailscale address or someone else's key in settings. |
| No GitHub account | Keep the two local drafts and send an owner-reviewed ZIP for manual intake. |
| Public APP web route unavailable | Use **Get the app → Create Companion**; do not infer that a 404 route is live. |

**Completion receipt (one line per person):** `COMPANION_DRAFT_OK · <public_slug> · <PR URL or NO_DATA(pr_pending_account)>`. No telemetry, IP, memory contents, model prompts or credentials are required.

**What is not promised on Day D:** Windows/iOS native app, public Android APP, autonomous node deployment, remote feedback delivery, two connected AI models, automatic building admission, or a public Hexelion.
