'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const api = require('../interface/owner_model_slots.js');

const initial = () => ({
  private_chat_model: { runtime: 'on_device', label: 'My local model' },
  public_visitor_model: { runtime: 'owner_managed', label: 'Crab Guide' },
});
function fakeStore() {
  const data = new Map();
  return {
    getItem: (k) => data.get(k) ?? null,
    setItem: (k, v) => data.set(k, v),
    removeItem: (k) => data.delete(k),
    data,
  };
}
test('two slots exist and are independent, never authority', () => {
  const state = api.snapshot(initial());
  assert.equal(state.schema, 'preceptoros.owner-model-slots/1');
  assert.equal(state.private_chat_model.selection_state, 'DRAFT_ONLY');
  assert.equal(state.private_chat_model.reply_state, 'NO_DATA');
  assert.equal(state.public_visitor_model.selection_state, 'DRAFT_ONLY');
  assert.equal(state.public_visitor_model.admission_state, 'NO_DATA');
  assert.equal(state.public_visitor_model.reply_state, 'NO_DATA');
  assert.equal(state.authority, 'NOT_AUTHORIZED');
});
test('private model name never appears in public visitor declaration', () => {
  const draft = api.publicDraft(initial(), true);
  assert.equal(draft.ok, true);
  const json = JSON.stringify(draft.value);
  assert.equal(draft.value.schema, 'preceptoros.public-visitor-model-draft/1');
  assert.equal(draft.value.state, 'DRAFT_ONLY');
  assert.equal(draft.value.authority, 'NOT_AUTHORIZED');
  assert.equal(draft.value.public_response, 'NO_DATA');
  assert.equal(draft.value.public_visitor_model.label, 'Crab Guide');
  assert.ok(!json.includes('My local model'), 'private chat name should not be in public export');
  assert.ok(!json.includes('private_chat_model'));
});
test('must consent explicitly for public draft', () => {
  assert.equal(api.publicDraft(initial(), false).cause, 'owner_consent_required');
  const c = initial();
  c.public_visitor_model.runtime = 'none'; c.public_visitor_model.label = '';
  assert.equal(api.publicDraft(c, true).cause, 'public_model_not_selected');
});
test('untrusted extra fields are removed from local storage', () => {
  const store = fakeStore();
  const config = {
    ...initial(),
    private_chat_model: { ...initial().private_chat_model, api_key: 'never-save' },
    public_visitor_model: { ...initial().public_visitor_model, endpoint: 'http://private.lan', grant: 'exec' },
    private_rack: true, token: 'sensitive',
  };
  const save = api.save(store, config);
  assert.equal(save.ok, true);
  const persisted = store.getItem(api.storageKey);
  for (const forbidden of ['api_key', 'token', 'grant', 'private_rack', 'endpoint', 'private.lan'])
    assert.equal(persisted.includes(forbidden), false, forbidden);
  assert.equal(api.read(store).ok, true);
  assert.equal(api.snapshot(api.read(store).value).authority, 'NOT_AUTHORIZED');
});
test('reject secret-looking names, endpoint URLs and malformed data', () => {
  const bad = [
    'sk-abcdef1234567890',
    'Bearer xyz123456789012345',
    'https://some.host:11434',
    '<script>alert(1)</script>',
    'github_pat_abcd1234',
    'private_key',
    'a'.repeat(61),
  ];
  for (const name of bad) {
    const config = initial(); config.private_chat_model.label = name;
    assert.equal(api.validate(config).ok, false, name);
  }
  const corrupted = [null, [], {}, { private_chat_model: {}, public_visitor_model: {} }];
  for (const config of corrupted) assert.equal(api.validate(config).ok, false);
});
test('invalid runtime cannot masquerade as a tool or rack model', () => {
  for (const runtime of ['private_hexelion', 'rack', 'mcp_exec', 'file:///etc/shadow']) {
    const c = initial(); c.private_chat_model.runtime = runtime;
    assert.equal(api.validate(c).ok, false, runtime);
    c.private_chat_model = initial().private_chat_model;
    c.public_visitor_model.runtime = runtime;
    assert.equal(api.validate(c).ok, false, runtime);
  }
});
test('new visitor starts unconfigured without a fake success', () => {
  const fresh = api.read(fakeStore());
  assert.equal(fresh.ok, true);
  assert.equal(fresh.cause, 'first_run');
  const state = api.snapshot(fresh.value);
  assert.equal(state.private_chat_model.selection_state, 'NO_DATA');
  assert.equal(state.public_visitor_model.selection_state, 'NO_DATA');
});
test('read corrupt localStorage fail closed and never recover unknown grants', () => {
  const store = fakeStore();
  store.setItem(api.storageKey, '{"private_chat_model": ');
  assert.equal(api.read(store).ok, false);
  store.setItem(api.storageKey, '{}'.padEnd(1100, 'x'));
  assert.equal(api.read(store).cause, 'stored_config_oversized');
  assert.equal(api.save({ setItem() { throw Error('denied'); } }, initial()).cause, 'browser_storage_unavailable');
});
test('label change cannot make a verified inference claim', () => {
  const c = initial(); c.private_chat_model.label = 'My 135M';
  const state = api.snapshot(c);
  assert.equal(state.private_chat_model.reply_state, 'NO_DATA');
  assert.equal(state.public_visitor_model.reply_state, 'NO_DATA');
});
