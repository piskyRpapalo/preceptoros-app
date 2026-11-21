/* My node lifecycle · real Chromium on the real APP server (bin/preceptoros-pwa, isolated temporary HOME).
 * Real: identity read, local identity provisioning, ladder painting, keyboard, 44 px, widths 390/420/780.
 * SYNTHETIC: the consented intake POST is answered by the test inside the page (route), because the server forwards
 * it to production Aduana; a real request must come from a person's consent, not from CI.
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
      await page.waitForFunction(() => /^Stage 2 of 10 · Owner consent/.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
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
      assert.match(await teaser(page), /^Stage 3 of 10 · Request admission/);
      const box = await page.$eval('#node-registration-submit', (b) => { const r = b.getBoundingClientRect(); return [r.width, r.height]; });
      assert.ok(box[1] >= 44, 'request button ≥ 44 px tall: ' + box);
      await page.focus('#node-registration-submit'); await page.keyboard.press('Enter');
      await page.waitForFunction(() => /^Stage 4 of 10 · Owner signature \(SSH\) · NO_DATA \(node_lifecycle_api_missing\)\. Next: The owner signs/.test(document.querySelector('#mvp-journey-guide .fold-teaser').textContent));
      l = await ladder(page);
      assert.equal(l[2].a, 'PENDING'); assert.equal(l[2].s, 'done');
      for (const later of l.slice(3)) assert.notEqual(later.s, 'done', later.k + ' must not be claimed');
      assert.equal(intake.length, 1);
      assert.deepEqual(Object.keys(intake[0]).sort(), ['consent', 'esquema', 'node', 'nonce']);
      // The same sentence for eye (teaser), screen reader (live status) and machine (data-*).
      const live = await page.$eval('#mvp-node-state', (e) => ({ t: e.textContent, s: e.dataset.state, c: e.dataset.cause, role: e.getAttribute('role') }));
      assert.equal(live.t, await teaser(page)); assert.equal(live.s, 'NO_DATA'); assert.equal(live.c, 'node_lifecycle_api_missing'); assert.equal(live.role, 'status');
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
