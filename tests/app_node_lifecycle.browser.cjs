/* My node lifecycle · real Chromium on the real APP server (bin/preceptoros-pwa, isolated temporary HOME).
 * Real: identity read, local identity provisioning, ladder painting, keyboard, 44 px, widths 390/420/780.
 * SYNTHETIC: the consented intake POST is answered by the test inside the page (route), because the server forwards
 * it to production Aduana; a real request must come from a person's consent, not from CI.
 * TEST DOUBLE (second test): GET /api/nodo/estado answers in the preceptoros.node-lifecycle/1 shape the ladder
 * consumes; Codex owns the real endpoint (HTTP 404 on Beelink 8742 on 2026-11-21).
 * Requires playwright-core (or playwright) and Chromium: CHROME_PATH or /usr/bin/google-chrome.
 */
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
let chromium;
try { ({ chromium } = require('playwright-core')); } catch (_) { ({ chromium } = require('playwright')); }

const ROOT = resolve(__dirname, '..');
const teaser = (page) => page.$eval('#mvp-journey-guide .fold-teaser', (e) => e.textContent);
const ladder = (page) => page.$$eval('#mvp-journey li', (ls) => ls.map((l) => ({ k: l.dataset.key, s: l.dataset.state, a: l.dataset.acho, c: l.dataset.cause, cur: l.getAttribute('aria-current') })));

test('My node: ladder follows the real server, identity step, consent and a pending receipt', { timeout: 180000 }, async () => {
  const home = mkdtempSync(join(tmpdir(), 'preceptoros-node-ladder-'));
  const port = Number(process.env.NODE_LADDER_PORT || 18931);
  const url = 'http://127.0.0.1:' + port + '/app';
  const child = spawn('python3', [join(ROOT, 'bin/preceptoros-pwa')], { cwd: ROOT,
    env: { ...process.env, HOME: home, PRECEPTOROS_HEXELION_ENDPOINT: '', PRECEPTOROS_PWA_BIND: '127.0.0.1', PRECEPTOROS_PWA_PUERTO: String(port) },
    stdio: 'ignore' });
  let browser;
  try {
    let alive = false;
    for (let i = 0; i < 60 && !alive; i++) {
      try { const r = await fetch(url); alive = r.ok; await r.arrayBuffer(); } catch (_) { await new Promise((r) => setTimeout(r, 150)); }
    }
    assert.equal(alive, true, 'APP server up');
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
    let first = true;
    for (const width of [390, 420, 780]) {
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
      const page = await ctx.newPage(), errors = [], intake = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      await page.route('**/api/nodo/identity', async (route) => {
        const req = route.request(), body = req.postDataJSON && req.method() === 'POST' ? req.postDataJSON() : null;
        if (body && body.esquema === 'preceptoros.pwa-node-deployment-request/1') {
          intake.push(body);
          return route.fulfill({ status: 202, contentType: 'application/json', body: JSON.stringify({ state: 'PENDING',
            contractVerified: true, preliminaryReceiptValidated: true, trackingId: 'f'.repeat(64), node: body.node, approved: false, live: false }) });
        }
        return route.continue();
      });
      await page.goto(url);
      await page.click('#tab-ajustes');
      if (first) {
        await page.waitForFunction(() => /Stage 1 of 10 · Prepare node identity · NO_DATA \(identidad_no_provisionada\)/.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
        // Real local step, through the existing Node identity form (writes only the temporary HOME).
        await page.click('#mynode-identity-toggle');
        await page.fill('#node-identity-id', 'nodo.42.ladder');
        await page.check('#node-identity-consent');
        await page.click('#node-identity-save');
        first = false;
      } else {
        await page.waitForFunction(() => document.querySelector('#mvp-journey li[data-key="prepare"]')?.dataset.state === 'done');
      }
      await page.waitForFunction(() => /Done: Prepare node identity\. Stage 2 of 10 · Owner consent · NO_DATA \(owner_consent_not_given\)\. Next \(you\): /.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
      let l = await ladder(page);
      assert.equal(l.length, 10); assert.equal(l[0].s, 'done'); assert.equal(l[1].cur, 'step');
      // Consent and request through the existing form, by keyboard where it matters.
      if (await page.$eval('#mynode-identity-toggle', (b) => b.getAttribute('aria-expanded')) !== 'true') await page.click('#mynode-identity-toggle');
      const hidden = await page.$eval('#node-admission-open', (b) => { const a = []; for (let x = b; x; x = x.parentElement) { if (x.hidden || (x.tagName === 'DETAILS' && !x.open) || getComputedStyle(x).display === 'none') a.push(x.id || x.tagName); } return a; });
      assert.deepEqual(hidden, [], 'admission button reachable after Node identity: ' + hidden);
      await page.click('#node-admission-open');
      await page.fill('#node-registration-name', 'nodo.42.ladder');
      await page.fill('#node-registration-purpose', 'Public benchmark participation');
      await page.click('#node-registration-form button[type=submit]');
      await page.focus('#node-registration-consent'); await page.keyboard.press('Space');
      assert.match(await teaser(page), /Done: Owner consent\. Stage 3 of 10 · Request admission/);
      const box = await page.$eval('#node-registration-submit', (b) => { const r = b.getBoundingClientRect(); return [r.width, r.height]; });
      assert.ok(box[1] >= 44, 'request button ≥ 44 px tall: ' + box);
      await page.focus('#node-registration-submit'); await page.keyboard.press('Enter');
      await page.waitForFunction(() => /^Done: Request admission\. Stage 4 of 10 · Owner signature \(SSH\) · NO_DATA \(signed_export_or_plan_unavailable\)\. Needs a human SSH signature: The owner signs/.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
      l = await ladder(page);
      assert.equal(l[2].a, 'PENDING'); assert.equal(l[2].s, 'done');
      for (const later of l.slice(3)) assert.notEqual(later.s, 'done', later.k + ' must not be claimed');
      assert.equal(intake.length, 1);
      assert.deepEqual(Object.keys(intake[0]).sort(), ['consent', 'esquema', 'node', 'nonce']);
      // The same sentence for eye (teaser), screen reader (live status) and machine (data-*).
      const live = await page.$eval('#mvp-node-state', (e) => ({ t: e.textContent, s: e.dataset.state, c: e.dataset.cause, role: e.getAttribute('role') }));
      assert.equal(live.t, await teaser(page)); assert.equal(live.s, 'NO_DATA'); assert.equal(live.c, 'signed_export_or_plan_unavailable'); // real #402 projection (the intake POST was synthetic) assert.equal(live.role, 'status');
      assert.match(await page.$eval('#node-registration-status', (e) => e.textContent), /Not a live node/);
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'no horizontal scroll at ' + width);
      assert.deepEqual(errors, []);
      await ctx.close();
    }
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
    rmSync(home, { recursive: true, force: true });
  }
});

test('My node follows backend transitions: signature, Aduana, heartbeat; a partial or foreign answer never shows LIVE', { timeout: 180000 }, async () => {
  const home = mkdtempSync(join(tmpdir(), 'preceptoros-node-ladder-'));
  const port = Number(process.env.NODE_LADDER_PORT || 18931) + 1;
  const url = 'http://127.0.0.1:' + port + '/app';
  const child = spawn('python3', [join(ROOT, 'bin/preceptoros-pwa')], { cwd: ROOT,
    env: { ...process.env, HOME: home, PRECEPTOROS_HEXELION_ENDPOINT: '', PRECEPTOROS_PWA_BIND: '127.0.0.1', PRECEPTOROS_PWA_PUERTO: String(port) },
    stdio: 'ignore' });
  let browser;
  try {
    let alive = false;
    for (let i = 0; i < 60 && !alive; i++) {
      try { const r = await fetch(url); alive = r.ok; await r.arrayBuffer(); } catch (_) { await new Promise((r) => setTimeout(r, 150)); }
    }
    assert.equal(alive, true, 'APP server up');
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
    const page = await (await browser.newContext({ viewport: { width: 420, height: 900 }, hasTouch: true })).newPage(), errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    let answer = null;
    await page.route('**/api/nodo/estado', (route) => answer
      ? route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(answer) })
      : route.fulfill({ status: 404, contentType: 'application/json', body: '{}' }));
    await page.goto(url);
    await page.click('#tab-ajustes');
    await page.click('#mynode-identity-toggle');
    await page.fill('#node-identity-id', 'nodo.42.ladder');
    await page.check('#node-identity-consent');
    await page.click('#node-identity-save');
    await page.waitForFunction(() => /Stage 2 of 10/.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
    const M = (cause) => ({ state: 'MEASURED', cause });
    const step = async (stages, expect, node = 'nodo.42.ladder') => {
      answer = { schema: 'preceptoros.node-lifecycle/1', node, stages };
      await page.click('#tab-settings'); await page.click('#tab-ajustes'); // the owner coming back re-reads the backend
      await page.waitForFunction((re) => new RegExp(re).test(document.querySelector("#mvp-journey-guide .fold-teaser").textContent), expect.source, { timeout: 8000 }).catch(async (e) => { throw new Error("teaser: " + await teaser(page)); });
      const live = await page.$eval('#mvp-node-state', (e) => e.textContent);
      assert.equal(live, await teaser(page), 'eye, ear and machine say the same');
      return ladder(page);
    };
    const pending = { request: { state: 'PENDING', cause: 'aduana_receipt_awaiting_human' } };
    let l = await step({ ...pending, signature: { state: 'PENDING', cause: 'sshsig_awaited' } },
      /^Done: Request admission\. Stage 4 of 10 · Owner signature \(SSH\) · PENDING \(sshsig_awaited\)\. Needs a human SSH signature:/);
    assert.equal(l[1].s, 'done', 'a recorded request implies the consent given before it');
    l = await step({ ...pending, signature: M('sshsig_verified'), approval: { state: 'PENDING', cause: 'aduana_review' } },
      /Stage 5 of 10 · Admission approved · PENDING \(aduana_review\)\. Waiting for Aduana:/);
    l = await step({ ...pending, signature: M('sshsig_verified'), approval: M('admission_signed'), live: M('world_state_live') },
      /Stage 6 of 10 · Heartbeat verified · NO_DATA \(stage_missing_in_lifecycle\)\. Next \(you\): Start the node heartbeat/);
    assert.equal(l[6].c, 'earlier_stage_unverified', 'partial answer: LIVE not shown');
    l = await step({ ...pending, signature: M('sshsig_verified'), approval: M('admission_signed'), heartbeat: M('hb_fresh'), live: M('world_state_live') },
      /Stage 2 of 10 · Owner consent · NO_DATA/, 'nodo.99.other');
    assert.ok(l.slice(2).every((x) => x.s !== 'done'), 'another node\'s answer never advances this one');
    assert.equal(l[3].c, 'lifecycle_node_mismatch');
    l = await step({ ...pending, signature: M('sshsig_verified'), approval: { state: 'REFUSED', cause: 'plan_rejected' } },
      /Stage 5 of 10 · Admission approved · REFUSED \(plan_rejected\)\. Blocked \(plan_rejected\): Read the cause, then send a new request/);
    assert.equal(await page.$eval('#mvp-node-state', (e) => e.dataset.acho), 'REFUSED');
    l = await step({ ...pending, signature: M('sshsig_verified'), approval: { state: 'EXPIRED', cause: 'request_expired' } },
      /Stage 5 of 10 · Admission approved · EXPIRED \(request_expired\)\. Blocked \(request_expired\):/);
    assert.equal(await page.$eval('#mvp-node-state', (e) => e.dataset.acho), 'EXPIRED');
    l = await step({ ...pending, signature: M('sshsig_verified'), approval: { state: 'REVOKED', cause: 'd1_revocation_verified' },
      revoke: { state: 'REVOKED', cause: 'd1_revocation_verified' } },
      /Stage 3 of 10 · Request admission · NO_DATA \(node_revoked\)\. Blocked \(node_revoked\): Your node was revoked/);
    assert.equal(l[9].a, 'REVOKED'); assert.notEqual(l[9].s, 'done');
    assert.deepEqual(errors, []);
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
    rmSync(home, { recursive: true, force: true });
  }
});

// Real projection: Codex's node_lifecycle.read on a real APP server. The intake evidence is a FIXTURE written through
// Codex's own node_lifecycle.record_intake (the same store the real POST uses); no Chromium double for /api/nodo/estado.
test('My node reads the real /api/nodo/estado: stage 3 survives a reload, the signature stage names who acts', { timeout: 180000 }, async () => {
  const home = mkdtempSync(join(tmpdir(), 'preceptoros-node-ladder-'));
  const port = Number(process.env.NODE_LADDER_PORT || 18931) + 2;
  const url = 'http://127.0.0.1:' + port + '/app';
  const env = { ...process.env, HOME: home, PRECEPTOROS_HEXELION_ENDPOINT: '', PRECEPTOROS_PWA_BIND: '127.0.0.1', PRECEPTOROS_PWA_PUERTO: String(port) };
  delete env.PRECEPTOROS_OWNER_REVIEW_KEY_FILE;
  const child = spawn('python3', [join(ROOT, 'bin/preceptoros-pwa')], { cwd: ROOT, env, stdio: 'ignore' });
  let browser;
  try {
    let alive = false;
    for (let i = 0; i < 60 && !alive; i++) {
      try { const r = await fetch(url); alive = r.ok; await r.arrayBuffer(); } catch (_) { await new Promise((r) => setTimeout(r, 150)); }
    }
    assert.equal(alive, true, 'APP server up');
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
    const page = await (await browser.newContext({ viewport: { width: 390, height: 900 }, hasTouch: true })).newPage(), errors = [], posts = [];
    page.on('pageerror', (e) => errors.push(String(e)));
    page.on('request', (r) => { if (r.method() !== 'GET' && r.url().includes('/api/nodo/')) posts.push(r.url()); });
    await page.goto(url);
    await page.click('#tab-ajustes');
    await page.click('#mynode-identity-toggle');
    await page.fill('#node-identity-id', 'nodo.42.ladder');
    await page.check('#node-identity-consent');
    await page.click('#node-identity-save');
    await page.waitForFunction(() => /Stage 2 of 10 · Owner consent/.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
    const seed = spawn('python3', ['-c', [
      'import casa, node_lifecycle as L',
      'q={"schema":"preceptoros.deployment-request/1","node":"nodo.42.ladder","consent":True,"nonce":"a"*32,"device_sha256":"b"*64}',
      'r={"schema":"preceptoros.deployment-request-receipt/1","request_id":L._digest(q),"state":"AWAITING_HUMAN","received_at":"2026-11-21T18:59:55Z"}',
      'assert L.record_intake(casa.raiz(), q, r)'].join('\n')], { cwd: ROOT, env, stdio: 'inherit' });
    assert.equal(await new Promise((r) => seed.on('exit', r)), 0, 'fixture intake recorded through Codex store');
    posts.length = 0; // identity provisioning above is the one intended write
    for (const pass of ['opened', 'reloaded']) {
      if (pass === 'reloaded') { await page.reload(); await page.click('#tab-ajustes'); } else { await page.click('#tab-settings'); await page.click('#tab-ajustes'); }
      await page.waitForFunction(() => /^Done: Request admission\. Stage 4 of 10 · Owner signature \(SSH\) · NO_DATA \(signed_export_or_plan_unavailable\)\. Needs a human SSH signature: /.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent), null, { timeout: 8000 })
        .catch(async () => { throw new Error(pass + ' teaser: ' + await teaser(page)); });
      const server = await page.evaluate(async () => (await fetch('/api/nodo/estado', { cache: 'no-store' })).json());
      const l = await ladder(page);
      assert.equal(server.node, 'nodo.42.ladder');
      assert.deepEqual([l[2].a, l[2].c, l[2].s], [server.stages.request.state, server.stages.request.cause, 'done'], pass);
      for (const row of l.slice(3)) {
        const s = server.stages[row.k];
        assert.ok((row.a === s.state && row.c === s.cause) || row.c === 'earlier_stage_unverified', pass + ' ' + row.k + ' mirrors the server');
        assert.notEqual(row.s, 'done');
      }
      assert.equal(await page.$eval('#mvp-node-state', (e) => e.textContent), await teaser(page));
    }
    assert.deepEqual(posts, [], 'reading My node never writes'); assert.deepEqual(errors, []);
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
    rmSync(home, { recursive: true, force: true });
  }
});

// Create building on the real server and real #402 projection: consent alone no longer enables the declaration.
test('Create building waits for the backend lifecycle and names the first missing requirement', { timeout: 120000 }, async () => {
  const home = mkdtempSync(join(tmpdir(), 'preceptoros-node-ladder-'));
  const port = Number(process.env.NODE_LADDER_PORT || 18931) + 3;
  const url = 'http://127.0.0.1:' + port + '/app';
  const env = { ...process.env, HOME: home, PRECEPTOROS_HEXELION_ENDPOINT: '', PRECEPTOROS_PWA_BIND: '127.0.0.1', PRECEPTOROS_PWA_PUERTO: String(port) };
  const child = spawn('python3', [join(ROOT, 'bin/preceptoros-pwa')], { cwd: ROOT, env, stdio: 'ignore' });
  let browser;
  try {
    let alive = false;
    for (let i = 0; i < 60 && !alive; i++) {
      try { const r = await fetch(url); alive = r.ok; await r.arrayBuffer(); } catch (_) { await new Promise((r) => setTimeout(r, 150)); }
    }
    assert.equal(alive, true, 'APP server up');
    browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
    const page = await (await browser.newContext({ viewport: { width: 420, height: 900 }, hasTouch: true })).newPage(), declared = [];
    page.on('request', (r) => { if (r.url().endsWith('/api/nodo/edificio')) declared.push(r.method()); });
    await page.goto(url);
    await page.click('#tab-ajustes');
    await page.click('#mynode-identity-toggle');
    await page.fill('#node-identity-id', 'primer-ancla'); // the one node the server may declare a building for
    await page.check('#node-identity-consent');
    await page.click('#node-identity-save');
    await page.waitForFunction(() => !document.getElementById('node-building-consent').disabled);
    await page.focus('#node-declaration-advanced > summary'); await page.keyboard.press('Enter');
    await page.focus('#node-building-consent'); await page.keyboard.press('Space');
    assert.equal(await page.$eval('#node-building-consent', (b) => b.checked), true, 'consent ticked by keyboard');
    await page.waitForFunction(() => document.getElementById('node-building-status').dataset.cause === 'owner_identity_unverified');
    const st = await page.$eval('#node-building-status', (e) => ({ t: e.textContent, s: e.dataset.state, a: e.dataset.acho, role: e.getAttribute('role') }));
    assert.match(st.t, /^NO_DATA\(owner_identity_unverified\)\. Next: Finish stage 4/);
    assert.deepEqual([st.s, st.a, st.role], ['NO_DATA', 'NO_DATA', 'status']);
    assert.equal(await page.$eval('#node-building-submit', (b) => b.disabled), true, 'no declaration without an admitted node');
    await page.focus('#node-building-submit'); await page.keyboard.press('Enter');
    assert.deepEqual(declared, [], 'nothing sent to Aduana');
  } finally {
    if (browser) await browser.close();
    child.kill('SIGTERM');
    rmSync(home, { recursive: true, force: true });
  }
});
