// Real-browser walk of plans in the panels (Superbot contract #310) at the mini window size (420x642).
// Not part of bin/pruebas.
//
//   NODE_PATH=<dir with playwright-core> CHROME_PATH=<chromium> [SHOTS=<dir>] node tests/plan.browser.cjs
//
// Two passes, never mixed:
//   REAL       /app.html from an isolated HOME. The plan store does not exist yet, so every plan surface must say
//              NO_DATA with its cause; the Command list is empty; the composer counts bytes and sends nothing.
//   SYNTHETIC  /app.html?plan=synthetic. Every surface must say SYNTHETIC; the Command buttons are 44 px, reachable by
//              keyboard, named for screen readers, and a click grants nothing.
// Also: no sideways scroll at 420 px, every badge has a visible word, no page errors, and a long plan is not cut.
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');

const HERE = path.resolve(__dirname, '..');
const PORT = Number(process.env.PREVIEW_PORT || 18763), BASE = 'http://127.0.0.1:' + PORT + '/app.html';
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'plan-browser-'));
const home = path.join(work, 'home');
const shots = process.env.SHOTS || path.join(work, 'shots');
fs.mkdirSync(path.join(home, '.preceptoros'), { recursive: true }); fs.mkdirSync(shots, { recursive: true });
let server = null;
async function serve() {
  server = spawn('python3', ['-B', 'bin/preceptoros-pwa', '--db', path.join(home, 'm.db')],
    { cwd: HERE, env: { ...process.env, HOME: home, PRECEPTOROS_PWA_PUERTO: String(PORT) }, stdio: 'ignore' });
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch('http://127.0.0.1:' + PORT + '/api/estado'); if (r.ok) return; } catch (_) {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('server did not start');
}
async function stop() { if (server) { const s = server; server = null; await new Promise((r) => { s.once('exit', r); s.kill(); }); } }

async function tab(page, id) { await page.click('#' + id); await page.waitForTimeout(250); }
const text = (page, sel) => page.$eval(sel, (e) => e.textContent.trim());
async function noSideways(page, where) {
  const w = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  assert.ok(w <= 1, where + ': sideways scroll ' + w + ' px');
}

(async () => {
  const out = { schema: 'preceptoros.plan-walk/1', result: 'FAIL' };
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] });
  try {
    await serve();
    const ctx = await browser.newContext({ viewport: { width: 420, height: 642 }, serviceWorkers: 'block' });
    const page = await ctx.newPage(), errors = [];
    page.on('pageerror', (e) => errors.push(String(e)));

    // REAL
    await page.goto(BASE, { waitUntil: 'networkidle' });
    await tab(page, 'tab-cuaderno');
    assert.match(await text(page, '#notebook-plans-status'), /^NO_DATA: plan store (not built|http 404)/);
    await tab(page, 'tab-mando');
    assert.match(await text(page, '#mando-plan-estado'), /^NO_DATA:/);
    assert.equal(await page.$$eval('#mando-plan-tareas li', (l) => l.length), 0);
    await tab(page, 'tab-lab'); assert.match(await text(page, '#lab-runs-status'), /^NO_DATA:/);
    await tab(page, 'tab-harness'); assert.match(await text(page, '#harness-plan-status'), /^NO_DATA:/);
    await tab(page, 'tab-conversacion');
    assert.equal(await page.$eval('#talk-plan', (e) => e.hidden), true);
    await page.click('.plan-escribir summary');
    const long = 'Paso del plan. '.repeat(14000);           // ~210 KB: far beyond the 1 KB router limit (A7)
    const sent = [];
    page.on('request', (r) => { if (r.method() !== 'GET') sent.push(r.url()); });
    await page.$eval('#plan-texto', (e, v) => { e.value = v; e.dispatchEvent(new Event('input')); }, long);
    await page.waitForFunction(() => /ref [0-9a-f]{16}/.test(document.getElementById('plan-ref').textContent));
    const bytes = Buffer.byteLength(long);
    assert.match(await text(page, '#plan-ref'), new RegExp('^' + bytes + ' B · ref [0-9a-f]{16}… · kept whole, never cut$'));
    assert.equal(await page.$eval('#plan-texto', (e) => e.value.length), long.length, 'the plan is not cut');
    await page.click('#plan-guardar');
    assert.match(await text(page, '#plan-guardar-estado'), /^NO_DATA: the plan store is not built yet/);
    assert.deepEqual(sent, [], 'the composer sent nothing');
    await noSideways(page, 'real talk');
    await page.screenshot({ path: path.join(shots, 'plan-real-talk.png'), fullPage: false });
    out.real = 'PASS:NO_DATA on five surfaces; ' + bytes + ' B plan kept whole; nothing sent';

    // SYNTHETIC
    await page.goto(BASE + '?plan=synthetic', { waitUntil: 'networkidle' });
    await tab(page, 'tab-conversacion');
    const line = await text(page, '#talk-plan .plan-line');
    assert.match(line, /^SYNTHETIC · Plan a{12}: /);
    for (const w of ['PROPOSED', 'RUNNING', 'RESULT']) assert.match(line, new RegExp('\\d ' + w));
    const sug = await page.$$eval('#talk-plan .plan-next li', (l) => l.map((x) => x.textContent));
    assert.ok(sug.length >= 1 && sug.length <= 3, 'continuations ' + sug.length);
    sug.forEach((s) => assert.match(s, / · from: /));
    await page.$eval('#talk-plan', (e) => e.scrollIntoView());
    await page.screenshot({ path: path.join(shots, 'plan-synthetic-talk.png') });

    await tab(page, 'tab-cuaderno');
    assert.equal(await page.$eval('#notebook-plans', (e) => e.dataset.synthetic), 'true');
    const cards = await page.$$eval('#notebook-plans .plan-task', (l) => l.map((c) => ({ stage: c.dataset.stage,
      word: (c.querySelector('.part-estado') || {}).textContent || '', sr: (c.querySelector('.part-estado .sr') || {}).textContent || '' })));
    assert.equal(cards.length, 6);
    cards.forEach((c) => { assert.ok(c.word.replace(/[^\p{L}]/gu, '').length > 1, 'badge without a word'); assert.ok(c.sr.length > 0, 'badge without a sentence'); });
    await page.$eval('#notebook-plans', (e) => e.scrollIntoView());
    await page.screenshot({ path: path.join(shots, 'plan-synthetic-notebook.png') });

    await tab(page, 'tab-mando');
    assert.match(await text(page, '#mando-plan-estado'), /^SYNTHETIC · \d task\(s\) wait for your decision\.$/);
    const btns = await page.$$eval('#mando-plan-tareas button', (l) => l.map((b) => ({ h: b.getBoundingClientRect().height, w: b.getBoundingClientRect().width, name: b.getAttribute('aria-label'), dis: b.disabled })));
    assert.ok(btns.length >= 2);
    btns.forEach((b) => { assert.ok(b.h >= 44 && b.w >= 44, '44 px: ' + JSON.stringify(b)); assert.match(b.name, /^(Authorize|Deny) t\d: /); });
    const firstYes = await page.$('#mando-plan-tareas .plan-si');
    await firstYes.focus(); await page.keyboard.press('Enter');
    assert.match(await text(page, '#mando-plan-nota'), /^SYNTHETIC · nothing was authorized or denied/);
    assert.equal(await page.$$eval('#mando-plan-tareas li', (l) => l.length), btns.length / 2, 'a click changed nothing');
    await page.$eval('#mando-plan-tareas', (e) => e.scrollIntoView());
    await noSideways(page, 'synthetic command');
    await page.screenshot({ path: path.join(shots, 'plan-synthetic-command.png') });

    await tab(page, 'tab-lab');
    assert.match(await text(page, '#lab-runs-status'), /run\(s\) from plan a{12} · SYNTHETIC\.$/);
    assert.ok(await page.$$eval('#lab-runs .notebook-card', (l) => l.length) >= 2);
    await tab(page, 'tab-harness');
    const agents = await page.$$eval('#harness-plan-agents li', (l) => l.map((x) => x.textContent));
    assert.ok(agents.some((a) => /unknown-agent .* not verified: can be proposed, never authorized/.test(a)));
    for (const id of ['tab-cuaderno', 'tab-mando', 'tab-lab', 'tab-harness', 'tab-conversacion']) { await tab(page, id); await noSideways(page, id); }

    await page.emulateMedia({ reducedMotion: 'reduce' });
    await tab(page, 'tab-cuaderno');
    const moving = await page.$$eval('#notebook-plans .estado-glyph', (l) => l.filter((g) => getComputedStyle(g).animationName !== 'none').length);
    assert.equal(moving, 0, 'nothing moves under reduced motion');

    assert.deepEqual(errors, []);
    out.synthetic = 'PASS:SYNTHETIC on five surfaces; 6 tasks with words and sentences; ' + sug.length + ' grounded continuations; 44 px buttons; a click grants nothing';
    out.result = 'PASS';
  } catch (e) { out.error = String(e && e.message || e).slice(0, 400); }
  finally { await browser.close(); await stop(); console.log(JSON.stringify(out)); process.exitCode = out.result === 'PASS' ? 0 : 1; }
})();
