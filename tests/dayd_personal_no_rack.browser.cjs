/* DAY-D PERSONAL BRIDGE GATE
 * Adversarial real-Chrome test: a private-mode server MUST NOT induce an
 * unconfigured personal_mvp client to POST a question to the rack door.
 * Uses a local fake server and synthetic text. No real model/rack contacted.
 * This is client routing safety, NOT authorization: server still owns auth.
 */
'use strict';
const assert = require('node:assert/strict');
const { createServer } = require('node:http');
const { readFileSync } = require('node:fs');
const { resolve, extname, sep } = require('node:path');
const { chromium } = require('playwright-core');

const root = resolve(__dirname, '../interface');
const types = {
  '.html': 'text/html; charset=utf-8',
  '.js': 'application/javascript',
  '.css': 'text/css',
  '.json': 'application/json',
  '.png': 'image/png',
  '.svg': 'image/svg+xml',
  '.webmanifest': 'application/manifest+json',
};
const state = { talkMode: 'private_hexelion', privatePosts: 0,
  localPosts: 0, sharedPosts: 0, sharedGets: 0, readRequests: 0,
  identityOk: false };
const server = createServer((req, res) => {
  const pathname = new URL(req.url, 'http://local').pathname;
  const json = (status, value) => {
    const data = Buffer.from(JSON.stringify(value));
    res.writeHead(status, {
      'Content-Type': 'application/json; charset=utf-8',
      'Content-Length': data.length,
      'Cache-Control': 'no-store',
    });
    res.end(data);
  };
  if (pathname.startsWith('/api/')) {
    if (req.method === 'POST') {
      if (pathname === '/api/hexelion/chat') state.privatePosts++;
      if (pathname === '/api/charla') state.localPosts++;
      if (pathname === '/api/conversacion') state.sharedPosts++;
      // Do not persist user text even in this synthetic fixture.
      req.resume();
      return json(503, { estado: 'NO_DATA', causa: 'synthetic_local_fixture_only' });
    }
    state.readRequests++;
    if (pathname === '/api/conversacion') state.sharedGets++;
    if (pathname === '/api/cerebro') {
      return json(200, { estado: 'ok', talk_mode: state.talkMode });
    }
    if (pathname === '/api/perfil') {
      // A real installation uses identidad.huella (pseudonym, not credential).
      // The synthetic identity never grants server-side permission.
      return state.identityOk
        ? json(200, { estado:'ok', identidad: { estado:'ok', huella:'a'.repeat(64) } })
        : json(200, { estado:'NO_DATA', identidad: { estado:'NO_DATA', causa:'fixture_absent' } });
    }
    if (pathname === '/api/conversacion') {
      return json(200, {schema:'preceptoros.multipreceptor/1',
        state:'NO_DATA', cause:'no_authenticated_thread'});
    }
    return json(503, { estado: 'NO_DATA', causa: 'not_available_in_fixture' });
  }
  if (req.method !== 'GET') {
    res.writeHead(405); res.end(); return;
  }
  try {
    const file = resolve(root, '.' + (pathname === '/' ? '/app.html' : pathname));
    if (file !== root && !file.startsWith(root + sep)) {
      res.writeHead(403); res.end(); return;
    }
    const data = readFileSync(file);
    res.writeHead(200, {
      'Content-Type': types[extname(file)] || 'application/octet-stream',
      'Cache-Control': 'no-store', 'Content-Length': data.length,
    });
    res.end(data);
  } catch (_) {
    res.writeHead(404); res.end();
  }
});

const wait = (ms) => new Promise(resolveWait => setTimeout(resolveWait, ms));
(async () => {
  await new Promise(ok => server.listen(0, '127.0.0.1', ok));
  let browser;
  try {
    browser = await chromium.launch({
      executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
      headless: true, args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const url = 'http://127.0.0.1:' + server.address().port + '/app.html';
    const cases = [];
    for (const mode of ['private_hexelion', 'local_gguf']) {
      state.talkMode = mode;
      state.identityOk = false;
      state.privatePosts = state.localPosts = state.sharedPosts = state.sharedGets = 0;
      const ctx = await browser.newContext({
        viewport: {width: 360, height: 640}, serviceWorkers:'block',
      });
      const page = await ctx.newPage();
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => window.PreceptorProfile === 'personal_mvp',
        null, {timeout:5000});
      const radio = await page.locator('input[value="personal_mvp"]').isChecked();
      assert.equal(radio, true, 'the fresh profile must be personal_mvp');
      const speaker = await page.locator('#conv-interlocutor-type').textContent();
      assert.match(speaker, /not Hexelion/,
        'a personal mini cannot introduce itself as the founder private brain');
      // Personal profile must not READ or WRITE the private shared thread,
      // even if a previously cached destination points at an operator.
      const sharedBefore = state.sharedGets;
      const syncResult = await page.evaluate(() => window.PreceptorConversacion.sync());
      const sharedSend = await page.evaluate(() =>
        window.PreceptorConversacion.send('claude', 'synthetic not for rack'));
      assert.equal(syncResult.cause, 'personal_profile_shared_thread_denied');
      assert.equal(sharedSend.cause, 'personal_profile_shared_thread_denied');
      assert.equal(state.sharedPosts, 0, 'no shared-thread submission');
      assert.equal(state.sharedGets, sharedBefore, 'no shared-thread fetch in personal mode');
      const text = 'synthetic browser no rack request';
      await page.locator('#dicho').fill(text);
      await page.locator('#form-chat').evaluate(form => form.requestSubmit());
      await wait(380);
      const status = await page.locator('#estado').textContent();
      const counts = {
        mode, profile: 'personal_mvp', privatePosts: state.privatePosts,
        localPosts: state.localPosts, sharedPosts: state.sharedPosts,
        sharedGetsAfterPersonalSync: state.sharedGets - sharedBefore,
        status: String(status).slice(0, 140),
      };
      cases.push(counts);
      assert.equal(counts.privatePosts, 0,
        'personal_mvp MUST NOT POST to the private rack even if a server advertises it');
      if (mode === 'private_hexelion') {
        assert.match(counts.status, /NO_DATA.*personal_profile_private_route_denied/,
          'the client must explain the blocked private route');
        const transcript = await page.locator('#hilo').textContent();
        assert.doesNotMatch(transcript, /synthetic browser no rack request/,
          'refused messages must not remain as apparently sent bubbles');
        assert.equal(await page.locator('#dicho').inputValue(), text,
          'an unsent personal message must remain editable');
        assert.equal(await page.locator('#enviar').isEnabled(), true,
          'rejected route must never strand the send button disabled');
        assert.equal(await page.evaluate(() => document.activeElement.id), 'dicho',
          'keyboard focus must return to the editable prompt after refusal');
      } else {
        assert.equal(counts.localPosts, 1,
          'personal_mvp may attempt its own local GGUF without a fake answer');
      }
      await ctx.close();
    }

    // Explicit private profile is only a UI preference, never inferred.
    // Do not mistake a host fingerprint for a user authorization.
    for (const identityOk of [false, true]) {
      state.talkMode = 'private_hexelion';
      state.identityOk = identityOk;
      state.privatePosts = state.localPosts = state.sharedPosts = state.sharedGets = 0;
      const ctx = await browser.newContext({
        viewport: {width: 360, height: 640}, serviceWorkers:'block',
      });
      await ctx.addInitScript(() => {
        localStorage.setItem('preceptoros.profile','private_rack');
      });
      const page = await ctx.newPage();
      await page.goto(url, { waitUntil:'domcontentloaded' });
      await page.waitForFunction(
        () => typeof window.PreceptorProfile === 'string', null, {timeout:5000});
      const expected = identityOk ? 'private_rack' : 'personal_mvp';
      await page.waitForFunction(expectedValue => window.PreceptorProfile === expectedValue,
        expected, {timeout:5000});
      await page.locator('#dicho').fill('synthetic owner private profile');
      await page.locator('#form-chat').evaluate(form => form.requestSubmit());
      await wait(300);
      const result = {
        explicitPreference:'private_rack', identityObserved:identityOk,
        displayProfile:await page.evaluate(() => window.PreceptorProfile),
        privatePosts:state.privatePosts, sharedPosts:state.sharedPosts,
      };
      assert.equal(result.privatePosts, identityOk ? 1 : 0,
        'only a deliberate and host-observed private mode may attempt the private endpoint');
      assert.equal(result.sharedPosts, 0);
      cases.push(result);
      await ctx.close();
    }
    console.log(JSON.stringify({
      schema:'preceptoros.dayd.personal-mvp-no-rack-browser/1',
      state:'PASS', engine:'Chrome', mode:'real static APP',
      local_server:'synthetic_loopback', real_rack_network:'NONE',
      cases,
    }));
  } finally {
    if (browser) await browser.close();
    await new Promise(ok => server.close(ok));
  }
})().catch(error => {
  console.error(String(error.stack || error));
  process.exitCode = 1;
});
