# HEX-NODE3 · three identities, one colony (APP)

Owner: Claude Code CLI (APP identity, lifecycle, federation). Mission: private Mesa #51, HEX-NODE3-CLAUDE-01/02.
Base APP `090ef4e` (#410). Aduana `origin/main` `4a99293` (#41). This is a contract and a test, not a node birth.

## Five namespaces, measured

| Namespace | Shape | Source | Proves |
|---|---|---|---|
| Public heartbeat alias | `^[a-z0-9][a-z0-9._-]{0,63}$` | Aduana `PRECEPTOROS_HEARTBEAT_NODES` + `_KEY_HASHES` | connection + state emission |
| Cédula admission ID | `^nodo\.[0-9]{1,6}\.[a-z0-9][a-z0-9-]{0,30}$` | Aduana `/api/v1/cedulas`, scoped plan, D1 `deployment_requests` APPROVED | authorized registration |
| APP local identity | one `node_id` in `<casa>/node-identity.json` | `POST /api/nodo/identity` | which node this install is |
| Device registry | `<casa>/federado/dispositivos.json` | private, roles only | declared role, nothing measured |
| AI backend | LAB `node-metadata-parts/1` | `/api/federado` (≤120 s) | models at a snapshot |

Aduana rule (`src/index.js`): a heartbeat whose ID matches the cédula shape needs `admissionLinked` (scoped signed plan + verified cédula + APPROVED intake), else `403 human_admission_not_verified`. A plain alias is accepted on its key alone. **So today an alias heartbeat is connectivity, never authorized registration.**

## Effective routes (GET, no mutation, 2026-11-22)

`/api/v1/cedulas` 200 (catalog: 0 cédulas) · `/api/v1/deployment-requests` 403 without owner review key (correct) · `/api/v1/latidos` 200 · `/api/v1/edificios` 405 on GET (POST route). No admission route returns 404; the earlier 404 was the APP path `/api/nodo`, which is not a route (`/api/nodo/estado`, `/identity`, `/export`, `/edificio`, `/door1/preview` are).

Deployed Worker: last code upload 2026-11-21 13:15Z, **before** #41 (merged 19:02Z). No `PRECEPTOROS_SIGNED_NODE_PLANS`, no sovereign public key binding: every cédula would be `pendiente · sin ancla`.

## Link `primer-ancla` → admission (proposal, nothing changed)

Constraint: one node per cell; the observatory building is bound to `primer-ancla`; nothing may silently rename an identity.

1. **Recommended · explicit signed link.** The heartbeat entry gains an optional field: `"primer-ancla": {"q":0,"r":0,"cedula":"nodo.<N>.primer-ancla"}`. When it is present the Worker runs `admissionLinked(cedula)` for that alias. Alias, cell and building stay the same; revoking the admission removes the alias from the colony. Order matters: admit first, then add the field, or `primer-ancla` falls off the map. The code change belongs to the Aduana owner.
2. APP side: `node-identity.json` schema `/2` = `{esquema, node_id, admission_node_id}`. `node_building` keeps reading `node_id`, and `node_lifecycle` reads `admission_node_id`. Today `/1` gives the honest `local_identity_not_cedula_namespace` (#410).
3. Rejected: migrating the heartbeat to `nodo.<N>.primer-ancla` (needs a new cell or retiring the alias and re-binding the building), and reusing one file for both IDs (that was the #410 defect).

## S110 credential (procedure, revocable, key never leaves the phone)

Today the rotation job writes the `doggee-s110` key **only on the host** and publishes its hash. The phone has none, so it cannot beat. The host also holds a valid S110 credential, which means a host-sent beat could fake the phone's presence. Proposal:

1. Junie's physical window: in Termux, generate a 256-bit key into a private file (600). Only `sha256(key)` crosses to the host. Never paste the key into chat, Mesa, adb logs or HTML.
2. The rotation job stops generating `doggee-s110` and instead publishes the hash that came from the phone (it keeps the same 2-entry overlap). Its 24 h ceiling means the phone must rotate daily and hand over only the new hash.
3. The phone runs the existing `f1_heartbeat.py` sender with its own sequence file. Witness: `doggee-s110` appears in `/api/v1/latidos` while the host sends nothing for it.
4. Revoke: drop `doggee-s110` from the hash map → next beat 401 → it leaves the projection after expiry (#39).
5. This is still alias connectivity. Authorized registration needs its own cédula (next section).

The rotation script is not versioned in any repo; it should be versioned before this change.

## Tank 3 (prepared for HITL, nothing decided)

Candidates only: alias `tank-3` (matches the device registry), cell `(3,0)` (free as of the 3-nov checklist; current secret map not readable, and the Worker refuses duplicates), role APP_CLIENT. It must never advertise MODEL_SERVER. Cédula `nodo.<N>.tank-3`, with `<N>` chosen by the Sovereign.

## Authorized registration per node (what is still missing)

Owner's scoped plan (SSHSIG `preceptoros-plan-nodo`, carrying `request_sha256` of the consented intake) → cédula (SSHSIG `preceptoros-cedula`) → APPROVED D1 review → plan in `PRECEPTOROS_SIGNED_NODE_PLANS` → #41 deployed → a heartbeat after admission. Every signature is the Sovereign's; none is produced here.

## Test

`test_node_three_identities.py`: three homes, three owner keys, one shared catalog and projection. Proves that each node reaches LIVE only on its own evidence, that one revocation or one expiry withdraws only its node, that another node's receipt or owner key never admits, that a LIVE public alias is never promoted (zero network), and that no secret leaks. Sabotage measured: making `_seen_live` ignore the ID fails the new expiry test while `test_node_lifecycle` stays green.

Rollback: remove the test file and this doc. Neither runtime code nor live identity is touched.
