# Node lifecycle · OWNER read contract

`GET /api/nodo/estado` is a no-store loopback OWNER read. It returns
`preceptoros.node-lifecycle/1` with `node`, `observed_at` and all ten keys in
`stages`. Every stage has `state`, `cause`, and `source`. `at` and
`receipt_ref` accompany evidence when available. Browser callers use the
current same-origin request. Proxies and cross-site visitors are refused.

My node must select the identity before the backend can correlate the
consented intake. The existing intake/export handlers save validated
receipts under the private APP home. `lifecycle_recorded` reports whether
the local copy was saved. Historical receipts absent from the APP remain
NO_DATA. A local save failure cannot undo a successful Aduana request.

For the physical ceremony, retain the exact signed plan at
`<app-home>/node-lifecycle/<node>.plan.json` with owner-only permissions.
A successful export supplies the matching cédula and its receipt. The
server rechecks both SSHSIG scopes against `allowed_signers_cedula`, plus
node, admin, plan digest, device claim and consented intake digest.
Configure `PRECEPTOROS_OWNER_REVIEW_KEY_FILE` to a private file with the
existing Aduana review credential. The credential stays on the server and
is used only for the fixed owner-review GET. The approval or revocation
ref comes from its exact D1 result.

The catalog corroborates the export receipt before the public projection
can report LIVE. The public projection does not give an exact authenticated
heartbeat receipt, so the heartbeat stage retains NO_DATA. A public AI turn
and an authorized functional building require their own sources. A
descriptive building marker is insufficient for either.

- [x] Exercise protected routing, exact receipt links, real fixture SSHSIG,
  pending intake, revocation, absence of LIVE and private value scrubbing.
- [ ] Owner ceremony and independent physical receipt from production.
