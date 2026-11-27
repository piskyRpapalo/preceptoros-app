# Local conversation cursor · ACHO-CHAT-BACKEND-01

## Explore

Talk uses the orquesta thread of the existing append-only eventos.db.
The legacy local GET /api/conversacion uses a recent 200-row window and a
40-row projection. It is not a lossless reconnect API. An addressed POST
acknowledges a thread append, not a process receipt. External destinations
have no authorized transport. Keep legacy consumers unchanged.

## Implement

Add the internal canales.lee_pagina primitive: ordered first page after the
last delivered n, explicit scope, 1–20 rows, 1024–8192 UTF-8 JSON bytes,
source, observed_at, complete, next_cursor and no authority. Oversize and
unclassifiable rows stop advancement with NO_DATA; no truncated message.
An empty page from an existing ledger means no newer matching messages.
No HTTP route, MCP registration, new database, or access grant is added.

## R7 local extension

- conversation_id is an optional scope stored in the existing message
  maquina metadata on orquesta. Scoped reads include only exact matching IDs;
  legacy/unscoped events do not leak into a scoped conversation. The old
  unscoped reader remains backward-compatible.
- ancla is reused as the existing canal_event/1 SHA-256 reference
  (64 lowercase hex characters). The cursor returns the reference only, never
  copies the referenced payload. The canonical event frame remains <=1024
  UTF-8 bytes.
- ledger_id is an opaque local fingerprint of the eventos.db file identity.
  It stays stable across appends and rejects a replaced ledger when the caller
  supplies expected_ledger_id. Persist the tuple
  {canal, conversation_id, ledger_id, cursor} per client. The cursor is the
  last delivered event n, not the newest global n and not an auth token.
- The 3-reader fixture uses labels beelink, tank3 and s110 as synthetic clients
  only. One append-only writer produces 100 messages; each reader disconnects
  and resumes with its own cursor. Tests require 100/100 in order, without
  loss or duplicates, and print local p50/p95 cursor latency. This is fixture
  evidence, not physical-device evidence.

## Check

    python3 -m unittest test_chat_cursor
    python3 -m unittest discover -p "test_*.py"

## Not implemented / gates

Next integration (not implemented): CAUDAL maps an authenticated principal
and effective, revocable read grant to an allowed scope and a bound cursor
including ledger identity. A separate send grant must bind actor, recipient,
operation ID and payload; reuse existing channel idempotency and grant
journal; deny conflicting retries, revoked or expired grants; never call
the sovereign write path for agents. Distinguish stored, process ACK and
result. Reuse turnos_hexelion and Acho projections; do not expose arbitrary
or historical private text. Tailscale reachability alone is not authority.

Physical Tank 3/S110 synchronization, network latency, authenticated remote
identity, visual/audio E2E parity, deployment and production service use
remain NO_DATA until their separate transport, authorization and evidence
gates are satisfied. No deployment or merge is authorized by this local
cursor change.
