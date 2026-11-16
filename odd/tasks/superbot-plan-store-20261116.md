# Superbot · private content-addressed plan store

Status: BUILD / local review. Contract source: APP #310 (`preceptoros.plan/1`); read consumer: APP #312 (`preceptoros.plan-flow/1`).

## Scope

`plan_store.py` validates and stores UTF-8 JSON plans under the existing `casa.raiz()/plans` private home. The only accepted document fields are `schema`, `title`, and `text`. Canonical JSON uses sorted keys, compact separators, UTF-8, and rejects duplicate keys/non-finite values. SHA-256 is over those canonical bytes. Files are immutable by content address, owner-only (directory 0700, blob 0600), written atomically without replacing an existing blob, and re-hashed on read.

The APP routes are local-only: `POST /api/plan`, `GET /api/plan/<sha256>`, and `GET /api/plan/flow`. POST records only `PLAN_REF <sha> <bytes>` in the existing `orquesta` channel, as a `DECLARADO` event from `superbot-plan-store`; it does not impersonate the Soberano. `plan-flow/1` exposes the newest valid reference and an empty proposal with `proposal_not_built`. No plan text is copied to the journal/channel, and no plan write or read creates a grant.

## Limits

Storage is not proposal, authentication, authorization, dispatch, execution, or a journal transition. A local loopback/same-origin check limits browser access; it is not proof of a human identity against a local process able to forge HTTP headers. The source event is explicitly DECLARADO. No CLI execution or APP panel integration was exercised here.

## Reproduction

`python3 -B -m unittest -q test_plan_store` — five deterministic tests, including a 210,000-character plan, byte digest, deduplication, tampering, duplicate JSON keys, and private channel reference only.
