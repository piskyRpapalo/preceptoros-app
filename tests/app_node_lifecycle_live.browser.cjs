/* My node on the LIVE owner APP service (default http://127.0.0.1:8742/app; LIVE_APP_URL to change). Read-only:
 * every non-GET request to /api/ is aborted and counted, so this can never provision, request admission or sign.
 * It proves the shipped page shows exactly what the real GET /api/nodo/estado says, at 390/420/780 px.
 * Not part of ./bin/pruebas (it needs the running service); run it after each service update.
 */
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
let chromium;
try { ({ chromium } = require('playwright-core')); } catch (_) { ({ chromium } = require('playwright')); }
const URL_APP = process.env.LIVE_APP_URL || 'http://127.0.0.1:8742/app';

test('live service: My node mirrors the real lifecycle projection, no writes', { timeout: 120000 }, async (t) => {
  const origin = new URL(URL_APP).origin;
  const probe = await fetch(origin + '/api/nodo/estado').catch(() => null);
  if (!probe) return t.skip('NO_DATA(live_app_service_unreachable)');
  assert.equal(probe.status, 200, 'GET /api/nodo/estado deployed on the live service (404 = node_lifecycle_api_missing)');
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
  try {
    for (const width of [390, 420, 780]) {
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
      const page = await ctx.newPage(), blocked = [], errors = [];
      page.on('pageerror', (e) => errors.push(String(e)));
      await page.route('**/api/**', (route) => {
        if (route.request().method() === 'GET') return route.continue();
        blocked.push(route.request().method() + ' ' + new URL(route.request().url()).pathname); return route.abort();
      });
      await page.goto(URL_APP);
      await page.keyboard.press('Tab');
      await page.focus('#tab-ajustes'); await page.keyboard.press('Enter');
      await page.waitForFunction(() => document.querySelectorAll('#mvp-journey li[data-key]').length === 10 &&
        document.getElementById('mvp-node-state').textContent === document.querySelector('#mvp-journey-guide .fold-teaser').textContent);
      const server = await page.evaluate(async () => (await fetch('/api/nodo/estado', { cache: 'no-store' })).json());
      const identity = await page.evaluate(async () => (await fetch('/api/nodo/identity', { cache: 'no-store' })).json());
      assert.equal(server.schema, 'preceptoros.node-lifecycle/1');
      const rows = await page.$$eval('#mvp-journey li', (ls) => ls.map((l) => ({ k: l.dataset.key, s: l.dataset.state, a: l.dataset.acho, c: l.dataset.cause, actor: l.dataset.actor })));
      const view = await page.evaluate((ev) => { const f = window.PreceptorNodeRegistration; const v = f.lifecycle(ev); return { v, sentence: f.lifecycleSentence(v) }; },
        { identity: identity.estado === 'configurada' ? { state: 'MEASURED', node: identity.node_id } : { state: 'NO_DATA', cause: identity.causa }, lifecycle: server });
      // Eye, ear and machine: one sentence, and it is what the pure ladder makes of the real answers.
      const teaser = await page.$eval('#mvp-journey-guide .fold-teaser', (e) => e.textContent);
      const status = await page.$eval('#mvp-node-state', (e) => ({ t: e.textContent, a: e.dataset.acho, c: e.dataset.cause, role: e.getAttribute('role') }));
      assert.equal(teaser, view.sentence); assert.equal(status.t, teaser); assert.equal(status.role, 'status');
      assert.equal(status.a, view.v.stages[view.v.current].state); assert.equal(status.c, view.v.stages[view.v.current].cause);
      for (const row of rows.slice(3)) {
        const s = server.stages[row.k];
        assert.ok((row.a === s.state && row.c === s.cause) || row.c === 'earlier_stage_unverified', width + ' ' + row.k + ' mirrors the server');
      }
      assert.equal(rows.filter((r) => r.k === 'live' && r.s === 'done').length, server.stages.live.state === 'MEASURED' && view.v.live ? 1 : 0);
      assert.ok(rows.every((r) => ['you', 'aduana', 'signature'].includes(r.actor)));
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'no horizontal scroll ' + width);
      assert.deepEqual(blocked, []); assert.deepEqual(errors, []);
      t.diagnostic(width + ' · ' + teaser);
      await ctx.close();
    }
  } finally { await browser.close(); }
});
