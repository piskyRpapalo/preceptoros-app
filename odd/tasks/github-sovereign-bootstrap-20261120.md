# APP-GH-BOOT-01 · Github owner context before AI automation

**Status:** proposed source slice, not a live GitHub connector or a running APP feature.
**Owner of this slice:** Codex GPT-6 · ChatGPT WEB orchestrator 1.
**Human authority:** each sovereign owns their GitHub, memory, hardware and signatures.
**Contract:** APP `AGENTS.md`, Companion `CONTRACT.md` and `PRECEPTOR_SWARM_PROFILE_TEMPLATE.md`, Study Carbon/HITL, ADS-STE100.

## Existing pieces — reuse, do not create a second system

- `memory_onboarding.py`: same private `memory.db`; creates only on explicit local owner consent. This slice never invokes it.
- `federado.py`: LAB-signed/hashed metadata snapshots; a device/model declaration is not an execution grant.
- `exportar_contexto.py`: deterministic scrub boundary before exporting owner memory to external AIs. No export is made here.
- Companion public templates: identity, one building, read-only declaration until owner signs.
- Public Mesa and Lab: mission source and reproducible receipts. Neither is the owner's private runtime database.
- **APP** is an owner's control plane. **WEB** is the shared public Window. **Aduana** authenticates admissions. GitHub is source and coordination, not the physical runtime database.

## Minimal adapter built in this branch

`github_bootstrap.py::propose` takes *supplied* public, bounded GitHub repository metadata (`preceptoros.github-owner-snapshot/1`). It requires exact URLs on `github.com`, an explicit owner/repo match, safe names/branches, no executable fields and <=100 rows / <=65,536 JSON bytes.

It returns an inert `preceptoros.github-bootstrap-proposal/1` object: sorted public repo references, source types and purpose **hints**; a declared-only local content hash; `NO_DATA` for authenticity, model runtime, live node, owner private grant and automations; six owner-consent-gated steps. Private repository *names and links* are not projected, only an aggregate count. An owner may suppress the whole count as well in a higher-level UI.

The adapter does **not** issue network requests, clone repositories, create memory, search RAG, copy files, start MCP tools, install a model, train LoRA, authorize A2A, post to GitHub or sign a node. The caller must authenticate any actual GitHub snapshot independently. **Source-controlled public metadata is not user authentication**, and source hash is not HITL.

Run the directed gate: `python3 -m unittest -v test_github_bootstrap`. Recorded 2026-11-20 on Beelink: **21 PASS ×2** on isolated APP origin/main `edb4b058ed` (with this proposal's new source). The current public WEB/Cloudflare/Android behavior is not covered by these tests.

## What the eventual end-to-end workflow must do

1. **Identify owner, don't impersonate:** explicitly choose GitHub user, visibility scope and a connector identity; display verified auth state separately from profile metadata. Privately admitted capabilities come only from a real, revocable owner consent.
2. **Read selected files:** only owner-selected repos and paths, starting with current README, AGENTS.md, llms.txt, existing contracts and commit hashes. Preserve provenance, licence, byte limits and `NO_DATA` for missing content; strip untrusted instructions as data.
3. **Owner selects the data boundary:** route chosen files to the existing local `memory.db` using explicit consent, limit, checksum and provenance. Never mirror founder/private repos to another user.
4. **Interpret capabilities:** inspect actual authorized MCPs, GPU/CPU, local models, storage and permissions. Record installed vs running vs tested, not a fantasy tool list. Prepared swarm personality MDs may route source articles without weakening their mandatory law.
5. **Propose first local benchmarks:** GitHub/source provenance; system inventory; two generative model prompts; private source retrieval with quotes; Acho visual/screen-reader/machine parity. Set all outcomes `NO_DATA(test_not_run)` until real hardware evidence. A proposed LoRA is only a future trained adapter, not a signing authority.
6. **Propose automations and loops:** only after owner-specific budgets, schedule, E-STOP and review scope. No automatic scheduling from a README or PR. Model memory and actual task execution remain separate services.
7. **Propose public Companion:** owner-approved declaration → private signed admission via APP/Aduana → authenticated heartbeat → WEB LIVE. Public visitors may browse without node credentials. No LIVE from a GitHub repo.

## Separate APP/model chunks — not the Acho control envelope

Native Android v7 (155,998,639 bytes) **already bundles** a 105,454,144-byte SmolLM2 GGUF and native engine. A raw GGUF shared on WhatsApp is **not** selectable by the current Android external-model picker.

Babel `proposals/blob-ticket.md` is a **proposal-only** SSHSIG/Acho envelope <=1,023 UTF-8 bytes with a **separate** <=25 MiB data plane. This is not deployed and has no proven Android model installer. File transport is a future capability, distinct from APK installation.

For a future opt-in chunk delivery: separate installable APP from external model weights only after new versionCode/signing and exact E2E proofs; publish a signed/versioned manifest with whole-file digest and each chunk's offset, byte count and SHA-256; fetch only from owner-approved source to app-private quarantine; verify every chunk, assembled model and model licence; atomic activation after validation; resumable bounded retries, rollback and transparent storage/download cost; offline and accessibility paths. Android's package manager must receive a valid final signed APK, not arbitrary `.part` files. Cloudflare Worker must not become a generic unrestricted file proxy or expose private model paths.

**Status:** `NO_DATA(chunked_APK_download_E2E_not_built)`, `NO_DATA(model_importer_E2E_not_built)`, `NO_DATA(private_GitHub_owner_grant_not_wired)`, `NO_DATA(automations_not_authorized)`, `NO_DATA(2nd_node_LIVE_not_verified)`.

## Joint responsibility of the two WEB preceptors

This slice claims only `github_bootstrap.py`, `test_github_bootstrap.py` and this document, in an isolated worktree. The second WEB preceptor should own the WEB Cloudflare/public presence/admission integration or indicate a narrower active claim in Mesa #50. Review prior existing APP/UI/Android worktree claims before proposing the next slice. Pi/OpenCode/Juni may act only under their real scopes; no fictitious swarm, persistent timer or tool permissions.

**Acceptance for a future real APP integration:** authenticated GitHub read adapter; private consent receipt; local SQLite memory persists on the owner's device; offline re-open; at least two independent repositories; Android/Windows owner parity; zero undeclared egress; tests ×2 and human exact-head FIRMO. Current adapter is *source-only*, not those end-to-end outcomes.
