'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const flow = require('../interface/node_registration.js');
const H1 = 'a'.repeat(64), H2 = 'b'.repeat(64), H3 = 'c'.repeat(64);

async function fixture(node = 'nodo.7.demo', attrs = {}) {
  return flow.createAduanaRequest(Object.assign({
    node, adminSha256: H1, planSha256: H2, devices: [],
    firmaSsh: ''
  }, attrs));
}
function receipt(cedula, estado = 'pendiente', causa = 'ancla_ausente') {
  const recibo = { esquema:'preceptoros.recibo-cedula/1',
    credential_sha256: cedula.sha256, node_id: cedula.nodo,
    admin_sha256: cedula.admin, plan_sha256: cedula.plan_sha256,
    estado, causa, recibido:'2026-11-18T18:12:00.000Z' };
  recibo.recibo_sha256 = createHash('sha256')
    .update(flow.canonicalAduana(recibo)).digest('hex');
  return { estado, causa, recibidos:1, recibo,
    paquete:{ esquema:'preceptoros/cedula-nodo/1', pares:[cedula], firma:null } };
}

test('Aduana cédula has required fields, canonical digest and NO synthetic signature', async () => {
  const c = await fixture();
  assert.equal(c.esquema, 'preceptoros.cedula-nodo/1');
  assert.equal(c.admin, H1); assert.equal(c.plan_sha256, H2);
  assert.equal(c.firma_ssh, '');
  assert.ok(!Object.hasOwn(c, 'firma'));
  assert.ok(!Object.hasOwn(c, 'autenticidad'));
  const { sha256, ...base } = c;
  assert.equal(sha256, createHash('sha256').update(flow.canonicalAduana(base)).digest('hex'));
});
test('malformed name, missing admin, missing signed-plan digest, bad device rejected', async () => {
  for (const obj of [
    { node:'bad' }, { adminSha256:null }, { planSha256:null },
    { devices:[{clave:H3,estado:'LIVE'}] },
    { devices:[{clave:'not-a-digest',estado:'solicitado'}] },
    { firmaSsh: 'x'.repeat(16385) }
  ]) await assert.rejects(fixture('nodo.7.demo',obj));
});
test('no consent means no call, no ambient browser network fallback', async () => {
  const c = await fixture();
  let calls = 0;
  const adapter = flow.aduanaAdapter(async () => { calls++; return {}; });
  await assert.rejects(adapter.submit(c, false), /explicit_consent_required/);
  await assert.rejects(flow.aduanaAdapter().submit(c, true), /native_https_transport_required/);
  assert.equal(calls, 0);
});
test('one approved endpoint/method, valid pending 202 is not APPROVED or LIVE', async () => {
  const c = await fixture(); let calls=0;
  const adapter = flow.aduanaAdapter(async (url, req) => {
    calls++;
    assert.equal(url, 'https://api.preceptoros.org/api/v1/cedulas');
    assert.equal(req.method, 'POST');
    assert.equal(req.cache, 'no-store');
    assert.deepEqual(Object.keys(JSON.parse(req.body)), ['cedula']);
    return {status:202, json:async () => receipt(c)};
  });
  const out=await adapter.submit(c, true);
  assert.equal(out.state,'pending'); assert.equal(out.approved,false);
  assert.equal(out.live,false); assert.equal(out.receiptIntegrity,'sha256_match_not_signature');
  assert.equal(out.aduanaState,'pendiente'); assert.equal(calls,1);
});
test('idempotent replay HTTP 200 keeps receipt and remains pending', async () => {
  const c = await fixture(); const saved=receipt(c); let calls=0;
  const adapter = flow.aduanaAdapter(async () => ({status: calls++ === 0 ? 202 : 200, json:async () => saved}));
  const first=await adapter.submit(c,true), second=await adapter.submit(c,true);
  assert.equal(first.receipt.recibo_sha256,second.receipt.recibo_sha256);
  assert.equal(second.state,'pending'); assert.equal(second.live,false);
});
test('verified cédula does NOT imply carbon approval or observed heartbeat', async () => {
  const c=await fixture();
  const out=await flow.verifyAduanaReceipt(c,receipt(c,'verificado',null),202);
  assert.equal(out.state,'submitted'); assert.equal(out.aduanaState,'verificado');
  assert.equal(out.approved,false); assert.equal(out.live,false);
});
test('tampering in cédula is refused before transport', async () => {
  const c=await fixture(), tampered={...c, admin:H3};
  let calls=0; const a=flow.aduanaAdapter(async () => {calls++;return {};});
  await assert.rejects(a.submit(tampered,true), /cedula_hash_mismatch/);
  assert.equal(calls,0);
});
test('tampered receipt hash, node, plan or status are rejected', async () => {
  const c=await fixture();
  for (const changed of [
    r=>{r.recibo.recibo_sha256=H3;},
    r=>{r.recibo.node_id='nodo.8.demo';},
    r=>{r.recibo.plan_sha256=H3;},
    r=>{r.estado='verificado';},
    r=>{r.recibo.estado='LIVE';},
    r=>{r.recibo.recibido='no-date';},
    r=>{r.paquete.pares[0]={sha256:H3};}
  ]) {
    const r=receipt(c); changed(r);
    await assert.rejects(flow.verifyAduanaReceipt(c,r,202));
  }
});
test('HTTP 200 alone, wrong status, malformed JSON and offline do not prove admission', async () => {
  const c=await fixture();
  await assert.rejects(flow.verifyAduanaReceipt(c,{estado:'pendiente'},200));
  await assert.rejects(flow.verifyAduanaReceipt(c,receipt(c),500));
  await assert.rejects(flow.aduanaAdapter(async()=>({status:200,json:async()=>{throw Error('bad');}}))
    .submit(c,true),/invalid_response_json/);
  await assert.rejects(flow.aduanaAdapter(async()=>{throw Error('offline');})
    .submit(c,true),/offline/);
});
test('unicode receipt hashes use Aduana ascii-only canonical JSON',async () => {
  const c=await fixture(), r=receipt(c,'pendiente','ancla_ausente \u00e1');
  const out=await flow.verifyAduanaReceipt(c,r,202);
  assert.equal(out.state,'pending');
  assert.ok(flow.canonicalAduana(r.recibo).includes('\\u00e1'));
});
