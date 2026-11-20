# MINI-RECOVER-01 · Consented recovery of an existing Mini

## Objective
Restore the owner's earlier `preceptoros.mini-project-export/1` as local project and documents in the existing My node and Lab surfaces. Never treat an export filename, content digest, or owner-selected JSON as node identity.

## Scope and acceptance
- [x] Reuse the existing Mini validator and export schema; only `interface/mini_recovery.js` imports.
- [x] Require explicit file selection or paste, preview, and local consent; reject foreign fields, tampered sources, duplicated or conflicting content.
- [x] Restore allowed content to local storage with bounded rollback and offline persistence.
- [x] Surface `UNVERIFIED_LOCAL` and `NO_DATA(no_signed_owner_proof)` in readable and machine-facing My node/Lab states; no grants or network request.
- [x] Wire Android system-owned JSON picker without filesystem scan or broad storage permission.
- [ ] Physical Android import/restart with an independently consenting owner, including speech reader check: `NO_DATA(physical_owner_test_pending)`.
- [ ] Signed cédula and native heartbeat: out of scope until separately verified and authorized.

## Evidence and boundaries
Source: `AGENTS.md` and Companion Preceptor Contract (§1/§7/§8), Study `02-legislation.md`; apply exact-head FIRMO before merge, not before building.
One original implementation was preserved in a separate worktree and was not registered. Synthetic JS/Python cases and Chrome package checks are distinct from physical Android. Browser-local SHA-256 labels content, not an authenticated owner. No new identity authority, database migration, service, model requirement or public deployment is introduced.

## Independent review
Faro/C to judge the exact PR HEAD, synthetic forgery/revocation paths, browser 360/420 and CI. `NO_DATA(approved_admission_and_public_E2E_not_measured)` until external evidence exists.
