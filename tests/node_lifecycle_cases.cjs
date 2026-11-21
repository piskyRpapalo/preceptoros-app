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
