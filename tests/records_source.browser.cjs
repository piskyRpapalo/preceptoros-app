#!/usr/bin/env node
// M2a · The person's experience of P2 task records, with a SYNTHETIC records source (Mesa #3 round 10, priority 5).
// Its OWN server (tests/pwa_synthetic_records.py) on 127.0.0.1 with a throw-away HOME; the fixture file plays the
// host's journal. No live journal, no model, no MCP, no 8742. Sequence: a request is recorded; no permission yet; a
// known result; a claim without a receipt is said as unknown; a refresh and a server restart keep the meaning; nothing
// runs a second time; Talk, the Notebook and the JSON agree; Acho shows uncertainty, never success.
// Run: NODE_PATH=<node_modules with playwright-core> CHROME_PATH=<chrome> node tests/records_source.browser.cjs
'use strict';
const assert = require('node:assert/strict');
const { chromium } = require('playwright-core');
const { spawn, execFileSync, execSync } = require('node:child_process');
const crypto = require('node:crypto');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');

const ROOT = path.resolve(__dirname, '..');
const PORT = Number(process.env.PREVIEW_PORT || 18760);
const ORIGIN = 'http://127.0.0.1:' + PORT;
const sha = (p) => crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex');
// The synthetic records, built by the same helpers the unit tests use (shapes of LAB's meta-receipt/1).
const STAGES = JSON.parse(execFileSync('python3', ['-c', `
import json
from test_tareas_hexelion import rec, receipt, runs
need = rec(receipt("blocked", "NOT_STARTED", "PERMISSION", "NO_DATA", None))
done, sim, claim = rec(receipt()), rec(receipt(confidence_basis="synthetic")), rec(None)
print(json.dumps({"permission": runs(need), "known": runs(need, done, sim), "claim": runs(need, done, sim, claim)}))`],
  { cwd: ROOT }));

async function waitServer(child) {
  for (let i = 0; i < 100; i++) {
    if (child.exitCode !== null) throw new Error('test server exited: ' + child.exitCode);
    try { const r = await fetch(ORIGIN + '/app'); if (r.ok) return; } catch { /* not yet */ }
    await new Promise((r) => setTimeout(r, 100));
  }
  throw new Error('test server did not answer');
}

(async () => {
  const home = fs.mkdtempSync(path.join(os.tmpdir(), 'preceptoros-records-'));
  const fixture = path.join(home, 'synthetic_records.json');
  const supply = (stage) => fs.writeFileSync(fixture, JSON.stringify({ records: STAGES[stage], complete_ref: 'c'.repeat(64) }));
  const env = { ...process.env, HOME: home, PRECEPTOROS_PWA_BIND: '127.0.0.1', PRECEPTOROS_PWA_PUERTO: String(PORT),
    PRECEPTOROS_MCP_NATIVO: path.join(home, 'must_not_run.py') };   // any MCP call would fail: nothing may execute
  delete env.PRECEPTOROS_HEXELION_ENDPOINT;
  const start = () => spawn('python3', [path.join(ROOT, 'tests/pwa_synthetic_records.py')], { cwd: ROOT, env, stdio: 'ignore' });
  const receipt = { schema: 'preceptoros.records-source-walk/1', head: null, source: 'SYNTHETIC(injected in a test server)',
    levels: { real_browser: null, live_host_records_source: 'NO_DATA(lab_m1a_contract_not_stable; no live journal read)',
      physical_screenreader_audio_E2E: 'NO_DATA(no_person_ran_the_protocol)' }, checks: {} };
  let browser, server;
  const json = async () => (await fetch(ORIGIN + '/api/hexelion/tareas')).json();
  try {
    supply('permission');
    server = start(); await waitServer(server);
    receipt.head = execSync('git rev-parse HEAD', { cwd: ROOT }).toString().trim();
    browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true, args: ['--no-sandbox'] });
    const page = await browser.newPage({ viewport: { width: 1280, height: 900 }, reducedMotion: 'reduce' });
    await page.addInitScript(() => { window.__audioMade = 0; const Real = window.AudioContext;
      window.AudioContext = function () { window.__audioMade++; return new Real(); }; });
    const outside = [];
    page.on('request', (r) => { if (!r.url().startsWith(ORIGIN) && !r.url().startsWith('data:')) outside.push(r.url()); });
    await page.goto(ORIGIN + '/app', { waitUntil: 'networkidle' });
    // What both panels say about tasks, read as the person meets it: Talk's line, the Notebook's status and cards.
    const surfaces = async (state) => {
      await page.locator('#tab-conversacion').click();
      await page.waitForFunction(() => !document.querySelector('#talk-tasks').hidden && document.querySelector('#talk-tasks').textContent.length > 0, null, { timeout: 10000 });
      const talk = await page.locator('#talk-tasks').textContent();
      await page.locator('#tab-cuaderno').click();
      await page.waitForSelector('#notebook-tasks [data-state="' + state + '"]', { timeout: 10000 });
      return { talk, ...(await page.evaluate(() => ({ status: document.querySelector('#notebook-tasks-status').textContent,
        cards: [...document.querySelectorAll('#notebook-tasks [data-state]')].map((c) => ({ state: c.dataset.state, acho: c.dataset.acho, text: c.innerText })),
        // One live region speaks in the panel on screen: the hidden panel's status is not exposed to a reader.
        liveShown: [...document.querySelectorAll('[aria-live]')].filter((n) => n.offsetParent !== null && /task/i.test(n.textContent)).map((n) => n.id),
        buttons: document.querySelectorAll('#notebook-tasks button, #talk-tasks button').length }))) };
    };
    const agree = (s, rows, label) => {
      assert.equal(s.talk, s.status, label + ': Talk and the Notebook word the tasks differently');
      assert.deepEqual(s.cards.map((c) => [c.state, c.acho]), rows.map((t) => [t.state, t.acho.class]), label + ': cards differ from the JSON rows');
      rows.forEach((t, i) => assert(s.cards[i].text.includes(t.sentence), label + ': a card lost its row sentence'));
      assert.deepEqual(s.liveShown, ['notebook-tasks-status'], label + ': more than one live region says the tasks');
      assert.equal(s.buttons, 0, label + ': a control appeared on a task row');
      assert(!/nothing (else )?(needs|waits)|all clear|\b(is|are) running\b/i.test(s.talk), label + ': a clear or a "running" was said');
    };

    // 1–2 · A request is recorded (the person asks in Talk); no permission is available yet.
    await page.locator('#tab-conversacion').click();
    await page.locator('#dicho').fill('What do you need from me?'); await page.locator('#enviar').click();
    await page.waitForFunction(() => /^ACTED: .*request \d+/.test(document.querySelector('#estado').textContent), null, { timeout: 15000 });
    const thread = await page.locator('#hilo').textContent();
    assert(thread.includes('at least 1 task decision(s) yours'), 'the report did not read the injected source');
    let rows = (await json()).tasks;
    let s = await surfaces('NEEDS_YOUR_AUTHORIZATION');
    agree(s, rows, 'no permission yet');
    assert.deepEqual(rows.map((t) => [t.state, t.acho.class]), [['NEEDS_YOUR_AUTHORIZATION', 'needs_you']]);
    receipt.checks.request_recorded_no_permission = 'MEASURED(talk report == notebook == json; needs_you)';

    // 3–4 · The host supplies a journal record with a known result. Verified and simulated stay apart.
    supply('known');
    await page.reload({ waitUntil: 'networkidle' });
    rows = (await json()).tasks; s = await surfaces('DONE_CHECKED');
    agree(s, rows, 'known result');
    assert.deepEqual(rows.map((t) => [t.state, t.evidence.origin, t.acho.class]),
      [['NEEDS_YOUR_AUTHORIZATION', 'NO_DATA', 'needs_you'], ['DONE_CHECKED', 'MEASURED', 'ok'], ['DONE_CHECKED', 'SIMULATED', 'proposed']]);
    receipt.checks.known_result_shown = 'MEASURED(verified ok; simulated proposed, never verified)';

    // 5–6 · A claim without a receipt: the outcome is unknown. Never "running", never success.
    supply('claim');
    const before = sha(fixture);
    await page.reload({ waitUntil: 'networkidle' });
    rows = (await json()).tasks; s = await surfaces('NO_RESULT_RECORDED');
    agree(s, rows, 'claim without receipt');
    const claim = rows[3], card = s.cards[3];
    assert.deepEqual([claim.state, claim.cause, claim.acho.class, card.acho], ['NO_RESULT_RECORDED', 'claim_without_receipt', 'uncertain', 'uncertain']);
    assert(/no known result/.test(s.talk) && /no result is recorded; it may have stopped/.test(card.text), 'the unknown was not said');
    const drawn = await page.$eval('#notebook-tasks [data-state="NO_RESULT_RECORDED"]', (c) => getComputedStyle(c).borderInlineStartStyle);
    assert.equal(drawn, 'dashed', 'uncertainty is drawn by line, not by colour alone');
    // Keyboard: the disclosure of the uncertain card opens with Enter and keeps the focus.
    const summary = page.locator('#notebook-tasks [data-state="NO_RESULT_RECORDED"] details > summary');
    if (await summary.count()) {
      await summary.focus(); await page.keyboard.press('Enter');
      assert.equal(await page.evaluate(() => document.activeElement && document.activeElement.tagName), 'SUMMARY', 'focus left the disclosure');
      receipt.checks.keyboard = 'MEASURED(disclosure opens with Enter; focus stays on it)';
    } else receipt.checks.keyboard = 'NO_DATA(no_disclosure_on_a_row_without_the_host_uncertainty_projection)';
    // The tab that owns the panel takes the focus back when reached by keyboard from its neighbour.
    await page.locator('#tab-cuaderno').focus(); await page.keyboard.press('ArrowLeft'); await page.keyboard.press('ArrowRight');
    assert.equal(await page.evaluate(() => document.activeElement.id), 'tab-cuaderno', 'focus was not restored to the Notebook tab');
    receipt.checks.claim_without_receipt = 'MEASURED(unknown said; acho uncertain; dashed line)';

    // 7 · A refresh and a server restart keep the meaning.
    const told = { talk: s.talk, cards: s.cards.map((c) => [c.state, c.acho, c.text]) };
    await page.reload({ waitUntil: 'networkidle' });
    s = await surfaces('NO_RESULT_RECORDED');
    assert.deepEqual({ talk: s.talk, cards: s.cards.map((c) => [c.state, c.acho, c.text]) }, told, 'a refresh changed what is said');
    server.kill('SIGTERM'); await new Promise((r) => server.once('exit', r));
    server = start(); await waitServer(server);
    await page.reload({ waitUntil: 'networkidle' });
    s = await surfaces('NO_RESULT_RECORDED');
    assert.deepEqual({ talk: s.talk, cards: s.cards.map((c) => [c.state, c.acho, c.text]) }, told, 'a restart changed what is said');
    const same = (await json()).tasks.map((t) => [t.run_id, t.state, t.cause, t.sentence, t.acho.class]);
    assert.deepEqual(same, rows.map((t) => [t.run_id, t.state, t.cause, t.sentence, t.acho.class]), 'the JSON rows changed over a restart');
    receipt.checks.refresh_and_restart_keep_the_meaning = 'MEASURED(same words, cards and rows)';

    // 8 · Nothing ran a second time: the source was only read, and the app holds no task state of its own.
    assert.equal(sha(fixture), before, 'the app wrote to the records source');
    const written = fs.readdirSync(home, { recursive: true }).map(String).filter((f) => /task|tarea|journal|records/i.test(f));
    assert.deepEqual(written, ['synthetic_records.json'], 'the app stored task state: ' + written.join(', '));
    assert.equal(fs.existsSync(path.join(home, 'must_not_run.py')), false);
    receipt.checks.no_second_execution = 'MEASURED(source bytes unchanged; no task file written; no MCP)';

    // 9–10 · One reading for every reader; reduced motion keeps the mark; sound stays off until turned on.
    const cue = () => page.evaluate(async (motif) => (await window.PreceptorAchoSonido.play({ class: 'uncertain', motif })).state,
      { portadora: 220, moduladora: 440, indice: 20, dur: 0.28, vibrato: true });
    assert.equal(await cue(), 'off', 'the task cue sounded before the person turned sounds on');
    assert.equal(await page.evaluate(() => window.__audioMade), 0, 'audio was made under reduced motion');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.reload({ waitUntil: 'networkidle' });
    const moving = await surfaces('NO_RESULT_RECORDED');
    assert.deepEqual(moving.cards.map((c) => [c.state, c.acho]), told.cards.map((c) => c.slice(0, 2)), 'motion changed a fact');
    assert.equal(await cue(), 'off', 'the task cue sounded with motion allowed');
    assert.deepEqual(outside, [], 'a request left the test origin');
    receipt.checks.talk_notebook_json_agree = 'MEASURED(4 readings; one live region on screen; 0 controls on task rows)';
    receipt.checks.reduced_motion_and_sound = 'MEASURED(same marks with and without motion; task cue off in both; no audio under reduced motion)';
    // Not this slice's: the panel sting (interface/sting.js) may open an audio context when motion is allowed.
    receipt.checks.panel_sting_with_motion = 'OBSERVED(audio contexts made: ' + await page.evaluate(() => window.__audioMade) + '; existing behaviour, not changed here)';
    receipt.levels.real_browser = 'MEASURED(headless_chrome)';
    receipt.result = 'PASS';
  } catch (e) {
    receipt.result = 'FAIL'; receipt.error = String(e && e.message || e).slice(0, 400);
    process.exitCode = 1;
  } finally {
    if (browser) await browser.close();
    if (server) server.kill('SIGTERM');
    fs.rmSync(home, { recursive: true, force: true });
    console.log(JSON.stringify(receipt));
  }
})();
