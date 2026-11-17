/* APP-UX-GAP-CLOSE-01 · real Chromium layout and navigation checks.
 * The checkout's STATIC files only: /api/* intentionally 404, no rack DB.
 * Run: NODE_PATH=/home/pisky/p0x/node_modules node tests/app_ux_gap_close.browser.cjs
 */
'use strict';
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(process.env.PREVIEW_ROOT || path.resolve(__dirname, '..'));
const port = Number(process.env.PREVIEW_PORT || 18893);
const url = 'http://127.0.0.1:' + port + '/app.html';
async function ready(child) {
  for (let i = 0; i < 40; i++) {
    if (child.exitCode !== null) throw new Error('isolated preview quit');
    try { if ((await fetch(url)).ok) return; } catch (_) {}
    await new Promise((resolve) => setTimeout(resolve, 100));
  }
  throw new Error('isolated preview unavailable');
}
(async () => {
  const server = spawn('python3', ['-m', 'http.server', String(port), '--bind',
    '127.0.0.1', '--directory', path.join(root, 'interface')], { stdio: 'ignore' });
  let browser;
  try {
    await ready(server);
    browser = await chromium.launch({
      headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const results = [];
    for (const viewport of [{ width: 900, height: 968 },
                             { width: 420, height: 680 },
                             { width: 360, height: 640 }]) {
      const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
      const page = await context.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => !!window.PreceptorPanelFlow);
      // This is an intentionally unconfigured personal MVP, NOT the rack.
      const before = await page.evaluate(() => {
        const rect = (sel) => document.querySelector(sel).getBoundingClientRect();
        const tabs = [...document.querySelectorAll('.pestanas [role="tab"]')];
        return {
          empty: document.querySelector('#hilo').childElementCount === 0,
          panelPosition: getComputedStyle(document.querySelector('#panel-conversacion')).position,
          distance: rect('#form-chat').top - rect('#plan-escribir').bottom,
          labels: tabs.filter((t) => !t.dataset.mvp).map((t) => ({
            id: t.id, label: t.getAttribute('aria-label'),
            after: getComputedStyle(t, '::after').content,
          })),
          backHidden: document.querySelector('#technical-options-close')?.hidden ?? true,
          advancedHidden: tabs.filter((t) => t.dataset.mvp === 'advanced').every((t) => t.hidden),
        };
      });
      assert.equal(before.empty, true, 'fresh preview thread should be empty');
      assert.equal(before.panelPosition, 'relative', 'empty Talk must use normal flow');
      assert.ok(before.distance >= 0 && before.distance < 65,
        'Talk composer gap ' + before.distance + 'px at ' + viewport.width);
      assert.equal(before.labels.length, 4);
      for (const item of before.labels) {
        assert.ok(item.after.includes(item.label),
          item.id + ' should retain a visible label');
      }
      assert.equal(before.backHidden, true);
      assert.equal(before.advancedHidden, true);
      await page.locator('#technical-options-toggle').click();
      await page.locator('#technical-options-menu').waitFor({ state: 'visible' });
      const opened = await page.evaluate(() => ({
        backVisible: !document.querySelector('#technical-options-close').hidden,
        advancedVisible: [...document.querySelectorAll('[data-mvp="advanced"]')].every((t) => !t.hidden),
        expanded: document.querySelector('#technical-options-toggle').getAttribute('aria-expanded'),
      }));
      assert.equal(opened.backVisible, true);
      assert.equal(opened.advancedVisible, true);
      assert.equal(opened.expanded, 'true');
      await page.locator('#tech-opt-mando').click();
      assert.equal(await page.locator('#technical-options-menu').isHidden(), true);
      assert.equal(await page.locator('#technical-options-close').isVisible(), true,
        'back button must remain visible after closing popover');
      await page.locator('#technical-options-close').click();
      assert.equal(await page.locator('#technical-options-close').isHidden(), true);
      assert.equal(await page.locator('#tab-mando').isHidden(), true);
      assert.equal(await page.locator('#tab-ajustes').getAttribute('aria-selected'), 'true');
      assert.equal(await page.evaluate(() => document.activeElement.id), 'tab-ajustes');
      await page.locator('#technical-options-toggle').click();
      await page.locator('#technical-options-dismiss').click();
      assert.equal(await page.locator('#technical-options-close').isHidden(), true);
      assert.equal(await page.locator('#technical-options-menu').isHidden(), true);
      await page.locator('#tab-conversacion').click();
      await page.evaluate(() => {
        const li = document.createElement('li'); li.textContent = 'synthetic local reply';
        document.querySelector('#hilo').append(li);
      });
      const after = await page.evaluate(() => ({
        panelPosition: getComputedStyle(document.querySelector('#panel-conversacion')).position,
        flexGrow: getComputedStyle(document.querySelector('#carril')).flexGrow,
      }));
      assert.equal(after.panelPosition, 'absolute', 'chat resumes anchored mode after first turn');
      assert.equal(after.flexGrow, '1', 'full-height conversation restored with history');
      results.push({ viewport, initial_gap_px: Math.round(before.distance),
        labels: before.labels.map(x => x.label), technical_close: 'PASS',
        populated_thread_layout: 'PASS', static_api: 'NO_DATA(expected_no_backend)' });
      await context.close();
    }
    console.log(JSON.stringify({ schema: 'preceptoros.app-ux-gap-close/1',
      result: 'PASS', actual_browser: 'Chromium', assistive_reader: 'NO_DATA(not_run)',
      cases: results }, null, 2));
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
  }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
