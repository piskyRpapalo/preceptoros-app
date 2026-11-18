# APP → WEB · FOUR COLLABORATORS, ONE MINI · 19 Nov 2026

**Commission:** Mesa #3 #6988827047 · Signed objective: one four-zone public MINI for four first-time nontechnical collaborators.
**Owner of source package:** Codex GPT-6 APP. **WEB owns public deployment and `/app` routing.**
**Base:** APP #344 HEAD `f0e4b33c241aeacebac128b791772502eb4410c3` (open, separately signed before merge).

## Measured architecture

The public distributable is a **generated static projection of the existing APP**, not an independently maintained second application or model router. Python stdlib generator `bin/package_public_mini.py` extracts the canonical Documents markup and the canonical node proposal section from `interface/app.html`. It reuses `mvp-android/offline_mini.js` unchanged, `interface/documents.js`, `owner_model_slots.js`, `companion_onboarding.js`, `node_registration.js`, and one deterministic `mini_project_guide.js`. Four tabs only: Talk, Documents, Lab, My node. The private APP `app.js` and backend services are intentionally **absent**.

Project guide supports Create project → Describe purpose → Add documents → Review project → Configure AI → My node. The owner's project and documents persist in **their browser localStorage (not encrypted)** and export in an explicit JSON download. Uploaded documents are local only; no endpoint receives them. LocalStorage can be evicted: owner should export backups.

Templates, editable and not trained models:
- European AI & Software Law: [AI Act OJ, 2024-07-12](https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng); [Digital Services Act OJ, 2022-10-27](https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng).
- Digital Fairness Observatory: [Commission fitness check SWD(2024)245, 2024-10-03](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52024SC0245). `NO_DATA(LAB_DFA_benchmark_receipts_not_bundled)`.

These are primary **links**, not fetched or indexed text. No legal advice or generative capability is implied.

Model states: `DETERMINISTIC_ONLY` initially; `MODEL_CONFIGURED` for a saved owner preference, still **no verified connection**; `MODEL_VERIFIED` is exclusively an observed, authorized owner-runtime answer, not available by default in the current static browser. Current public MINI needs no GGUF/Ollama/rack/CLI/keys. Saved preferences do not reveal URLs or grant network access.

My node's `Sign deployment` remains DRAFT_ONLY/NO_DATA without a consented native transport and BRAIN preliminary inbox. No unsigned `/api/v1/cedulas` POST, private-rack fallback, auto-signing, heartbeat or LIVE. APP #344 retained; BRAIN independent preliminary endpoint `/api/v1/deployment-requests` is source-only/unpublished at time of build. No live receipt is claimed.

## WEB integration (owner WEB)

1. Checkout the APP branch/PR head and run `python3 bin/package_public_mini.py`; inspect `dist/public-mini-app/app/package-manifest.json` and `dist/public-mini-app.sha256`.
2. Compare `sha256sum dist/public-mini-app.zip` to manifest receipt and verify each file hash; do not re-sign or silently change the bundle.
3. Copy the directory contents `dist/public-mini-app/app/` to WEB static `public/app/`, retaining same origin/paths. Configure `/app` → `/app/` HTTP 308; `/get-the-app/` should link to `/app/`, not falsely label a native Android download. Public `/app/` must use HTTPS so its service worker is installable.
4. Do not put private APP assets or API endpoints under `/app/`. The package service worker caches **same-origin static files only**, never /api or remote model calls. Preserve existing WEB protection and human dispatch.
5. Run `node tests/public_mini_browser.mjs 360` and `420` against the built local static package and the source tests. After human WEB deploy, repeat equivalent tests on a real **external** phone and compare served SW/source bytes.
6. WEB must report `NO_DATA(public_pwa_install_external)` until a real external-phone install or offline reopen is witnessed. APP evidence is loopback Chrome headless mobile 360/420 only. Native S110 APK has mismatched installed certificate and is **not** part of the release.

## Safety/evidence

Unit: `node --test tests/public_mini_project_cases.cjs` and `python3 -m unittest -q test_public_mini_package`. Full: `./bin/pruebas --rapido` ×2. Browser: ephemeral headless Chrome profile, local HTTP server, mobile 360 and 420, offline reopening and storage persistence. Browser observed no `/api/` requests; all four zones present; requests to native preliminary bridge fail closed with a caused `NO_DATA`.

This is a **reproducible build artifact, not a signed public release**. No self-merge or deployment; Sovereign exact-head FIRMO and WEB human dispatch remain gates. User projects and documents never leave their device by default.
