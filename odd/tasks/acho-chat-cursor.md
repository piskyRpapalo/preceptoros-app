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
Cursor is local to one scope and one ledger; it is not an external token.
Actors in the ledger are declarations, not authenticated principals.

## Check
python3 -m unittest test_chat_cursor
python3 -m unittest discover -p "test_*.py"

Next integration (not implemented): CAUDAL maps an authenticated principal
and effective, revocable read grant to an allowed scope and a bound cursor
including ledger identity. A separate send grant must bind actor, recipient,
operation ID and payload; reuse existing channel idempotency and grant
journal; deny conflicting retries, revoked or expired grants; never call
the sovereign write path for agents. Distinguish stored, process ACK and
result. Reuse turnos_hexelion and Acho projections; do not expose arbitrary
or historical private text. Tailscale reachability alone is not authority.
Measure authorized local/remote reconnect, reply, revocation and physical
APP parity with synthetic messages before integration. No deployment.
