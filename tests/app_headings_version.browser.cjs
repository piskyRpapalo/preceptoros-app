/* Round 2 · Objective 4 · real Chromium on the real interface/app.html (served under the APK origin, /api/* unanswered
 * unless a case says otherwise). Five duplicate panel titles are visually gone but remain the accessible h2 of each
 * tab panel; Talk is untouched; Settings names the product release only from a verifiable source.
 * The Android version bridge and the Beelink /api/estado answer are TEST DOUBLES with the shapes the page already reads.
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
const PANELS = [['cuaderno', 'notebook-title', 'Operations Data'], ['lab', 'h-lab', 'Lab'], ['modelos', 'h-modelos', 'Open World'],
  ['ajustes', 'h-ajustes', 'My node'], ['settings', 'h-settings', 'Settings']];

async function open(browser, width, { nativeVersion = null, estado = null } = {}) {
  const ctx = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
  await ctx.route('**/*', async (route) => {
    const u = new URL(route.request().url());
    if (u.origin !== 'https://preceptoros.mvp.local') return route.abort();
    if (u.pathname === '/api/estado' && estado) return route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify(estado) });
    if (u.pathname.startsWith('/api/')) return route.abort('connectionrefused');
    const path = u.pathname === '/' ? '/app.html' : u.pathname;
    const file = path === '/offline_mini.js' ? resolve(ROOT, 'mvp-android/offline_mini.js') : resolve(ROOT, 'interface', '.' + path);
    try { await route.fulfill({ status: 200, body: readFileSync(file), contentType: TYPES[extname(file)] || 'text/plain' }); }
    catch (_) { await route.fulfill({ status: 404, body: '' }); }
  });
  if (nativeVersion) await ctx.addInitScript(`window.PreceptorAndroidMiniModel = { version() { return ${JSON.stringify(nativeVersion)}; }, generate() { return ''; } };`);
  const page = await ctx.newPage();
  await page.goto('https://preceptoros.mvp.local/app.html');
  await page.waitForFunction(() => document.getElementById('settings-version'));
  return { ctx, page };
}
const launch = () => chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });

for (const width of [390, 420, 780]) {
  test('five duplicate titles: invisible, no orphan space, still the accessible name · ' + width, { timeout: 90000 }, async () => {
    const browser = await launch();
    try {
      const { page } = await open(browser, width);
      for (const [panel, h2, name] of PANELS) {
        await page.click('#tab-' + panel);
        const m = await page.$eval('#panel-' + panel, (p, h2) => {
          const h = document.getElementById(h2), header = h.closest('header'), r = header.getBoundingClientRect();
          const first = [...p.children].find((c) => c !== header && !c.hidden && getComputedStyle(c).display !== 'none' && getComputedStyle(c).position !== 'absolute');
          return { tag: h.tagName, text: h.textContent.trim(), area: r.width * r.height, labelledby: p.getAttribute('aria-labelledby'),
            gap: first ? first.getBoundingClientRect().top - p.getBoundingClientRect().top : null, hidden: h.hidden || h.getAttribute('aria-hidden') };
        }, h2);
        assert.equal(m.tag, 'H2'); assert.equal(m.text, name); assert.equal(m.hidden, null);
        assert.ok(m.area <= 1, panel + ' header has no visual area: ' + m.area);
        assert.ok(m.gap !== null && m.gap < 40, panel + ' no orphan space above first block: ' + m.gap);
        assert.equal(m.labelledby, 'tab-' + panel, 'tab keeps naming the panel');
        const snap = await page.locator('#panel-' + panel).ariaSnapshot();
        assert.match(snap, new RegExp('heading "' + name + '" \\[level=2\\]'), panel + ' h2 in the accessibility tree');
      }
      await page.click('#tab-conversacion');
      assert.equal(await page.$eval('#h-conversacion', (h) => h.closest('header').classList.contains('sr')), false, 'Talk header unchanged');
      assert.equal(await page.$eval('#superbot-title', (h) => h.getBoundingClientRect().height > 0), true, 'Talk visible title unchanged');
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    } finally { await browser.close(); }
  });
}

test('Settings names the release only from a verifiable source; one live announcement', { timeout: 90000 }, async () => {
  const browser = await launch();
  try {
    const cases = [
      [{ nativeVersion: 'v7 · 0.3.0-mvp' }, 'PreceptorOS APP 1.0 · Android build 7', 'MEASURED'],
      [{ nativeVersion: 'v8 · 0.3.1-mini-recovery' }, 'PreceptorOS APP 1.1 · Android build 8', 'MEASURED'],
      [{ nativeVersion: 'v9 · 0.4.0' }, 'PreceptorOS APP · Android build 9 · NO_DATA(release_not_named)', 'NO_DATA'],
      [{ estado: { estado: 'ok', turnos: {}, version: { huella: 'a1b2c3d4e5f6', faltan: [] } } },
        'PreceptorOS APP · Shell a1b2c3d4e5f6 · NO_DATA(release_manifest_unverified)', 'NO_DATA'],
      [{}, 'PreceptorOS APP · NO_DATA(release_manifest_unverified)', 'NO_DATA'],
    ];
    for (const [opts, text, state] of cases) {
      const { page, ctx } = await open(browser, 420, opts);
      await page.click('#tab-settings');
      await page.waitForFunction((t) => document.getElementById('settings-version').textContent === t, text, { timeout: 8000 });
      const v = await page.$eval('#settings-version', (e) => ({ s: e.dataset.state, a: e.dataset.acho, role: e.getAttribute('role'), live: e.getAttribute('aria-live'), h: e.getBoundingClientRect().height }));
      assert.equal(v.s, state); assert.equal(v.a, state);
      assert.equal(v.role, null); assert.equal(v.live, null); // the Talk version line is the only live one
      assert.ok(v.h > 0, 'visible in Settings');
      if (opts.estado) assert.doesNotMatch(text, /1\.[01]/, 'a shell fingerprint never names a release');
      await ctx.close();
    }
  } finally { await browser.close(); }
});
