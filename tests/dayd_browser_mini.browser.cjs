/* APP-DAYD-MINI-01 · real browser test of opt-in mini on the APP PWA server.
 * Isolated process + temporary home. It cannot contact a rack model.
 * Requires playwright-core and Chromium on the executing host.
 */
'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const { mkdtempSync, rmSync } = require('node:fs');
const { tmpdir } = require('node:os');
const { join, resolve } = require('node:path');
const { chromium } = require('playwright-core');

test('opt-in mini provides local closed intents at desktop and mobile sizes', { timeout: 90000 }, async () => {
  const root = resolve(__dirname, '..');
  const home = mkdtempSync(join(tmpdir(), 'preceptoros-dayd-mini-'));
  const port = Number(process.env.MINI_BROWSER_PORT || 18923);
  const url = 'http://127.0.0.1:' + port + '/app';
  const child = spawn('python3', [join(root, 'bin/preceptoros-pwa')], {
    cwd: root,
    env: { ...process.env, HOME: home, PRECEPTOROS_HEXELION_ENDPOINT: '',
      PRECEPTOROS_PWA_BIND: '127.0.0.1', PRECEPTOROS_PWA_PUERTO: String(port) },
    stdio: 'ignore',
  });
  let browser;
  try {
    let alive = false;
    for (let i=0; i<45; i++) {
      if (child.exitCode !== null) throw Error('PWA died');
      try {
        const r = await fetch(url);
        alive = r.ok;
        if (alive) break;
      } catch (_) {}
      await new Promise(r=>setTimeout(r,100));
    }
    assert.equal(alive, true);
    assert.equal((await fetch('http://127.0.0.1:'+port+'/offline_mini.js?v=1')).status, 200);
    browser = await chromium.launch({
      headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
      args: ['--no-sandbox','--disable-dev-shm-usage'],
    });
    for (const viewport of [{ width: 900, height: 968 }, { width: 420, height: 680 }, { width: 360, height: 640 }]) {
      const context = await browser.newContext({ viewport, serviceWorkers: 'block' });
      const page = await context.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => window.PreceptorOfflineMini &&
        window.PreceptorProfile === 'personal_mvp');
      const toggle = page.locator('#mini-local-toggle');
      const showMiniControl = async () => {
        if (await page.locator('#modelos-menu').isHidden()) {
          await page.locator('#modelos-toggle').click();
        }
        assert.equal(await page.locator('#mini-local-toggle').isVisible(),true);
      };
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      assert.equal(await page.locator('#mini-local-mode-status').getAttribute('data-state'), 'NO_DATA');
      await showMiniControl();
      assert.ok(await toggle.evaluate(e=>e.getBoundingClientRect().height)>=44);
      await page.keyboard.press('Escape'); // close existing picker before the ordinary Talk request
      let apiRequests = 0, privatePosts = 0, foreignPosts = 0;
      page.on('request', r => {
        const u = new URL(r.url());
        if (/\/api\/(charla|hexelion\/chat|conversacion)(?:\?|$)/.test(u.pathname)) apiRequests++;
        if (r.method() === 'POST') {
          if (u.pathname === '/api/hexelion/chat') privatePosts++;
          if (u.origin !== new URL(url).origin) foreignPosts++;
        }
      });
      // Default personal_mvp WITHOUT a model must finish with NO_DATA,
      // not contact a private Hexelion or hang indefinitely.
      await page.locator('#dicho').fill('Write an unprovided poem about a red star');
      const pendingLocal = page.waitForResponse(r =>
        new URL(r.url()).pathname === '/api/charla', {timeout:8000});
      await page.locator('#enviar').click();
      const localReply = await pendingLocal;
      const localData = await localReply.json();
      assert.notEqual(localData?.estado, 'ok', 'an absent model is not a model reply');
      await page.waitForFunction(() => {
        const t=document.querySelector('#estado');
        return t?.dataset?.state === 'NO_DATA' &&
          t.textContent?.includes('NO_DATA');
      });
      assert.equal(privatePosts,0,'fresh personal profile must not post to rack model');
      assert.equal(foreignPosts,0,'no phone-home from personal browser');
      const baselineRequests = apiRequests;
      await showMiniControl();
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
      assert.equal(await page.locator('#mini-local-mode-status').getAttribute('data-acho'), 'DRAFT_ONLY');
      await page.keyboard.press('Escape');
      await page.locator('#dicho').fill('hola');
      await page.locator('#enviar').click();
      await page.waitForFunction(() =>
        document.querySelector('#hilo')?.textContent?.includes('Soy MINI-LOCAL'));
      assert.equal(apiRequests,baselineRequests,'mini must not POST to model/backend');
      await page.locator('#dicho').fill('Escribe un poema sobre una rana');
      await page.locator('#enviar').click();
      await page.waitForFunction(() =>
        document.querySelector('#hilo')?.textContent?.includes('NO_DATA(on_device_model_unavailable)'));
      assert.equal(apiRequests,baselineRequests,'unknown prompt must fail closed in mini mode');
      // Emoji fit the textarea's 600 UTF-16 units but exceed 1023 UTF-8
      // bytes. They must not be truncated into a valid "open lab" intent.
      const oversize = 'open lab ' + '🌱'.repeat(280);
      await page.locator('#dicho').fill(oversize);
      await page.locator('#enviar').click();
      assert.equal(await page.locator('#offline-mini-status').getAttribute('data-cause'),'input_oversize');
      assert.equal(await page.locator('#offline-mini-status').getAttribute('data-acho'),'NO_DATA');
      assert.equal(await page.locator('#dicho').inputValue(),oversize,'rejected text remains editable');
      assert.equal(await page.locator('#tab-lab').getAttribute('aria-selected'),'false',
        'oversize input must not be truncated into navigation');
      assert.equal(apiRequests,baselineRequests,'oversize must not contact a backend');
      await showMiniControl();
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      assert.equal(await page.locator('#mini-local-mode-status').getAttribute('data-acho'), 'NO_DATA');
      await page.keyboard.press('Escape');
      // When the owner turns mini off, the existing Chat backend must be
      // reachable again (its response can still be NO_DATA without a GGUF).
      await page.locator('#dicho').fill('hello');
      const backToModel = page.waitForRequest((r) => {
        const path = new URL(r.url()).pathname;
        return path === '/api/charla' || path === '/api/hexelion/chat';
      }, { timeout: 6000 });
      await page.locator('#enviar').click();
      await backToModel;
      assert.ok(apiRequests > baselineRequests, 'turning mini off must restore the regular Chat path');
      const requestsAfterModel = apiRequests;
      await page.evaluate(() => { window.PreceptorProfile='private_rack'; });
      await showMiniControl();
      await toggle.click();
      assert.equal(await toggle.getAttribute('aria-pressed'), 'false');
      assert.equal(await page.locator('#mini-local-mode-status').getAttribute('data-cause'), 'rack_profile_read_only');
      // Keyboard activation of the toggle must behave like a click.
      await page.evaluate(() => { window.PreceptorProfile='personal_mvp'; });
      await toggle.focus();
      await page.keyboard.press('Enter');
      assert.equal(await toggle.getAttribute('aria-pressed'), 'true');
      const state=await page.locator('#mini-local-mode-status').evaluate(el=>({
        state:el.dataset.state, acho:el.dataset.acho, text:el.textContent,
      }));
      assert.equal(state.state,'DRAFT_ONLY');
      assert.equal(state.acho,'DRAFT_ONLY');
      assert.ok(state.text.includes('deterministic routing only. No external model, network or tools.'));
      assert.equal(privatePosts,0,'no private chat POST on this fresh personal client');
      assert.equal(foreignPosts,0,'no non-local POST from this fresh personal client');
      console.log(JSON.stringify({viewport, mini: 'PASS', local_backend_requests:apiRequests,
        private_posts:privatePosts, foreign_posts:foreignPosts, fresh_missing_model:'NO_DATA',
        unknown_prompt:'NO_DATA', keyboard:'PASS', rack_guard:'PASS',
        model_generation:'NO_DATA(not_packaged_in_browser)'}));
      await context.close();
    }
  } finally {
    if(browser) await browser.close();
    child.kill('SIGTERM');
    rmSync(home,{recursive:true,force:true});
  }
});
