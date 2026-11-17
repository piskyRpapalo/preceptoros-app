// Talk stores a real plan in the private Plan Store (#314), in a real browser against the real server, isolated HOME.
// Usage: NODE_PATH=<playwright-core> CHROME_PATH=<chromium> node tests/talk_plan.browser.cjs [shots-dir]
// One sanitized JSON receipt on stdout (no paths, no plan text). REAL: no synthetic data and no ?plan=synthetic.
const { spawn, execFileSync } = require("node:child_process");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path"), net = require("node:net");
const { chromium } = require("playwright-core");
const ROOT = path.resolve(__dirname, "..");
const shots = process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(), "plan-shots-"));
const port = () => new Promise((ok) => { const s = net.createServer().listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => ok(p)); }); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));
// The plan: 210 KB with the characters that break naive canonical JSON (accents, emoji, quotes, backslash, tab,
// control characters, U+2028) so the page's SHA must equal Python's canonical SHA byte for byte.
const PIECE = "Paso ñ — «comillas» \"dobles\" \\ barra\ttab \u0001 ctl   sep · 🦀 crab\n";
const TEXT = ("# Plan grande\n" + PIECE.repeat(Math.ceil(210000 / PIECE.length))).slice(0, 210000);
const TITLE = "E2E · 210 KB plan with hard characters";

async function server(home, p) {
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith("PRECEPTOROS_")));
  Object.assign(env, { HOME: home, PRECEPTOROS_PWA_PUERTO: String(p), PRECEPTOROS_PWA_BIND: "127.0.0.1" });
  const child = spawn("python3", [path.join(ROOT, "bin", "preceptoros-pwa")], { cwd: home, env, stdio: "ignore" });
  for (let i = 0; i < 100; i++) { try { if ((await fetch(`http://127.0.0.1:${p}/app`)).ok) return child; } catch {} await wait(100); }
  throw new Error("server did not start");
}
const pythonSha = (title, text) => execFileSync("python3", ["-c",
  "import sys,json,hashlib;d=json.load(sys.stdin);print(hashlib.sha256(json.dumps({'schema':'preceptoros.plan/1','title':d['t'],'text':d['x']},ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()).hexdigest())"],
  { input: JSON.stringify({ t: title, x: text }) }).toString().trim();

(async () => {
  const out = { schema: "preceptoros.talk-plan-e2e/1", evidence: "REAL: real server, real Chromium, isolated HOME; no synthetic plan", result: "FAIL" };
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "plan-home-")), p = await port(), srv = await server(home, p), origin = `http://127.0.0.1:${p}`;
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH }), errors = [];
  const expected = pythonSha(TITLE, TEXT);
  try {
    const page = await browser.newPage({ viewport: { width: 420, height: 680 }, reducedMotion: "reduce" });
    page.on("pageerror", (e) => errors.push(String(e)));
    await page.goto(origin + "/app");
    await page.click("#tab-conversacion");
    await page.click("#plan-escribir > summary");
    out.button_disabled_when_empty = await page.isDisabled("#plan-guardar");
    // keyboard only: title, text, then Enter on the button
    await page.focus("#plan-titulo"); await page.keyboard.type(TITLE.slice(0, 10));
    await page.fill("#plan-titulo", TITLE);
    await page.fill("#plan-texto", TEXT);
    await page.waitForFunction(() => !document.getElementById("plan-guardar").disabled);
    out.page_ref_equals_python_canonical = (await page.getAttribute("#plan-guardar", "data-ref")) === expected;
    // 1) network failure: nothing stored, text kept
    await page.route("**/api/plan", (r) => r.abort());
    await page.evaluate(() => { document.getElementById("plan-escribir").dataset.state = "pressed"; }); await page.focus("#plan-guardar"); await page.keyboard.press("Enter");
    await page.waitForFunction(() => document.getElementById("plan-escribir").dataset.state === "no_data");
    out.network_error = (await page.getAttribute("#plan-escribir", "data-state")) + ":text_kept=" + ((await page.inputValue("#plan-texto")).length === TEXT.length);
    await page.unroute("**/api/plan");
    // 1b) SIMULATED server lies (intercepted in the browser, labelled as such): a ref that is not this text's, then a
    //     read-back with other text. The page must say BLOCKED, never PLAN_STORED.
    const lie = async (route) => {
      await page.route("**/api/plan", (r) => r.fulfill({ status: 201, contentType: "application/json",
        body: JSON.stringify({ schema: "preceptoros.plan-ref/1", plan_sha256: route === "ref" ? "0".repeat(64) : expected, bytes: 1, title: TITLE, created: true, stored: true, authority: "none" }) }));
      // «ref»: a consistent liar, whose wrong ref also serves the same text, so only the page's own SHA can catch it.
      const fake = "0".repeat(64);
      if (route === "ref") await page.route("**/api/plan/" + fake, (r) => r.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ schema: "preceptoros.plan/1", plan_sha256: fake, bytes: 1, title: TITLE, text: TEXT }) }));
      if (route === "readback") await page.route("**/api/plan/" + expected, (r) => r.fulfill({ status: 200, contentType: "application/json",
        body: JSON.stringify({ schema: "preceptoros.plan/1", plan_sha256: expected, bytes: 1, title: TITLE, text: "something else" }) }));
      await page.evaluate(() => { document.getElementById("plan-escribir").dataset.state = "pressed"; }); await page.focus("#plan-guardar"); await page.keyboard.press("Enter");
      await page.waitForFunction(() => ["stored", "blocked", "refused"].includes(document.getElementById("plan-escribir").dataset.state));
      const st = await page.getAttribute("#plan-escribir", "data-state");
      await page.unroute("**/api/plan"); await page.unroute("**/api/plan/" + (route === "ref" ? fake : expected));
      return st;
    };
    out.simulated_wrong_ref = await lie("ref");
    out.simulated_wrong_read_back = await lie("readback");
    // 2) stored for real
    await page.evaluate(() => { document.getElementById("plan-escribir").dataset.state = "pressed"; }); await page.focus("#plan-guardar"); await page.keyboard.press("Enter");
    await page.waitForFunction(() => ["stored", "refused", "blocked"].includes(document.getElementById("plan-escribir").dataset.state), null, { timeout: 30000 });
    out.stored = (await page.getAttribute("#plan-escribir", "data-state")) + ":" + (await page.getAttribute("#plan-escribir", "data-acho"));
    out.sentence = (await page.textContent("#plan-guardar-estado")).replace(/[0-9a-f]{16}…/, "<ref16>…");
    const direct = await (await fetch(`${origin}/api/plan/${expected}`, { headers: { Origin: origin } })).json();
    out.read_back_identical = direct.text === TEXT && direct.title === TITLE && direct.plan_sha256 === expected;
    out.bytes = direct.bytes;
    await page.click("#plan-releer");
    await page.waitForFunction(() => !document.getElementById("plan-leido").hidden);
    out.read_back_in_page = (await page.textContent("#plan-leido-texto")).length === TEXT.length;
    // 3) the panels: stored, nothing proposed, nothing to authorize
    await page.waitForFunction(() => !document.getElementById("talk-plan").hidden, null, { timeout: 10000 }).catch(() => {});
    out.talk_line = ((await page.textContent("#talk-plan")) || "").replace(/[0-9a-f]{12}/, "<ref12>").trim();
    await page.screenshot({ path: path.join(shots, "talk-plan-stored-420.png") });
    await page.click("#tab-mando");
    out.command_buttons = await page.locator("#mando-plan-tareas button:not([disabled])").count();
    out.authorized_or_dispatched_shown = await page.evaluate(() => /AUTHORIZED|DISPATCHED/.test(document.body.innerText.replace(/[A-Z]+ · /g, "")) && !!document.querySelector('[data-estado="authorized"]'));
    out.animations_with_reduced_motion = await page.evaluate(() => document.getAnimations().filter((a) => a.playState === "running" && document.getElementById("plan-escribir").contains(a.effect && a.effect.target)).length);
    // 4) the same plan again: same ref, «already stored»
    await page.click("#tab-conversacion");
    await page.fill("#plan-texto", TEXT + " "); await page.fill("#plan-texto", TEXT);
    await page.waitForFunction(() => !document.getElementById("plan-guardar").disabled);
    await page.evaluate(() => { document.getElementById("plan-escribir").dataset.state = "pressed"; }); await page.focus("#plan-guardar"); await page.keyboard.press("Enter");
    await page.waitForFunction(() => /already stored/.test(document.getElementById("plan-guardar-estado").textContent), null, { timeout: 30000 });
    out.second_store = "already_stored_same_ref";
    // 5) size: over 1 MiB is never cut and never sent
    await page.evaluate((t) => { const a = document.getElementById("plan-texto"); a.value = t; a.dispatchEvent(new Event("input")); }, "x".repeat(1024 * 1024 + 10));
    await page.waitForFunction(() => /over the 1 MiB/.test(document.getElementById("plan-ref").textContent));
    out.over_limit = "button_disabled=" + (await page.isDisabled("#plan-guardar")) + ":text_length_kept=" + ((await page.inputValue("#plan-texto")).length === 1024 * 1024 + 10);
    const big = await fetch(origin + "/api/plan", { method: "POST", headers: { "Content-Type": "application/json", Origin: origin },
      body: JSON.stringify({ schema: "preceptoros.plan/1", title: "big", text: "x".repeat(1024 * 1024 + 10) }) });
    out.over_limit_direct = big.status + ":" + ((await big.json().catch(() => ({}))).cause || "");
    await page.close();
    // 6) 360 px, a second page: no sideways scroll, the stored plan is visible in Talk
    const small = await browser.newPage({ viewport: { width: 360, height: 716 } });
    small.on("pageerror", (e) => errors.push(String(e)));
    await small.goto(origin + "/app"); await small.click("#tab-conversacion"); await small.click("#plan-escribir > summary");
    await small.waitForFunction(() => !document.getElementById("talk-plan").hidden, null, { timeout: 10000 }).catch(() => {});
    out.no_sideways_scroll_360 = await small.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
    const bb = await small.locator("#plan-guardar").boundingBox(), tb = await small.locator("#plan-titulo").boundingBox();
    out.targets_360 = `store ${Math.round(bb.height)}px, title ${Math.round(tb.height)}px`;
    await small.screenshot({ path: path.join(shots, "talk-plan-360.png") });
    await small.close();
    // 7) permissions: another site, a rebound Host, plain text
    const deny = async (h, body) => (await fetch(origin + "/api/plan", { method: "POST", headers: h, body: body || JSON.stringify({ schema: "preceptoros.plan/1", title: "x", text: "y" }) })).status;
    out.permissions = [await deny({ "Content-Type": "application/json", Origin: "https://evil.example" }),
      await deny({ "Content-Type": "application/json", Origin: "http://evil.example:" + p, Host: "evil.example:" + p }),
      await deny({ "Content-Type": "text/plain", Origin: origin })].join(",");
    // 8) memory separation: using Talk created no memory (no engrams table)
    const db = path.join(home, ".preceptoros", "memory.db");
    out.memory_created_by_talk = fs.existsSync(db) && execFileSync("python3", ["-c",
      "import sqlite3,sys;print('engrams' in {r[0] for r in sqlite3.connect('file:'+sys.argv[1]+'?mode=ro',uri=True).execute('select name from sqlite_master')})", db]).toString().trim() === "True";
    out.plan_files_mode = execFileSync("python3", ["-c", "import os,sys,stat;d=os.path.join(sys.argv[1],'.preceptoros','plans');print(oct(os.stat(d).st_mode&0o777))", home]).toString().trim();
    out.page_errors = errors.length;
    const ok = out.simulated_wrong_ref === "blocked" && out.simulated_wrong_read_back === "blocked" && out.button_disabled_when_empty && out.page_ref_equals_python_canonical && out.network_error === "no_data:text_kept=true"
      && out.stored === "stored:verified" && /^PLAN_STORED: ref <ref16>… · \d+ B · read back identical\. Not a task/.test(out.sentence)
      && out.read_back_identical && out.read_back_in_page && /PLAN_STORED · \d+ B · no task proposed \(proposal not built\)/.test(out.talk_line)
      && out.command_buttons === 0 && !out.authorized_or_dispatched_shown && out.animations_with_reduced_motion === 0
      && out.over_limit === "button_disabled=true:text_length_kept=true" && /^422:plan_body_out_of_range$/.test(out.over_limit_direct)
      && out.no_sideways_scroll_360 && out.permissions === "403,403,415" && out.memory_created_by_talk === false
      && out.plan_files_mode === "0o700" && !errors.length;
    out.result = ok ? "PASS" : "FAIL";
  } catch (e) { out.error = String(e.message || e).split("\n")[0]; }
  finally { await browser.close(); srv.kill(); fs.rmSync(home, { recursive: true, force: true }); }
  out.shots = fs.existsSync(shots) ? fs.readdirSync(shots).filter((f) => /^talk-plan-.*\.png$/.test(f)).sort() : [];
  console.log(JSON.stringify(out));
  process.exit(out.result === "PASS" ? 0 : 1);
})();
