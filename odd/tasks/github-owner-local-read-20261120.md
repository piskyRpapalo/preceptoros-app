# APP-GH-READ-02 · Owner-only GitHub context in existing LAB API

**Status:** PROPOSAL / source-only · Codex GPT-6 WEB (B), private Mesa #47. **Not a second GitHub importer.** Reuses [APP #357](https://github.com/piskyRpapalo/preceptoros-app/pull/357) `github_bootstrap.propose` and its `preceptoros.github-owner-snapshot/1` input.

## What is delivered

- Owner chooses a **local** JSON snapshot from an approved workflow and keeps it at `<owner-app-home>/sources/github-owner-snapshot.json`, with the directory `0700` and file `0600` (owner-owned, no symlinks). App reading never creates that file or authenticates to GitHub.
- `github_snapshot_read.py` only checks this local file and calls the **already merged** `github_bootstrap.propose`. Public repo references are passed through existing validator; private repo **names** never leave it (count only), with explicit `NO_DATA` for unverified private access and other capabilities.
- New GET `/api/lab/github` uses existing APP `_memoria_local()` loopback, Host and same-origin protection. A remote/LAN request is denied with 403; no public web or Android native route is promised.
- Local-file mtime and `STALE` flag are **not** proof of latest GitHub HEAD. Output always remains `OWNER_SUPPLIED_UNVERIFIED`, `changed=false`; no memory writes, LoRA, model provisioning, credential handling, grants, loops, fork, clone, PR or deployment.

## What this does NOT claim

The APP Lab **visual** tab is not yet wired to this endpoint; the API is an internal source projection for the next APP owner-reviewed UI slice. No current GitHub freshness until an authenticated, consented owner connector supplies exact commit refs. No claim of the owner's private repos unless separately granted. Notebook's existing bench receipts remain authoritative for *measured* benchmarks; GitHub repo metadata is merely a source hint.

## Acceptance gates

1. `test_github_bootstrap` (already merged) + `test_github_snapshot_read` registered in **existing** `bin/pruebas`, fixing default runner omission.
2. Invalid permissions/symlink/duplicate JSON/malformed URLs/secret-like extra data fail closed.
3. Isolated live HTTP proves local opt-in `200 PROPOSED` vs spoofed Host `403`; private repo names not echoed.
4. Full APP `bin/pruebas --rapido` ×2, plus exact-head HITL before main. `NO_DATA(voice_screen_reader_E2E_not_tested)` until APP Lab renders identical state/cause for text, audio and machine.

**Next:** existing Lab/Harness component renders this snapshot's source age, proposal and NO_DATA state without adding a new tab, with separate owner approval for write-back PRs. A owns public WEB multi-user; no WEB/Cloudflare or native Android code touched.
