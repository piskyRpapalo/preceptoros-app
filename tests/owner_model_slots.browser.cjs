/* APP-MODEL-SLOTS-01 · real Chromium first-run and privacy checks.
 * Local isolated file server; API 404 is expected and cannot verify a model.
 */
'use strict';
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const port = Number(process.env.PREVIEW_PORT || 18913);
const url = 'http://127.0.0.1:' + port + '/app.html';

async function ready(child) {
  for (let i = 0; i < 40; i++) {
    if (child.exitCode !== null) throw new Error('preview server died');
    try { if ((await fetch(url)).ok) return; } catch (_) {}
    await new Promise((r) => setTimeout(r, 80));
  }
  throw new Error('preview did not start');
}
(async () => {
  const server = spawn('python3', ['-m', 'http.server', String(port),
    '--bind', '127.0.0.1', '--directory', path.join(root, 'interface')], { stdio: 'ignore' });
  let browser;
  try {
    await ready(server);
    browser = await chromium.launch({ headless: true,
      executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'] });
    const cases = [];
    for (const viewport of [{ width: 900, height: 968 }, { width: 420, height: 680 }, { width: 360, height: 640 }]) {
      const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
      const page = await context.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => !!window.PreceptorOwnerModelSlots);
      await page.locator('#tab-ajustes').click();
      const rootId = '#owner-models';
      await page.locator(rootId).scrollIntoViewIfNeeded();
      assert.equal(await page.locator('#owner-models-status').getAttribute('data-state'), 'NO_DATA');
      assert.equal(await page.locator('#owner-private-status').getAttribute('data-state'), 'NO_DATA');
      assert.equal(await page.locator('#owner-public-status').getAttribute('data-acho'), 'NO_DATA');
      for (const selector of ['#owner-model-save', '#owner-model-clear', '#owner-model-export']) {
        const h = await page.locator(selector).evaluate((el) => el.getBoundingClientRect().height);
        assert.ok(h >= 44, selector + ' should be >=44px, got ' + h);
      }
      const scrollWidth = await page.evaluate(() =>
        document.getElementById('owner-models').scrollWidth -
        document.getElementById('owner-models').clientWidth);
      assert.ok(scrollWidth <= 3, 'model slots overflow at ' + viewport.width);
      await page.locator('#owner-private-runtime').selectOption('on_device');
      await page.locator('#owner-private-label').fill('Private 135M');
      await page.locator('#owner-public-runtime').selectOption('owner_managed');
      await page.locator('#owner-public-label').fill('Crab Guide');
      await page.locator('#owner-model-save').click();
      assert.equal(await page.locator('#owner-models-status').getAttribute('data-state'), 'DRAFT_ONLY');
      let json = JSON.parse(await page.locator('#owner-models-machine').textContent());
      assert.equal(json.private_chat_model.reply_state, 'NO_DATA');
      assert.equal(json.public_visitor_model.admission_state, 'NO_DATA');
      assert.equal(json.authority, 'NOT_AUTHORIZED');
      await page.locator('#owner-model-export').click();
      assert.equal(await page.locator('#owner-model-export-status').getAttribute('data-state'), 'NO_DATA');
      await page.locator('#owner-model-public-consent').check();
      await page.locator('#owner-model-export').click();
      assert.equal(await page.locator('#owner-model-export-status').getAttribute('data-state'), 'DRAFT_ONLY');
      const draft = await page.locator('#owner-model-public-draft').textContent();
      assert.ok(draft.includes('Crab Guide'));
      assert.ok(!draft.includes('Private 135M'), 'private model leaked into public declaration');
      assert.ok(!draft.includes('api_key'));
      assert.ok(!draft.includes('endpoint'));
      await page.reload({ waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => !!window.PreceptorOwnerModelSlots);
      await page.locator('#tab-ajustes').click();
      assert.equal(await page.locator('#owner-private-label').inputValue(), 'Private 135M');
      assert.equal(await page.locator('#owner-public-label').inputValue(), 'Crab Guide');
      assert.equal(await page.locator('#owner-models-status').getAttribute('data-state'), 'DRAFT_ONLY');
      await page.locator('#owner-private-label').fill('https://private.example:11434');
      await page.locator('#owner-model-save').click();
      assert.equal(await page.locator('#owner-models-status').getAttribute('data-state'), 'NO_DATA');
      const oldStored = await page.evaluate(() => localStorage.getItem(window.PreceptorOwnerModelSlots.storageKey));
      assert.ok(oldStored.includes('Private 135M') && !oldStored.includes('private.example'));
      await page.locator('#owner-model-clear').click();
      assert.equal(await page.locator('#owner-models-status').getAttribute('data-acho'), 'NO_DATA');
      assert.equal(await page.locator('#owner-public-label').inputValue(), '');
      assert.equal(await page.evaluate(() => localStorage.getItem(window.PreceptorOwnerModelSlots.storageKey)), null);
      cases.push({ viewport, slots: 'PASS', persistence: 'PASS', privacy: 'PASS',
        consent: 'PASS', a11y_focus_44px: 'PASS', model_E2E: 'NO_DATA(unconnected)' });
      await context.close();
    }
    console.log(JSON.stringify({ schema: 'preceptoros.app-model-slots-browser/1',
      result: 'PASS', engine: 'Chromium', network_model_turns: 0,
      real_assistive_reader: 'NO_DATA(not_run)', cases }, null, 2));
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
  }
})().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
