'use strict';
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { test } = require('node:test');
const script = readFileSync(require('node:path').join(__dirname, '../mvp-android/android_review_bridge.js'), 'utf8');

function fixture(bridgeResult, options = {}) {
  const events = [];
  const status = {
    textContent: 'DRAFT_ONLY · ready to copy or download',
    values: { 'data-state': 'DRAFT_ONLY' },
    setAttribute(name, value) { this.values[name] = value; },
    getAttribute(name) { return this.values[name]; },
  };
  const link = {
    hidden: !!options.hidden,
    href: 'https://github.com/piskyRpapalo/preceptoros-companion/issues/new?title=...',
    dataset: {},
    addEventListener(type, callback) { events.push({ type, callback }); },
  };
  const draft = { textContent: options.empty ? '' : '# Companion Declaration Draft\nStatus: DRAFT_ONLY\n' };
  const calls = [];
  const bridge = {
    openReview(url) {
      calls.push(url);
      if (bridgeResult === 'throw') throw new Error('bridge failure');
      return bridgeResult;
    },
  };
  const dom = {
    getElementById(id) {
      return ({
        'companion-request-review': link,
        'companion-status': status,
        'companion-draft': draft,
      })[id] || null;
    }
  };
  const context = { document: dom, window: options.browser ? {} : { PreceptorAndroidReview: bridge } };
  function activate() { runInNewContext(script, context); }
  function click() {
    let prevented = false;
    for (const event of events) {
      assert.equal(event.type, 'click');
      event.callback({ preventDefault() { prevented = true; } });
    }
    return prevented;
  }
  return { activate, click, calls, status, link, events };
}

test('Android explicit click requests external composer only, NEVER submits', () => {
  const f = fixture(true);
  f.activate();
  assert.equal(f.events.length, 1);
  assert.equal(f.click(), true);
  assert.equal(f.calls.length, 1);
  assert.equal(f.status.values['data-state'], 'DRAFT_ONLY');
  assert.equal(f.status.values['data-acho'], 'DRAFT_ONLY');
  assert.equal(f.status.values['data-cause'], 'external_review_requested_not_submitted');
  assert.match(f.status.textContent, /Not submitted or received/);
});

test('Browser mode uses original link with no bridge interception', () => {
  const f = fixture(true, { browser: true });
  f.activate();
  assert.equal(f.events.length, 0);
  assert.equal(f.click(), false);
});

test('Android bridge refusal is NO_DATA for eye/ear/machine', () => {
  const f = fixture(false); f.activate(); f.click();
  assert.equal(f.calls.length, 1);
  assert.equal(f.status.values['data-state'], 'NO_DATA');
  assert.equal(f.status.values['data-acho'], 'NO_DATA');
  assert.equal(f.status.values['data-cause'], 'android_review_handoff_rejected');
});

test('Exception is not presented as delivery', () => {
  const f = fixture('throw'); f.activate(); f.click();
  assert.equal(f.status.values['data-state'], 'NO_DATA');
  assert.match(f.status.textContent, /Nothing sent/);
});

test('No draft or hidden link forbids handoff', () => {
  for (const settings of [{ empty: true }, { hidden: true }]) {
    const f = fixture(true, settings); f.activate(); f.click();
    assert.equal(f.calls.length, 0);
    assert.equal(f.status.values['data-cause'], 'android_review_draft_missing');
  }
});

test('Duplicate script injection does not attach duplicate listeners', () => {
  const f = fixture(true); f.activate(); f.activate();
  assert.equal(f.events.length, 1);
  assert.equal(f.click(), true);
  assert.equal(f.calls.length, 1);
});
