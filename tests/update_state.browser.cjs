// Real-browser walk of the update-state slice at the mini window size (420x642). Not part of bin/pruebas.
//
//   NODE_PATH=<dir with playwright-core> CHROME_PATH=<chromium> OLD_TREE=<checkout of origin/main> \
//     node tests/update_state.browser.cjs
//
// One browser profile, an isolated HOME and a side port, like a phone that already has the app:
//   1. OLD_TREE serves (the shell before this slice); its worker installs; storage markers are written.
//   2. This tree serves: the existing install updates by itself and keeps localStorage and IndexedDB.
//   3. A copy of this tree with the next cache number serves: Settings offers the update only once the new
//      worker holds every file; Reload moves the page to it.
//   4. The server stops: the app opens from the device; served version and check say NO_DATA.
// Never claims a native OS install, a phone, or a signed release: those stay NO_DATA.
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn, execFileSync } = require('node:child_process');
const fs = require('node:fs'), os = require('node:os'), path = require('node:path');

const HERE = path.resolve(__dirname, '..');
const PORT = Number(process.env.PREVIEW_PORT || 18761), URL = 'http://127.0.0.1:' + PORT + '/app.html';
const work = fs.mkdtempSync(path.join(os.tmpdir(), 'update-state-browser-'));
const home = path.join(work, 'home'); fs.mkdirSync(home);
let server = null;

function cacheNumber(tree) {
  return Number(/preceptoros-armazon-v(\d+)/.exec(fs.readFileSync(path.join(tree, 'interface/sw.js'), 'utf8'))[1]);
}
function nextTree() {
  const dest = path.join(work, 'next'); fs.mkdirSync(dest);
  const files = execFileSync('git', ['ls-files', '-co', '--exclude-standard', '-z'], { cwd: HERE }).toString().split('\0').filter(Boolean);
  for (const f of files) { const to = path.join(dest, f); fs.mkdirSync(path.dirname(to), { recursive: true }); if (fs.existsSync(path.join(HERE, f))) fs.copyFileSync(path.join(HERE, f), to); }
  const sw = path.join(dest, 'interface/sw.js'), n = cacheNumber(HERE);
  fs.writeFileSync(sw, fs.readFileSync(sw, 'utf8').replace('preceptoros-armazon-v' + n, 'preceptoros-armazon-v' + (n + 1)));
  return dest;
}
async function serve(tree) {
  await stop();
  server = spawn('python3', ['-B', 'bin/preceptoros-pwa', '--db', path.join(home, 'm.db')],
    { cwd: tree, env: { ...process.env, HOME: home, PRECEPTOROS_PWA_PUERTO: String(PORT) }, stdio: 'ignore' });
  for (let i = 0; i < 40; i++) {
    try { const r = await fetch('http://127.0.0.1:' + PORT + '/api/estado'); if (r.ok) return; } catch (_) {}
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error('server did not start from ' + tree);
}
async function stop() {
  if (!server) return;
  const s = server; server = null;
  await new Promise((r) => { s.once('exit', r); s.kill(); });
}
const text = (page, sel) => page.textContent(sel);

(async () => {
  assert(process.env.OLD_TREE, 'OLD_TREE (a checkout of the shell before this slice) is required');
  const now = cacheNumber(HERE), old = cacheNumber(process.env.OLD_TREE), next = nextTree();
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH, headless: true, args: ['--no-sandbox'] });
  const page = await (await browser.newContext({ viewport: { width: 420, height: 642 } })).newPage();
  const receipt = {};

  await serve(process.env.OLD_TREE);
  await page.goto(URL); await page.evaluate(() => navigator.serviceWorker.ready);
  if (!(await page.evaluate(() => !!navigator.serviceWorker.controller))) await page.reload();
  assert.deepEqual(await page.evaluate(() => caches.keys()), ['preceptoros-armazon-v' + old]);
  await page.evaluate(() => new Promise((ok) => { localStorage.setItem('update-walk', 'kept'); const r = indexedDB.open('update-walk', 1);
    r.onupgradeneeded = () => r.result.createObjectStore('s');
    r.onsuccess = () => { const tx = r.result.transaction('s', 'readwrite'); tx.objectStore('s').put('kept', 'k'); tx.oncomplete = ok; }; }));

  await serve(HERE);
  await page.evaluate(async () => (await navigator.serviceWorker.getRegistration()).update());
  await page.waitForFunction((c) => caches.keys().then((k) => k.join() === c), 'preceptoros-armazon-v' + now, { timeout: 20000 });
  // A reload of the page that was open during the swap can still paint the old document; a fresh open shows the new one.
  receipt.opens_until_new_face = 0;
  for (let i = 1; i <= 5 && !receipt.opens_until_new_face; i++) {
    await page.goto(URL);
    try { await page.waitForFunction((n) => ((document.getElementById('update-installed') || {}).textContent || '').includes('App v' + n), now, { timeout: 4000 }); receipt.opens_until_new_face = i; } catch (_) {}
  }
  assert(receipt.opens_until_new_face, 'the new face never appeared in 5 opens');
  receipt.storage = await page.evaluate(() => new Promise((ok) => { const r = indexedDB.open('update-walk', 1);
    r.onsuccess = () => { const g = r.result.transaction('s').objectStore('s').get('k'); g.onsuccess = () => ok({ local: localStorage.getItem('update-walk'), idb: g.result }); }; }));
  assert.deepEqual(receipt.storage, { local: 'kept', idb: 'kept' });
  await page.click('#tab-ajustes');
  await page.focus('#update-check'); await page.keyboard.press('Enter');
  await page.waitForFunction(() => /^(Up to date|NO_DATA)/.test(document.getElementById('update-state').textContent), null, { timeout: 10000 });
  assert.match(await text(page, '#update-state'), /^Up to date/);
  assert(await page.evaluate(() => document.getElementById('update-reload').disabled), 'nothing offered when nothing is new');

  await serve(next);
  await page.click('#update-check');
  await page.waitForFunction(() => /^Update ready/.test(document.getElementById('update-state').textContent), null, { timeout: 20000 });
  assert(await page.evaluate(() => !document.getElementById('update-reload').disabled));
  await page.waitForFunction(() => /until you reload/.test(document.getElementById('update-installed').textContent), null, { timeout: 5000 });
  await Promise.all([page.waitForNavigation(), page.click('#update-reload')]);
  await page.waitForFunction((n) => ((document.getElementById('update-installed') || {}).textContent || '').includes('App v' + n), now + 1, { timeout: 10000 });

  await stop();
  await page.reload();
  await page.waitForFunction(() => /^NO_DATA · the rack is not reachable/.test((document.getElementById('update-served') || {}).textContent || ''), null, { timeout: 10000 });
  assert.match(await text(page, '#update-installed'), new RegExp('App v' + (now + 1)));
  await page.click('#tab-ajustes'); await page.click('#update-check');
  await page.waitForFunction(() => /^NO_DATA/.test(document.getElementById('update-state').textContent), null, { timeout: 10000 });
  receipt.a11y = await page.evaluate(() => ['update-check', 'update-reload', 'install-app'].map((id) => {
    const b = document.getElementById(id); return { id, name: b.textContent.trim(), height: Math.round(b.getBoundingClientRect().height) }; }));
  for (const b of receipt.a11y) { assert(b.name.length > 3, b.id + ' has a name'); assert(b.height >= 44, b.id + ' is 44 px'); }
  assert.equal(await page.getAttribute('#update-state', 'role'), 'status');
  await browser.close();
  console.log(JSON.stringify({ schema: 'preceptoros.update-walk/1', old, now, next: now + 1, ...receipt, result: 'PASS' }));
})().catch(async (e) => { await stop(); console.error('FAIL', e.message); process.exit(1); })
  .finally(() => fs.rmSync(work, { recursive: true, force: true }));
