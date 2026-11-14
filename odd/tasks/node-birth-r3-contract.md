# NODE-BIRTH R3 · request/receipt correlation contract

2026-11-14. Read depth 2. Mission: private Mesa #3, ROUND 7;
CLAIM 6880827144. This document is a technical contract, not a new mission.
Base APP: `3581518b3dfa43a4db42bdb234b9f5f6432c1f2c`.
Preserved Round6 lab: `ee681b57aea39ba0512881b7bc06d206e90439f7`.

## Recovery and observed defect

Recovered unapplied proposal SHA256:
`38917adb1eb1e8d82b3f10a8d1e97762a17f6ecd91df79b6b92293d86cff5bbd`.
Current exporter and its original tests match the Round6 production source;
only AGENTS culture documentation changed on main. Previous green totals are
historical, not validation of this new branch. No conflicting scope edits were
found across 96 local worktrees or visible Mesa claims before building.

The unchanged Round6 strict suite reproduces five failures on the new base.
R3: a locally verified request accepts another credential's actual pending
Worker receipt. The preflight also preserved an injected verified variant.
Both are message-correlation failures, not demonstrated cryptographic bypasses.

The recovered proposal rejects ordinary foreign receipts but observes mutable
caller data after transport. A synthetic callback models caller mutation during
I/O: bytes sent contain A, caller dictionary becomes B, reply belongs to B;
recovered proposal accepts pending. The correction compares with a snapshot
parsed from the exact serialized bytes before invoking transport. It also
compares canonical JSON rather than Python equality (True aliases integer 1).
This is R3 hardening; no new admission service, signature or territorial rule.

## Correction

Scope: `nodo_export.py`, `test_nodo_export.py`, this contract.
Require a receipt with existing `preceptoros.recibo-cedula/1` schema, exact
credential/node/admin/plan identifiers, the entire sent credential in the
returned package, consistent state/cause/count and recomputed receipt hash.
Count is strictly integer 1. JSON canonicalization ignores key order, preserves
JSON types and uses ASCII escaping compatible with existing Worker hashing.

Mismatch, missing receipt or damaged hash yields:
`{"estado":"bloqueado","codigo":"recibo_no_corresponde","http":502}`.
Existing package/state/signature gate failures retain their earlier codes.
Pending stays pending; verified stays documentary verification. Existing success
shape is unchanged: estado/codigo/causa/recibidos, no authority or territorial grant.
An identical replay returns the same document state; no authorization is minted.
No arbitrary receipt TTL is invented in this change.

Three different questions remain separate:
- SSH verification authenticates the credential against a configured local key.
- Receipt hash and correlation check integrity and correspondence to sent bytes.
- Admission, remote execution and territorial authority need separate evidence.
A caller can forge a self-consistent unkeyed hash; correlation is not a new
receipt-signature guarantee. System Check CONNECTED remains NOT_AUTHORIZED.

## Validation and limits

Directed yardstick: `python3 -B -m unittest test_nodo_export -v`, twice.
Reuse the exact Round6 lab against this checkout with pinned Aduana source
`5f58d76677149518db72866504fa55c2a8436fe0` and System Check
`34f6b7726f09fccc936be9e4608d87ab635c58c4`; do not copy or edit its tests.
Run integration14 and strict R1–R5 separately, twice: expected R3 green,
R1/R2/R4/R5 still RED. Run complete `./bin/pruebas` twice and report skips
and sabotage counts separately. A removed-binding mutation must fail a targeted
foreign-receipt test; do not hide strict RED with expectedFailure.

External receipt retains before/after logs, recovered-proposal counterexample,
comparative tests, exact-head bundle/patch, negative matrix and draft text.
No live network, key generation, public admission, WEB/Worker edits, merge or
deploy. The old APP-CLI-01, System Check and Round6 heads/packages remain intact.
Real admission, signer-authenticated receipt, UI, external installation and
public territory remain NO_DATA(not_measured_in_this_increment).
Mesa #42's human publication grant is limited to two older refs; this branch
has NO_DATA(authorized_new_ref_transport). Receiver ACK is not inferred.
Next proposal: owner-reviewed R4 public-field preview/selection before export,
without silently redacting an already signed credential.
