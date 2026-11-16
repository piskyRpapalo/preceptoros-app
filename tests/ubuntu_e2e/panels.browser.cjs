// Host-side walk of the APP installed in the Ubuntu container (tests/ubuntu_e2e/run.sh, host network).
// The INSTALLED app, not this tree: it is served from the container on 127.0.0.1:8740. Real Chromium at 420x642.
// Every panel tab opens its own panel with no page error; then Talk asks Hexelion and waits for the answer row.
// Prints {"panels": n, "talk": "ANSWERED"|..., "tabs": [...]} or exits 1.
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const path = require('node:path'), fs = require('node:fs');
const shots = process.argv[2]; fs.mkdirSync(shots, { recursive: true });
const U = 'http://127.0.0.1:' + (process.env.APP_PORT || 8740) + '/app.html';
(async () => {
  const b = await chromium.launch({ executablePath: process.env.CHROME_PATH, args: ['--no-sandbox'] });
  const p = await (await b.newContext({ viewport: { width: 420, height: 642 }, reducedMotion: 'reduce', serviceWorkers: 'block' })).newPage();
  const errors = []; p.on('pageerror', (e) => errors.push(e.message));
  await p.goto(U);
  const tabs = await p.$$eval('[role=tab][id^="tab-"]', (ts) => ts.map((t) => ({ id: t.id, panel: t.getAttribute('aria-controls'), name: t.textContent.trim() || t.getAttribute('aria-label') })));
  assert(tabs.length >= 7, 'the app shows its panels: ' + tabs.length);
  const seen = [];
  for (const t of tabs) {
    await p.click('#' + t.id);
    await p.waitForTimeout(700);
    const shown = await p.evaluate((id) => { const el = document.getElementById(id); return !!el && !el.hidden && el.offsetParent !== null; }, t.panel);
    assert(shown, t.id + ' opens ' + t.panel);
    seen.push(t.id.replace('tab-', ''));
    await p.screenshot({ path: path.join(shots, 'installed-' + t.id + '.png') });
  }
  // Talk: the person's own words, through the composer, to Hexelion's door (the default route).
  await p.click('#tab-conversacion');
  await p.fill('#dicho', 'Who is the lighthouse keeper of the test island?');
  await p.click('#enviar');
  const talk = await p.waitForFunction(() => {
    const t = (document.getElementById('hilo') || {}).textContent || '';
    if (/Marisol Quintero/.test(t.split('Who is the lighthouse keeper').pop())) return 'ANSWERED';
    if (/did not answer|NO_DATA/.test(t.split('Who is the lighthouse keeper').pop())) return 'NO_ANSWER';
    return false;
  }, null, { timeout: 280000, polling: 1000 }).then((h) => h.jsonValue());
  await p.screenshot({ path: path.join(shots, 'installed-talk-answer.png') });
  assert.equal(talk, 'ANSWERED', 'Talk shows the model answer');
  assert.deepEqual(errors, [], 'no page errors');
  await b.close();
  console.log(JSON.stringify({ panels: seen.length, tabs: seen, talk }));
})().catch((e) => { console.error(e.message); process.exit(1); });
