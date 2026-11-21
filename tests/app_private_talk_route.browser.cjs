/* ONLINE3 · real Chromium test of the Talk route selector (interface/browser_mini_gate.js).
 * The real interface/app.html is served under the APK origin https://preceptoros.mvp.local with /api/* unanswered,
 * as WebViewAssetLoader does. The two Android bridges are TEST DOUBLES that follow the written contracts
 * (offline_mini.js generate(); odd/tasks/online3-private-talk.md postMessage {id,op[,texto]} → {id,result}).
 * This proves the page's behaviour, NOT the physical APK, the Tailscale link or a Hexelion inference.
 * Requires playwright-core (or playwright) and Chromium: CHROME_PATH or /usr/bin/google-chrome.
 */
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve, extname } = require('node:path');
let chromium;
try { ({ chromium } = require('playwright-core')); } catch (_) { ({ chromium } = require('playwright')); }

const ROOT = resolve(__dirname, '..');
const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json',
  '.png': 'image/png', '.svg': 'image/svg+xml', '.webmanifest': 'application/manifest+json' };

function doubles(withPrivate) {
  return `(() => {
    window.__sent = []; window.__local = 0; window.__offline = false; window.__configured = false;
    window.PreceptorAndroidMiniModel = { generate(t) { window.__local++; return 'local answer to ' + t; } };
    if (!${withPrivate}) return;
    const listeners = [];
    const reply = (id, result) => setTimeout(() => listeners.forEach(f => f({ data: JSON.stringify({ id, result }) })), 30);
    window.PreceptorPrivateTalkNative = {
      addEventListener(type, f) { if (type === 'message') listeners.push(f); },
      postMessage(raw) {
        const m = JSON.parse(raw); window.__sent.push(m);
        if (!/^[a-f0-9]{32}$/.test(m.id)) return;
        if (m.op === 'configure') { window.__configured = true; return reply(m.id, { estado: 'NO_DATA', stage: 'authentication', causa: 'private_talk_auth_unverified' }); }
        if (m.op === 'status') return reply(m.id, window.__configured
          ? { estado: 'NO_DATA', stage: 'authentication', causa: 'private_talk_auth_unverified' }
          : { estado: 'NO_DATA', stage: 'connection', causa: 'private_talk_serve_not_configured' });
        if (m.op === 'send') return reply(m.id, window.__offline
          ? { estado: 'NO_DATA', stage: 'connection', causa: 'private_talk_unreachable' }
          : { estado: 'MEASURED', respuesta: { estado: 'MEASURED', voz: 'hexelion', texto: 'private answer',
              fuentes: ['doc:1'], maquina: { modelo: 'hexelion:latest', ms: 2915 } } });
      },
    };
  })();`;
}

async function open(browser, withPrivate, size) {
  const ctx = await browser.newContext({ viewport: size, hasTouch: true });
  const external = [];
  await ctx.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.origin !== 'https://preceptoros.mvp.local') { external.push(u.origin); return route.abort(); }
    if (u.pathname.startsWith('/api/')) return route.abort('connectionrefused');
    let path = u.pathname === '/' ? '/app.html' : u.pathname;
    const file = path === '/offline_mini.js' ? resolve(ROOT, 'mvp-android/offline_mini.js') : resolve(ROOT, 'interface', '.' + path);
    try { await route.fulfill({ status: 200, body: readFileSync(file), contentType: TYPES[extname(file)] || 'text/plain' }); }
    catch (_) { await route.fulfill({ status: 404, body: '' }); }
  });
  await ctx.addInitScript(doubles(withPrivate));
  const page = await ctx.newPage();
  await page.goto('https://preceptoros.mvp.local/app.html');
  await page.waitForFunction(() => document.getElementById('form-chat') && window.PreceptorOfflineMini);
  return { ctx, page, external };
}
const lastRow = (page) => page.$eval('#hilo li:last-child', (li) => ({ text: li.textContent, state: li.dataset.state, source: li.dataset.source }));
const statusOf = (page) => page.$eval('#private-talk-status', (e) => ({ text: e.textContent, ...e.dataset }));
async function say(page, text) {
  await page.fill('#dicho', text);
  await page.click('#enviar');
}

test('without the OWNER bridge (signed v7 / public) nothing changes', { timeout: 60000 }, async () => {
  const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
  try {
    const { page, external } = await open(browser, false, { width: 412, height: 900 });
    assert.equal(await page.$('#private-talk-switch'), null);
    assert.match(await page.$eval('#modelos-toggle span', (e) => e.textContent), /Choose model/);
    await say(page, 'why is the sea salty');
    await page.waitForFunction(() => window.__local === 1);
    assert.equal((await lastRow(page)).source, 'smollm2_135m_on_device');
    assert.deepEqual(external, []);
  } finally { await browser.close(); }
});

for (const size of [{ width: 412, height: 900 }, { width: 1280, height: 900 }]) {
  test('OWNER bridge: local default, explicit private, offline keeps words and Local Mini answers · ' + size.width, { timeout: 90000 }, async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
    try {
      const { page, external } = await open(browser, true, size);
      const events = [];
      await page.exposeFunction('__acho', (d) => events.push(d));
      await page.evaluate(() => document.addEventListener('acho:event', (e) => window.__acho(e.detail)));
      // Default: Local Mini, the private bridge is not used.
      assert.equal(await page.$eval('#private-talk-toggle', (b) => b.getAttribute('aria-pressed')), 'false');
      assert.equal(await page.$eval('#modelos-toggle span', (e) => e.textContent), 'Model · Local Mini');
      await say(page, 'why is the sea salty');
      await page.waitForFunction(() => window.__local === 1);
      assert.equal(await page.evaluate(() => window.__sent.filter((m) => m.op === 'send').length), 0);

      // Explicit choice, through the existing Choose model dialog; keyboard reachable, 44 px.
      await page.click('#modelos-toggle');
      const box = await page.$eval('#private-talk-toggle', (b) => { const r = b.getBoundingClientRect(); return [r.width, r.height]; });
      assert.ok(box[0] >= 44 && box[1] >= 44, 'toggle ≥ 44 px: ' + box);
      await page.focus('#private-talk-toggle');
      await page.keyboard.press('Space');
      assert.equal(await page.$eval('#private-talk-toggle', (b) => b.getAttribute('aria-pressed')), 'true');
      assert.equal(await page.$eval('#modelos-toggle span', (e) => e.textContent), 'Model · Private Hexelion');
      await page.waitForFunction(() => document.getElementById('private-talk-status').dataset.cause === 'private_talk_serve_not_configured');
      await page.click('#private-talk-configure');
      await page.waitForFunction(() => document.getElementById('private-talk-status').dataset.cause === 'private_talk_auth_unverified');
      assert.equal((await statusOf(page)).state, 'NO_DATA', 'a saved address is not a verified link');
      await page.keyboard.press('Escape');

      // Private turn: one send with a 32-hex id and only {id,op,texto}; MEASURED with model, time and sources.
      await say(page, 'dos');
      await page.waitForFunction(() => document.getElementById('private-talk-status').dataset.state === 'MEASURED', null, { timeout: 8000 })
        .catch(async (e) => { console.log('DEBUG', JSON.stringify(await statusOf(page)), JSON.stringify(await lastRow(page)), JSON.stringify(await page.evaluate(() => window.__sent))); throw e; });
      const sent = await page.evaluate(() => window.__sent.filter((m) => m.op === 'send'));
      assert.equal(sent.length, 1);
      assert.deepEqual(Object.keys(sent[0]).sort(), ['id', 'op', 'texto']);
      assert.match(sent[0].id, /^[a-f0-9]{32}$/);
      const measured = await lastRow(page);
      assert.match(measured.text, /^Hexelion · private orchestrator · private answer$/);
      assert.equal(measured.state, 'MEASURED');
      const st = await statusOf(page);
      assert.equal(st.acho, 'ok');
      assert.match(st.text, /hexelion:latest · 2915 ms · 1 sources\. Not your on-device model\./);
      assert.equal(await page.evaluate(() => window.__local), 1, 'local model not called for a private turn');
      assert.ok(events.some((e) => e.id === 'talk/private-route' && e.state === 'MEASURED'), 'acho:event carries the same state');

      // Network lost: NO_DATA(connection), words kept, nothing invented.
      await page.evaluate(() => { window.__offline = true; });
      await say(page, 'tres');
      await page.waitForFunction(() => document.getElementById('private-talk-status').dataset.stage === 'connection' &&
        document.getElementById('private-talk-status').dataset.cause === 'private_talk_unreachable');
      assert.equal(await page.$eval('#dicho', (t) => t.value), 'tres');
      assert.equal((await lastRow(page)).state, 'NO_DATA');

      // Back to Local Mini: answers on the device while the private link is down.
      await page.click('#modelos-toggle');
      await page.click('#private-talk-toggle');
      await page.keyboard.press('Escape');
      await page.click('#enviar');
      await page.waitForFunction(() => window.__local === 2);
      assert.equal((await lastRow(page)).source, 'smollm2_135m_on_device');
      assert.deepEqual(external, [], 'no request leaves the APK origin from the page');
    } finally { await browser.close(); }
  });
}
