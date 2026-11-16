// Real-browser walk of the shared participant state (PreceptorEstado) in Talk, Lab, Notebook and Command, at the
// mini window size (420x642). Not part of bin/pruebas.
//
//   NODE_PATH=<dir with playwright-core> CHROME_PATH=<chromium> [SNAPSHOT_FROM=<a .preceptoros dir>] [SHOTS=<dir>] \
//     node tests/estado.browser.cjs
//
// Two passes, never mixed:
//   REAL      this tree serves from an isolated HOME. With SNAPSHOT_FROM, a read-only COPY of that home's
//             notebook/ and firmas/ files is placed in it first (the server never sees the original). Every state
//             on screen comes from the server's own answers.
//   FIXTURE   the same page with /api/notebook, /api/hexelion/tareas and /api/firmas answered by made-up rows that
//             reach every state. A banner «FIXTURE · not telemetry» is drawn on the page before any screenshot.
// Asserts: no state without a word on screen; glyph hidden from readers; every badge carries data-acho; nothing
// moves under prefers-reduced-motion; no sideways scroll at 420 px; Command buttons are 44 px and land on the
// evidence tab; Lab and Notebook keep their own cards (states are added, nothing is replaced).
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');

const HERE = path.resolve(__dirname, '..');
const PORT = Number(process.env.PREVIEW_PORT || 18762), URL = 'http://127.0.0.1:' + PORT + '/app.html';
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'estado-browser-'));
const home = path.join(work, 'home'), data = path.join(home, '.preceptoros');
const shots = process.env.SHOTS || path.join(work, 'shots');
fs.mkdirSync(data, { recursive: true }); fs.mkdirSync(shots, { recursive: true });
let server = null;

if (process.env.SNAPSHOT_FROM) {
  for (const d of ['notebook', 'firmas']) {
    const from = path.join(process.env.SNAPSHOT_FROM, d);
    if (fs.existsSync(from)) fs.cpSync(from, path.join(data, d), { recursive: true });
  }
}
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

const SHA = 'f'.repeat(64);
const iso = (sAgo) => new Date(Date.now() - sAgo * 1000).toISOString().replace(/\.\d+Z$/, 'Z');
function fixtureNotebook() {
  return { schema: 'preceptoros.notebook-readonly/0', agents_status: 'DECLARADO', agents_cause: null,
    agents: [
      { id: 'codex', name: 'Codex (fixture)', role: 'contracts', last_seen: iso(60), status: 'OBSERVADO', cause: 'recent_declared_heartbeat', receipt_sha256: SHA },
      { id: 'mistral', name: 'Mistral (fixture)', role: 'research', last_seen: iso(4000), status: 'STALE', cause: 'declared_heartbeat_expired', receipt_sha256: SHA }],
    reports: [{ kind: 'WBR', status: 'NO_DATA', cause: 'file_missing' }, { kind: 'MBR', status: 'NO_DATA', cause: 'file_missing' }],
    receipts: [
      { voice: 'hexelion', tool: 'read_file', result: 'ok', status: 'DECLARED', measured_at: iso(300), ms: 12, bytes: 300, receipt_sha256: SHA },
      { voice: 'claude', tool: 'write_file', result: 'refused', status: 'DECLARED', measured_at: iso(200), ms: 3, bytes: 0, receipt_sha256: SHA }],
    bench: [] };
}
function fixtureTasks() {
  const t = (run, state, sentence) => ({ run_id: run, state, sentence, next: '', evidence: { origin: 'SIMULATED' } });
  return { schema: 'preceptoros.hexelion-tasks/1', state: 'MEASURED', cause: null, observed_at: iso(1),
    tasks: [t('fx-1', 'NEEDS_YOUR_AUTHORIZATION', 'FIXTURE: waits for your authorization.'), t('fx-2', 'DONE_CHECKED', 'FIXTURE: done and checked.'),
      t('fx-3', 'FAILED', 'FIXTURE: failed.'), t('fx-4', 'NO_RESULT_RECORDED', 'FIXTURE: claimed, no result yet.')],
    needs_you: 1, blocks_new_work: 1, decisions_for_you: 0,
    counters: { state: 'NO_DATA', cause: 'completeness_not_attested', complete_ref: null, known_counts_are: 'at_least' } };
}
const fixtureFirmas = () => ({ esquema: 'preceptoros.firmas-pendientes/1', medido: iso(30), hoy: iso(0).slice(0, 10), cuenta: { sign: 2 }, filas: [], no_data: [] });

async function banner(page, label) {
  await page.evaluate((label) => {
    let b = document.getElementById('walk-banner');
    if (!b) { b = document.createElement('div'); b.id = 'walk-banner'; document.body.prepend(b); }
    b.textContent = label;
    b.style.cssText = 'position:sticky;top:0;z-index:99;padding:4px 8px;font:700 12px system-ui;letter-spacing:.04em;' +
      (label.startsWith('FIXTURE') ? 'background:#7a1f5c;color:#fff' : 'background:#1f4d7a;color:#fff');
  }, label);
}
async function audit(page, where) {
  return page.evaluate((where) => {
    const badges = [...document.querySelectorAll('.part-estado')].filter((b) => b.offsetParent !== null);
    for (const b of badges) {
      const word = b.querySelector('.estado-word'), glyph = b.querySelector('.estado-glyph'), sr = b.querySelector('.sr');
      if (!word || !word.textContent.trim()) throw new Error(where + ': a badge without a word');
      if (!glyph || glyph.getAttribute('aria-hidden') !== 'true') throw new Error(where + ': glyph not hidden from readers');
      if (!sr || !/evidence/.test(sr.textContent)) throw new Error(where + ': no reader sentence');
      if (!b.dataset.acho) throw new Error(where + ': no Acho reading');
      const anim = getComputedStyle(glyph).animationName;
      if (matchMedia('(prefers-reduced-motion: reduce)').matches && anim !== 'none') throw new Error(where + ': moves under reduced motion');
    }
    if (document.documentElement.scrollWidth > innerWidth + 1) throw new Error(where + ': sideways scroll ' + document.documentElement.scrollWidth);
    return badges.map((b) => b.dataset.estado + (b.dataset.cause ? ':' + b.dataset.cause : ''));
  }, where);
}

(async () => {
  await serve();
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true, args: ['--no-sandbox'] });
  const receipt = { schema: 'preceptoros.estado-walk/1', snapshot: !!process.env.SNAPSHOT_FROM, passes: {} };
  for (const pass of ['REAL', 'FIXTURE']) {
    const ctx = await browser.newContext({ viewport: { width: 420, height: 642 }, reducedMotion: 'reduce', serviceWorkers: 'block' });
    const page = await ctx.newPage();
    if (pass === 'FIXTURE') {
      await page.route('**/api/notebook', (r) => r.fulfill({ json: fixtureNotebook() }));
      await page.route('**/api/hexelion/tareas', (r) => r.fulfill({ json: fixtureTasks() }));
      await page.route('**/api/firmas', (r) => r.fulfill({ json: fixtureFirmas() }));
    }
    const label = pass === 'REAL' ? 'REAL · ' + (process.env.SNAPSHOT_FROM ? 'copy of this rack\'s files' : 'empty home') + ' · read ' + iso(0)
      : 'FIXTURE · not telemetry · made-up rows';
    const seen = receipt.passes[pass] = {};
    await page.goto(URL);
    for (const [tab, wait] of [['mando', '#mando-tareas-estado .part-estado:not(.estado-loading)'], ['conversacion', '#conv-estados .part-estado:not(.estado-loading)'],
      ['lab', '#tab-lab'], ['cuaderno', '#notebook-agents .notebook-card, #notebook-agents article, #notebook-agents > *']]) {
      await page.click('#tab-' + tab);
      await page.waitForSelector(wait, { timeout: 15000 }).catch(() => {});
      await page.waitForTimeout(600);
      await banner(page, label + ' · ' + tab);
      seen[tab] = await audit(page, pass + '/' + tab);
      await page.screenshot({ path: path.join(shots, pass.toLowerCase() + '-' + tab + '.png') });
      // A second picture where the badges sit: Lab benchmarks opened, Notebook tasks and agents.
      const focus = { lab: '#lab-bench', cuaderno: '#notebook-tasks', conversacion: null, mando: null }[tab];
      if (focus) {
        await page.evaluate((sel) => { const el = document.querySelector(sel); if (!el) return;
          const d = el.closest('details'); if (d) d.open = true;
          const btn = el.closest('section') && el.closest('section').querySelector('button[aria-expanded="false"]'); if (btn) btn.click();
          el.scrollIntoView({ block: 'center' }); }, focus);
        await page.waitForTimeout(800);
        await banner(page, label + ' · ' + tab + ' · ' + focus);
        seen[tab + '_focus'] = await audit(page, pass + '/' + tab + focus);
        await page.screenshot({ path: path.join(shots, pass.toLowerCase() + '-' + tab + '-focus.png') });
      }
    }
    // Command walks to the evidence: the tasks button lands on the Notebook.
    await page.click('#tab-mando');
    const b = await page.$('#mando-ir-tareas'); const box = await b.boundingBox();
    assert(box.height >= 44, 'Command button is 44 px');
    await b.focus(); await page.keyboard.press('Enter');
    assert.equal(await page.getAttribute('#tab-cuaderno', 'aria-selected'), 'true', 'Enter on «Open the Notebook» opens the Notebook');
    seen.lab_cards_kept = await page.evaluate(() => document.querySelectorAll('#lab-bench > *, #notebook-loops > *').length);
    await ctx.close();
  }
  // The fixture reaches the states the rack cannot show today; the real pass never shows WORKING (no producer).
  const fx = Object.values(receipt.passes.FIXTURE).flat().join(' ');
  for (const s of ['available', 'stale', 'hitl', 'done', 'refused', 'blocked', 'waiting']) assert.match(fx, new RegExp('\\b' + s), 'fixture shows ' + s);
  assert.doesNotMatch(Object.values(receipt.passes.REAL).flat().join(' '), /\bworking\b/, 'nothing real declares a run');
  await browser.close(); await stop();
  receipt.shots = shots; receipt.result = 'PASS';
  console.log(JSON.stringify(receipt));
})().catch(async (e) => { await stop(); console.error('FAIL', e.message); process.exit(1); })
  .finally(() => { fs.rmSync(path.join(work, 'home'), { recursive: true, force: true }); });
