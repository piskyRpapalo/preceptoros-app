# Superbot F1 · agent identity and task grant

Status: **built as a pure APP contract; no authorization endpoint or dispatcher is connected.**

## Existing sources reused

- APP `cuenta_cangrejo.py`: linked account verification, revocation/expiry checks, SSHSIG message verification, and the existing host `allowed_signers` trust anchor.
- Companion #31, `preceptoros.agent-card/1`: card schema, 1,023-byte limit, closed request vocabulary, and `authority: none`.
- APP #310, `odd/tasks/superbot-e2e-contract-20261116.md`: task hash binding and the PROPOSED → AUTHORIZED → DISPATCHED → RUNNING → RESULT boundary.

## Implemented contract

`agentes_contrato.py` parses card/grant bytes strictly (UTF-8, duplicate-key rejection, finite JSON, closed fields) and validates the Companion card shape. A valid card returns `DECLARED`, never authenticated or authorized.

Authentication reuses the existing Sovereign-linked crab account and `cuenta_cangrejo` Ed25519 SSHSIG verification. The agent public key is resolved only from the host-provided key directory and must match the key declared by the card. A card's registry path is not a trust anchor. Missing host signer/key files return `NO_DATA`; fixture cards cannot authenticate for runtime.

The grant shape `preceptoros.agent-grant/1` is scoped to one agent, exact card bytes, authenticated key, task bytes, one requested capability, one device, accepted-conditions bytes, validity interval, and nonce. The Sovereign signature is verified with the same existing host `allowed_signers` trust root used for the account chain and a dedicated `preceptoros-agent-grant` namespace. No key or signature is created by production code. The real host trust file's acceptance of this namespace has not been inspected or changed. Revocation and consumed-grant snapshots are required; unknown snapshots fail closed.

The strongest positive verdict is `ELIGIBLE_FOR_ATOMIC_CLAIM`. This module does not create grants, persist revocations, consume nonces, claim the journal, dispatch a CLI, or mark a task AUTHORIZED. A host adapter must perform atomic single-use journal claiming before dispatch. This avoids presenting a check-then-act result as authorization.

## Tests and limits

`test_agentes_contrato.py` uses throwaway Ed25519 keys and temporary trust files. It tests cryptographic verification plumbing and bindings only; it does not represent a real Sovereign grant, registered production agent, or execution. The positive result is a synthetic contract fixture. The suite is registered in the canonical `bin/pruebas` list; existing `test_superficie.py` enforces suite registration.

Required live evidence still absent:

- `NO_DATA(authentication_key_registry_binding)`: no deployed APP source currently binds Babel's real card registry keys to host-linked accounts.
- `NO_DATA(signed_grant_issuer_and_storage)`: no APP producer, private grant store, revocation writer, or nonce-consumption transaction is connected.
- `NO_DATA(superbot_dispatch_journal_adapter)`: no APP path performs the atomic claim and dispatch.
- `NO_DATA(real_cli_superbot_e2e)`: no real CLI received and completed a signed Superbot task through APP.

The test runner registration and the plan-flow API are separate next increments; no panel, service worker, memory, or conversation route was changed here.
