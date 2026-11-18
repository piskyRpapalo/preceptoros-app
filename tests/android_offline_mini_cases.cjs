'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const mini = require('../mvp-android/offline_mini.js');
const p = mini.parse;
test('public deterministic contract has no actor permissions', () => {
  assert.equal(mini.schema, 'preceptoros.offline-mini/1');
  for (const input of ['/ejecuta git status', 'deploy the rack', 'firma mi nodo']) {
    const result = p(input);
    assert.equal(result.state, 'NO_DATA', input);
    assert.equal(result.cause, 'remote_effect_not_authorized', input);
    assert.equal(result.action, undefined, input);
  }
});
test('visible local navigation works in Spanish, English and Portuguese', () => {
  const examples = [
    ['abre documentos', 'documents'], ['open lab', 'lab'],
    ['abre laboratorio', 'lab'], ['go to chat', 'chat'],
    ['muestra mi nodo', 'node'], ['ve a documentos', 'documents'],
  ];
  for (const [input, action] of examples) {
    const r = p(input);
    assert.equal(r.action, action, input);
    assert.equal(r.source, 'rules');
  }
});
test('local help, greeting, status are not claimed as generative answers', () => {
  for (const input of ['hola', '/help', 'estado']) {
    const r = p(input);
    assert.equal(r.source, 'rules');
    assert.equal(r.state, 'DRAFT_ONLY');
  }
});
test('plans require explicit human Save and do not create a task', () => {
  const r = p('escribe un plan');
  assert.equal(r.action, 'plan');
  assert.match(r.text, /No se guarda ni ejecuta nada/);
});
test('unknown prompt remains fail-closed without a native LLM', () => {
  for (const input of ['Dime qué piensa Aristóteles', 'redacta un poema', '2 + 2']) {
    const r = p(input);
    assert.equal(r.source, 'model');
    assert.equal(r.state, 'NO_DATA');
    assert.equal(r.cause, 'on_device_model_unverified');
  }
});
test('limits user text without escaping into executable content', () => {
  const r = p('<script>alert(1)</script>');
  assert.equal(r.state, 'NO_DATA');
  assert.equal(r.action, undefined);
  assert.equal(mini.parse('x'.repeat(15000)).cause, 'input_oversize');
});
test('oversize cannot be truncated into navigation, action or model call', () => {
  const attempts = [
    'go to lab ' + 'x'.repeat(1300),
    'escribe un plan ' + 'x'.repeat(1300),
    'hola ' + 'x'.repeat(1300),
    'abre documentos ' + '🌱'.repeat(280), // < 600 JS chars, > 1023 UTF-8 bytes
  ];
  for (const text of attempts) {
    const out = p(text);
    assert.equal(out.state, 'NO_DATA', text.slice(0, 20));
    assert.equal(out.cause, 'input_oversize', text.slice(0, 20));
    assert.equal(out.action, undefined);
    assert.equal(out.source, 'rules');
  }
});
