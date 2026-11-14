# NODE-BIRTH R4 · pure export inspection contract

2026-11-14. Existing mission NODE-BIRTH-R4-FIELDS-01/Mesa #3 claim6881839694;
ROUND9 BUILD update6882515184. Read depth2. Initial scope:nodo_export_preview.py,
test_nodo_export_preview.py,this technical contract. Direct user HITL then authorized
the single bin/pruebas registration line,recorded in amendment6882714674.
Current scope is those four files. Mission stays in Mesa.
Base APP7ac622872bdecb9d77569cb6d83a18be0b043745 includes R3 PR296 unchanged.
Prior plan packet73325c19aeee4a272f8c2e7ac9bceafa8d19d5e2ebdedec9dc1bfb7b9e096493
and its26 specifications/Q1-Q6 are reused,not reconstructed into another service.

## Output for Claude and Junie

`preview(raw_json,selected_paths,expected_ref=None,generation=0,consent=None,
revoked=False,recipient=existing_export_endpoint,purpose="export")` is pure.
It accepts bounded UTF-8 JSON bytes/text,not a filename or live registry object.
No clock,filesystem,network,process,key verification,signing,policy loading,
identifier mapping or transport is called. Existing nodo_app shape/signed-body
helpers and existing exporter serialization/recipient are reused.

Output schema preceptoros.node-export-preview/0:
- Valid inspectable input:state=BLOCKED,inspection=AVAILABLE;masked concrete
  field rows,required/present/selected/signed/digest coverage,type,field/value refs.
- Invalid/oversize/deep/duplicate-key/type/selection/context input:REJECTED with
  safe causes,no raw source echoed. Unknown field names/values are withheld.
- Always export_allowed=false,transport=null,authority=NOT_GRANTED,
  may_operate=false,node_admission=NO_DATA. No READY or transportable credential.
- binding contains existing credential digest,signed-body ref,exact would-send
  payload ref,selection ref,selected concrete paths,fixed recipient/method,local
  generation/revoked/purpose and UNRESOLVED policy state;preview_ref binds these.
  References prove correlation,not identity,signature or disclosure permission.
- Raw values/signature bytes are withheld;source remains local to the caller.
  This increment exposes field inventory and fingerprints,not a value-display UI.

Bounds:65536 serialized bytes,depth12 before decoder,512 value nodes,512 selected
paths of at most128 characters. JSON duplicate keys/nonfinite values rejected.
Containers (including empty arrays) and concrete device indexes are explicit;
no wildcard,alias,truthy consent,implicit subtree or unknown-field publication.

## Fail-closed policy

Q1-Q6 remain unresolved. Even a fully selected clean credential remains BLOCKED
with disclosure_policy_unresolved,consent_authority_unresolved,
revocation_action_policy_unresolved,replacement_authority_unresolved and
signature_not_verified. Passing a purported consent/MH-01 packet adds
supplied_consent_not_authority;it does not supply trusted permission.
No arbitrary owner-approved allowlist/TTL/retry rule was invented.

Deselected required/signed fields add explicit blocking causes. Input/hash/signature
are never rewritten or silently filtered. Optional root firma/autenticidad are
outside SSH coverage but inside credential-digest coverage when present;their
selection still matters. Unknown nested data is blocked and masked. A changed
payload/signature/selection/recipient/context/generation invalidates earlier
preview_ref;known revocation flags and historical revoked records are reported
with blocked unresolved action semantics,not an admission revocation decision.
A compatible replacement credential needs existing authorized owner/issuer review;
this module cannot create one. No use of device identity as node admission.

MH-01 retains120-second operational freshness and its independent witness;
its declared/ATTESTED/CONNECTED/history/lease states are not consent,execution,
publication,admission or territory. No other adapter/scheduler is introduced.

## Reused adversarial specification mapping

S01-S17:default selection/consent,unknown root/nested/list fields,required/signed
and unsigned deselection,masked values,exact paths/empty containers,integrity,
changed payload/context,immutable bytes and revocation become executable tests.
S18 after-send remote history/retraction is outside a pure non-sender;no executable
PASS is claimed for it. S19-S22 revoked records/notices,MH claims,self-hash evidence
are blocked diagnostic tests. S23 clean complete selection is a positive inspection
case that remains policy-BLOCKED;actual allowed transport is not implemented.
S24 repeats remain blocked. S25 preview cannot be sent as a credential;foreign
receipt rejection is tested by unchanged R3's separate regression suite.
S26 bounded parser and duplicate/nonfinite/type cases are executable.
Extra tests pin existing byte/hash semantics,missing receiver fields,node bounds,
unknown nested scalars,strict context types,determinism and forbidden I/O.
No vacuous after-send mutation test or expectedFailure/skip hides missing transport.

Run new suite and R3 regression twice. Test-only mutations removing selected/signed
causes,binding/masking,or fail-closed authorization must be detected. Run baseline
bin/pruebas twice,separately preserving skips/RED and its inherited intermittent
canales baseline behavior. No baseline failure is relabeled a PASS.

## Scope and limits

The initial3-file core was tested directly and both unregistered general gates
failed test_superficie.py:181. Those RED controls are retained. The user explicitly
authorized one bin/pruebas list-line amendment;new suite is now registered beside
R3 and will be exercised by the final whole gate. No expectation was weakened.
The 31 new tests are counted separately and included in final registered totals.
Exporter/PWA transport gate is not activated.
R4 transport RED from prior rounds and PWA document-state409 RED remain independent;
this new inspection core does not fix or hide them. No live UI/HTTP/device proof.

Next owner step:answer Q1-Q6 and authorize the later existing exporter/consumer
gate as a separate scoped piece. Runner registration is already authorized. No new network/rack/signing/
node/territorial permissions required. Publish only an isolated draft if core
gates pass. No WEB/Aduana/signatures/services/permissions/main/merge/deploy changes.
