'use strict';
// My node: Beelink loopback intake adapter + ten-stage ladder (interface/node_registration.js). Pure, CI-safe.
const { test } = require('node:test');
const assert = require('node:assert/strict');
const flow = require('../interface/node_registration.js');
const loop = require('../interface/node_building.js').loopback; // owner APP only; absent from public builds
const { webcrypto } = require('node:crypto');

function win(origin, responder) {
  const u = new URL(origin), calls = [];
  return { calls, location: { protocol: u.protocol, hostname: u.hostname }, crypto: webcrypto,
    fetch: async (path, init) => { calls.push({ path, init }); return responder(path, init); } };
}
const json = (status, body) => ({ ok: status >= 200 && status < 300, status, json: async () => body });

test('adapter exists only on a plain-http loopback APP page', () => {
  for (const o of ['https://preceptoros.mvp.local', 'https://preceptoros.org', 'http://192.168.1.9:8742', 'https://127.0.0.1:8742'])
    assert.equal(loop.intake(win(o, () => json(200, {}))), null, o);
  for (const o of ['http://127.0.0.1:8742', 'http://localhost:8742'])
    assert.equal(typeof loop.intake(win(o, () => json(200, {}))).requestPreliminary, 'function', o);
});

test('one consented attempt: exact body, 32-hex nonce reused on retry, new attempt new nonce', async () => {
  const w = win('http://127.0.0.1:8742', () => json(502, { state: 'NO_DATA', cause: 'intake_receipt_unverified' }));
  const a = loop.intake(w);
  await assert.rejects(a.requestPreliminary({ node: 'nodo.42.fixture', purpose: 'p', consent: false }), /explicit_consent_required/);
  assert.equal(w.calls.length, 0);
  await assert.rejects(a.requestPreliminary({ node: 'nodo.42.fixture', purpose: 'p', consent: true }), /^Error: intake_receipt_unverified$/);
  await assert.rejects(a.requestPreliminary({ node: 'nodo.42.fixture', purpose: 'p', consent: true }), /intake_receipt_unverified/);
  const bodies = w.calls.map((c) => JSON.parse(c.init.body));
  assert.equal(w.calls[0].path, '/api/nodo/identity');
  assert.equal(w.calls[0].init.method, 'POST');
  assert.deepEqual(Object.keys(bodies[0]).sort(), ['consent', 'esquema', 'node', 'nonce']);
  assert.equal(bodies[0].esquema, 'preceptoros.pwa-node-deployment-request/1');
  assert.match(bodies[0].nonce, /^[a-f0-9]{32}$/);
  assert.equal(bodies[1].nonce, bodies[0].nonce, 'retry of the same attempt');
  const b = loop.intake(w);
  await assert.rejects(b.requestPreliminary({ node: 'nodo.42.fixture', purpose: 'p', consent: true }));
  assert.notEqual(JSON.parse(w.calls[2].init.body).nonce, bodies[0].nonce, 'new attempt');
  assert.ok(!('purpose' in bodies[0]), 'purpose stays local');
});

test('verified PENDING receipt through the adapter is never approval or LIVE', async () => {
  const d = flow.deploymentDraft('nodo.42.fixture', 'Public benchmark participation');
  const w = win('http://127.0.0.1:8742', () => json(202, { state: 'PENDING', contractVerified: true,
    preliminaryReceiptValidated: true, trackingId: 'a'.repeat(64), node: 'nodo.42.fixture', approved: false, live: false }));
  const r = await flow.requestDeploymentReview(d, true, loop.intake(w));
  assert.equal(r.state, flow.deploymentStates.pending); assert.equal(r.approved, false); assert.equal(r.live, false);
  const bad = win('http://127.0.0.1:8742', () => json(200, { state: 'PENDING', trackingId: 'x', node: 'nodo.42.fixture' }));
  await assert.rejects(flow.requestDeploymentReview(d, true, loop.intake(bad)), /preliminary_receipt_contract_unconfirmed/);
});

test('ladder: next action follows the first open stage; no skips; never LIVE by itself', () => {
  let v = flow.lifecycle({ identity: { state: 'NO_DATA', cause: 'identidad_no_provisionada' } });
  assert.equal(v.stages.length, 10); assert.equal(v.current, 0);
  assert.equal(v.stages[0].cause, 'identidad_no_provisionada'); assert.match(v.stages[0].next, /Node identity/);
  v = flow.lifecycle({ identity: { state: 'MEASURED' }, consented: true });
  assert.equal(v.current, 2); assert.equal(v.stages[1].done, true);
  v = flow.lifecycle({ identity: { state: 'MEASURED' }, receipt: { state: 'PENDING', trackingId: 'a'.repeat(64) },
    lifecycle: { cause: 'node_lifecycle_api_missing' } });
  assert.equal(v.current, 3); assert.equal(v.stages[2].state, 'PENDING');
  assert.equal(v.stages[3].cause, 'node_lifecycle_api_missing'); assert.match(v.stages[3].next, /never signs/);
  // A later server reading never counts while an earlier stage is open.
  v = flow.lifecycle({ identity: { state: 'NO_DATA', cause: 'x' }, lifecycle: { stages: { live: { state: 'MEASURED', cause: 'heartbeat_fresh' } } } });
  assert.equal(v.stages[6].state, 'NO_DATA'); assert.equal(v.stages[6].cause, 'earlier_stage_unverified');
  // A refusal stops the ladder where it happened.
  v = flow.lifecycle({ identity: { state: 'MEASURED' }, receipt: { state: 'PENDING', trackingId: 'a'.repeat(64) },
    lifecycle: { stages: { signature: { state: 'MEASURED', cause: 'sshsig_verified' }, approval: { state: 'REFUSED', cause: 'plan_rejected' } } } });
  assert.equal(v.current, 4); assert.equal(v.stages[4].state, 'REFUSED'); assert.equal(v.stages[4].cause, 'plan_rejected');
  assert.equal(v.live, false);
  // Unknown server state words and unbounded causes are not trusted.
  v = flow.lifecycle({ identity: { state: 'MEASURED' }, receipt: { state: 'PENDING', trackingId: 't' },
    lifecycle: { stages: { signature: { state: 'LIVE!!', cause: '<b>' } } } });
  assert.equal(v.stages[3].state, 'NO_DATA');
});

test('without the owner loopback module the page reads nothing and offers no intake', async () => {
  const e = await flow.readEvidence({});
  assert.equal(e.identity.cause, 'app_server_not_on_this_device');
});

test('reads report NO_DATA with cause off the loopback APP and when the lifecycle API is missing', async () => {
  let e = await loop.read(win('https://preceptoros.mvp.local', () => json(200, {})));
  assert.equal(e.identity.cause, 'app_server_not_on_this_device');
  e = await loop.read(win('http://127.0.0.1:8742', (p) => p === '/api/nodo/identity'
    ? json(200, { estado: 'configurada', node_id: 'nodo.42.fixture' }) : json(404, {})));
  assert.equal(e.identity.state, 'MEASURED'); assert.equal(e.lifecycle.cause, 'node_lifecycle_api_missing');
  e = await loop.read(win('http://127.0.0.1:8742', () => { throw new Error('down'); }));
  assert.equal(e.identity.cause, 'app_server_unreachable');
});

// Round 3 · the ladder consumes preceptoros.node-lifecycle/1 receipts.
const ID = { state: 'MEASURED', node: 'nodo.42.fixture' };
const R = { state: 'PENDING', trackingId: 'a'.repeat(64) };
const M = (cause) => ({ state: 'MEASURED', cause });
const life = (stages, node = 'nodo.42.fixture') => ({ schema: 'preceptoros.node-lifecycle/1', node, stages });

test('backend transitions advance the ladder one stage at a time; actor and next action are explicit', () => {
  let v = flow.lifecycle({ identity: ID, receipt: R, lifecycle: life({ signature: { state: 'PENDING', cause: 'sshsig_awaited' } }) });
  assert.equal(v.current, 3); assert.equal(v.stages[3].actor, 'signature');
  assert.match(flow.lifecycleSentence(v), /^Done: Request admission\. Stage 4 of 10 · Owner signature \(SSH\) · PENDING \(sshsig_awaited\)\. Needs a human SSH signature: /);
  v = flow.lifecycle({ identity: ID, receipt: R, lifecycle: life({ signature: M('sshsig_verified'), approval: { state: 'PENDING', cause: 'aduana_review' } }) });
  assert.equal(v.current, 4); assert.match(flow.lifecycleSentence(v), /Waiting for Aduana: /);
  v = flow.lifecycle({ identity: ID, receipt: R, lifecycle: life({ signature: M('a'), approval: M('b'), heartbeat: { state: 'NO_DATA', cause: 'heartbeat_key_missing' } }) });
  assert.equal(v.current, 5); assert.match(flow.lifecycleSentence(v), /Next \(you\): Start the node heartbeat/);
  assert.equal(v.live, false);
});

test('LIVE only when every earlier stage is MEASURED in a complete answer for this node', () => {
  const all = { request: M('r'), signature: M('a'), approval: M('b'), heartbeat: M('c'), live: M('world_state_live') };
  let v = flow.lifecycle({ identity: ID, lifecycle: life(all) });
  assert.equal(v.live, true); assert.equal(v.current, 7, 'next: local AI');
  const partial = { ...all }; delete partial.heartbeat;
  v = flow.lifecycle({ identity: ID, lifecycle: life(partial) });
  assert.equal(v.live, false); assert.equal(v.stages[5].cause, 'stage_missing_in_lifecycle');
  assert.equal(v.stages[6].cause, 'earlier_stage_unverified');
  v = flow.lifecycle({ identity: ID, lifecycle: life(all, 'nodo.99.other') });
  assert.equal(v.live, false); assert.equal(v.stages[3].cause, 'lifecycle_node_mismatch');
  v = flow.lifecycle({ identity: ID, lifecycle: life({ ...all, heartbeat: { state: 'ONLINE', cause: 'x' } }) });
  assert.equal(v.stages[5].cause, 'stage_state_unrecognized'); assert.equal(v.live, false);
});

test('the server request record survives a reload; refusal and revocation say how to continue', () => {
  let v = flow.lifecycle({ identity: ID, lifecycle: life({ request: { state: 'PENDING', cause: 'aduana_receipt_awaiting_human' } }) });
  assert.equal(v.stages[1].done, true, 'consent implied by a recorded request'); assert.equal(v.stages[2].done, true);
  v = flow.lifecycle({ identity: ID, receipt: R, lifecycle: life({ signature: M('a'), approval: { state: 'REFUSED', cause: 'plan_rejected' } }) });
  assert.match(flow.lifecycleSentence(v), /Blocked \(plan_rejected\): Read the cause, then send a new request/);
  v = flow.lifecycle({ identity: ID, lifecycle: life({ request: M('r'), signature: M('a'), approval: M('b'), revoke: { state: 'REVOKED', cause: 'owner_revoked' } }) });
  assert.equal(v.revoked, true); assert.equal(v.current, 2); assert.equal(v.stages[2].cause, 'node_revoked');
  assert.match(flow.lifecycleSentence(v), /Blocked \(node_revoked\): Your node was revoked/);
  assert.equal(v.stages[9].done, false, 'revoke is an action, never ticked off');
  const every = { request: M('r'), signature: M('a'), approval: M('b'), heartbeat: M('c'), live: M('d'), ai: M('e'), building: M('f'), revoke: M('revocation_available') };
  v = flow.lifecycle({ identity: ID, lifecycle: life(every) });
  assert.equal(v.stages[9].done, false); assert.equal(v.current, 9);
  assert.match(flow.lifecycleSentence(v), /^Done: Functional building published\. Stage 10 of 10 · Revoke · MEASURED \(revocation_available\)\. Next \(you\): You can revoke/);
});

test('EXPIRED and REFUSED stop the ladder wherever they appear, without ticking anything', () => {
  const v = flow.lifecycle({ identity: ID, receipt: R, lifecycle: life({ approval: { state: 'EXPIRED', cause: 'request_expired' } }) });
  assert.equal(v.current, 4); assert.equal(v.stages[3].done, false);
  assert.match(flow.lifecycleSentence(v), /Stage 5 of 10 · Admission approved · EXPIRED \(request_expired\)\. Blocked \(request_expired\): Read the cause/);
});

test('Create building: blocked with the first missing requirement; allowed only when the backend reports it ready', () => {
  const g = loop.buildingGate, ok = (c) => ({ state: 'MEASURED', cause: c });
  assert.equal(g(null).cause, 'node_lifecycle_unverified');
  assert.equal(g({ cause: 'node_lifecycle_api_missing' }).cause, 'node_lifecycle_api_missing');
  assert.equal(g(life({})).cause, 'owner_identity_unverified');
  assert.equal(g(life({ signature: ok('s') })).cause, 'node_not_admitted');
  assert.equal(g(life({ signature: ok('s'), approval: { state: 'PENDING', cause: 'd1_awaiting_owner_review' } })).cause, 'node_not_admitted');
  // Codex #402 today: building NO_DATA with its own cause → that cause explains the block.
  const real = g(life({ signature: ok('s'), approval: ok('a'), building: { state: 'NO_DATA', cause: 'authorized_function_invocation_source_unavailable' } }));
  assert.deepEqual([real.ok, real.cause], [false, 'authorized_function_invocation_source_unavailable']); assert.match(real.next, /function/);
  assert.equal(g(life({ signature: ok('s'), approval: ok('a'), building: { state: 'PENDING', cause: 'function_tested_policy_accepted' }, revoke: { state: 'REVOKED', cause: 'x' } })).cause, 'node_revoked');
  const ready = g(life({ signature: ok('s'), approval: ok('a'), building: { state: 'PENDING', cause: 'function_tested_policy_accepted' } }));
  assert.equal(ready.ok, true, 'not blocked when every requirement is accredited');
});

test('a local public alias does not advance cédula admission', () => {
  const result = flow.lifecycle({
    identity: { state: 'MEASURED', node: 'public-fixture' },
    lifecycle: life({ prepare: { state: 'NO_DATA', cause: 'local_identity_not_cedula_namespace' } }, null)
  });
  assert.equal(result.current, 0);
  assert.equal(result.stages[0].cause, 'local_identity_not_cedula_namespace');
  assert.equal(result.live, false);
});

test('HEX-NODE3 v2: the owner-chosen alias and roles go in the request; without the form v1 stays', () => {
  const nb = require('../interface/node_building.js');
  const form = { 'node-registration-roles': { querySelectorAll: () => [{ checked: true, value: 'APP_CLIENT' },
    { checked: false, value: 'MODEL_SERVER' }] }, 'node-registration-alias': { value: ' fixture-v2 ' } };
  const v2 = nb.loopback.intakeBody({ document: { getElementById: (id) => form[id] || null } }, 'nodo.906.fixture-v2', 'a'.repeat(32));
  assert.deepEqual(v2, { esquema: 'preceptoros.pwa-node-deployment-request/2', node: 'nodo.906.fixture-v2',
    nonce: 'a'.repeat(32), consent: true, alias: 'fixture-v2', roles: ['APP_CLIENT'] });
  const none = { 'node-registration-roles': { querySelectorAll: () => [] } };
  assert.deepEqual(nb.loopback.intakeBody({ document: { getElementById: (id) => none[id] || null } }, 'n', 'b').roles, ['APP_CLIENT']);
  assert.equal(nb.loopback.intakeBody({ document: { getElementById: () => null } }, 'n', 'b').esquema,
    'preceptoros.pwa-node-deployment-request/1');
});

test('HEX-NODE3-07: one reading drives Acho, the spoken sentence and the JSON; every asked cause is named', () => {
  const ex = require('../interface/node_building.js').loopback.explain;
  const ok = ex({ state: 'MEASURED', cause: 'heartbeat_receipt_verified', node: 'fixture-v2', public_map: 'LISTED' }, 'Received.');
  assert.deepEqual([ok.state, ok.acho], ['MEASURED', 'ok']);
  assert.match(ok.sentence, /^Received\. The public map lists fixture-v2\.$/);
  assert.doesNotMatch(ok.sentence, /LIVE/);
  const asked = { emisor_no_autorizado: [/revoked/, 'fence'], heartbeat_key_expired: [/expired/, 'needs_you'],
    human_admission_not_verified: [/signed admission/, 'needs_you'], plan_firmado_rechazado: [/rejected/, 'fence'],
    aduana_unavailable: [/Connection lost/, null], awaiting_sovereign_approval: [/not signed/, 'needs_you'] };
  for (const [cause, [text, acho]] of Object.entries(asked)) {
    const v = ex({ state: 'NO_DATA', cause }, 'x');
    assert.equal(v.state, 'NO_DATA'); assert.equal(v.acho, acho, cause); assert.match(v.sentence, text, cause);
  }
  const odd = ex({ state: 'NO_DATA', cause: '<img onerror=x>' }, 'x');
  assert.equal(odd.cause, 'no_answer');
  assert.equal(ex({ state: 'LIVE', cause: 'self_declared' }, 'x').state, 'NO_DATA', 'a self-declared LIVE is not a state');
});
