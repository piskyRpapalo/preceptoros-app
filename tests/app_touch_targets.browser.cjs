/* Round 5 · 44 px touch targets · real Chromium on the real interface/app.html (served under the APK origin; /api/*
 * unanswered). Every section of Operations Data, Lab and My node is opened and every visible control is measured at
 * 390/420/780 px. A checkbox counts through its label. Found on the live Beelink APP on 2026-11-21: 13–24 px targets.
 */
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { resolve, extname } = require('node:path');
let chromium;
try { ({ chromium } = require('playwright-core')); } catch (_) { ({ chromium } = require('playwright')); }
const ROOT = resolve(__dirname, '..');
const TYPES = { '.js': 'text/javascript', '.css': 'text/css', '.html': 'text/html', '.json': 'application/json', '.png': 'image/png', '.svg': 'image/svg+xml' };

for (const width of [390, 420, 780]) {
  test('every visible control is at least 44 px tall · ' + width, { timeout: 90000 }, async () => {
    const browser = await chromium.launch({ headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome' });
    try {
      const ctx = await browser.newContext({ viewport: { width, height: 900 }, hasTouch: true });
      await ctx.route('**/*', async (route) => {
        const u = new URL(route.request().url());
        if (u.origin !== 'https://preceptoros.mvp.local' || u.pathname.startsWith('/api/')) return route.abort();
        const path = u.pathname === '/' ? '/app.html' : u.pathname;
        const file = path === '/offline_mini.js' ? resolve(ROOT, 'mvp-android/offline_mini.js') : resolve(ROOT, 'interface', '.' + path);
        try { await route.fulfill({ status: 200, body: readFileSync(file), contentType: TYPES[extname(file)] || 'text/plain' }); }
        catch (_) { await route.fulfill({ status: 404, body: '' }); }
      });
      const page = await ctx.newPage();
      await page.goto('https://preceptoros.mvp.local/app.html');
      const short = {};
      for (const panel of ['cuaderno', 'lab', 'ajustes']) {
        await page.click('#tab-' + panel);
        await page.evaluate((p) => { document.querySelectorAll('#panel-' + p + ' details').forEach((d) => { d.open = true; }); }, panel);
        await page.waitForTimeout(300);
        short[panel] = await page.evaluate((p) => {
          const vis = (e) => { const r = e.getBoundingClientRect(); return r.width > 0 && r.height > 0 && getComputedStyle(e).visibility !== 'hidden'; };
          return [...document.querySelectorAll('#panel-' + p + ' button, #panel-' + p + ' a[href], #panel-' + p + ' select, #panel-' + p + ' summary, #panel-' + p + ' input[type=checkbox]')]
            .filter(vis).filter((e) => {
              const h = (e.type === 'checkbox' && e.closest('label') ? e.closest('label') : e).getBoundingClientRect().height;
              return h < 43.5;
            }).map((e) => (e.id || e.className || e.tagName) + ':' + Math.round(e.getBoundingClientRect().height));
        }, panel);
      }
      assert.deepEqual(short, { cuaderno: [], lab: [], ajustes: [] });
      assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false, 'no horizontal scroll');
    } finally { await browser.close(); }
  });
}
