// Real browser, real server, isolated HOME: a fresh install creates its private memory from Settings.
// Usage: NODE_PATH=<playwright-core> CHROME_PATH=<chromium> node tests/memory_onboarding.browser.cjs [shots-dir]
// Prints one JSON receipt. Never touches the person's own memory: HOME is a new temporary folder.
const { spawn } = require("node:child_process");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path"), net = require("node:net");
const { chromium } = require("playwright-core");
const ROOT = path.resolve(__dirname, "..");
const shots = process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(), "mem-shots-"));
const port = () => new Promise((ok) => { const s = net.createServer().listen(0, "127.0.0.1", () => { const p = s.address().port; s.close(() => ok(p)); }); });
const wait = (ms) => new Promise((r) => setTimeout(r, ms));

async function server(home, p) {
  const env = Object.fromEntries(Object.entries(process.env).filter(([k]) => !k.startsWith("PRECEPTOROS_")));
  Object.assign(env, { HOME: home, PRECEPTOROS_PWA_PUERTO: String(p), PRECEPTOROS_PWA_BIND: "127.0.0.1" });
  const child = spawn("python3", [path.join(ROOT, "bin", "preceptoros-pwa")], { cwd: home, env, stdio: "ignore" });
  for (let i = 0; i < 100; i++) { try { const r = await fetch(`http://127.0.0.1:${p}/app`); if (r.ok) return child; } catch {} await wait(100); }
  throw new Error("server did not start");
}

(async () => {
  const out = { schema: "preceptoros.memory-onboarding-e2e/1", evidence: "REAL: real server and real Chromium on an isolated HOME; no synthetic data", result: "FAIL" };
  const home = fs.mkdtempSync(path.join(os.tmpdir(), "mem-home-")), db = path.join(home, ".preceptoros", "memory.db");
  let p = await port(), srv = await server(home, p);
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH });
  const errors = [];
  try {
    for (const [w, h] of [[420, 680], [360, 716]]) {
      const page = await browser.newPage({ viewport: { width: w, height: h } });
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(`http://127.0.0.1:${p}/app`);
      await page.click("#tab-ajustes");
      await page.waitForFunction(() => document.getElementById("memoria-inicio").dataset.state !== "loading");
      const card = page.locator("#memoria-inicio");
      if (w === 420) {
        out.fresh = await card.getAttribute("data-state") + ":" + await page.textContent("#memoria-inicio-estado");
        if (!/^hitl:NEEDS YOU/.test(out.fresh)) throw new Error("fresh install is not NEEDS YOU: " + out.fresh);
        const btn = page.locator("#memoria-inicio-boton");
        // refused: no tick, then a wrong phrase, then a synthetic click — nothing is created
        await page.fill("#memoria-inicio-frase", "create my memory");
        if (!(await btn.isDisabled())) throw new Error("button enabled without the tick");
        await page.check("#memoria-inicio-entiendo"); await page.fill("#memoria-inicio-frase", "yes");
        if (!(await btn.isDisabled())) throw new Error("button enabled with a wrong phrase");
        await page.fill("#memoria-inicio-frase", "create my memory");
        await page.evaluate(() => document.getElementById("memoria-inicio-boton").dispatchEvent(new MouseEvent("click", { bubbles: true })));
        await wait(400);
        if (fs.existsSync(db) && (await (await fetch(`http://127.0.0.1:${p}/api/memoria/inicio`)).json()).state === "READY") throw new Error("a synthetic click created it");
        out.refused = "PASS:no_tick,wrong_phrase,synthetic_click";
        await btn.scrollIntoViewIfNeeded();
        const box = await btn.boundingBox(), tick = await page.locator(".memoria-entiendo").boundingBox();

        out.targets = `button ${Math.round(box.height)}px, tick row ${Math.round(tick.height)}px`;
        if (box.height < 44 || tick.height < 44) throw new Error("target under 44 px: " + out.targets);
        // granted: a real keyboard gesture
        await btn.focus(); await page.keyboard.press("Enter");
        await page.waitForFunction(() => document.getElementById("memoria-inicio").dataset.state === "done");
        out.granted = await card.getAttribute("data-acho") + ":" + await page.textContent("#memoria-inicio-estado");
        out.focus_after = await page.evaluate(() => document.activeElement && document.activeElement.id);
        out.file_mode = (fs.statSync(db).mode & 0o777).toString(8);
        await page.screenshot({ path: path.join(shots, "memory-created-420.png"), fullPage: false });
        // the memory is usable: a fact is nested and found
        const nest = await page.evaluate(async () => (await fetch("/api/anidar", { method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ texto: "The test island lighthouse is green.", porque: "memory onboarding e2e" }) })).status);
        out.memory_usable = "anidar_http_" + nest;
      } else {
        out.second_view = await card.getAttribute("data-state") + ":" + await page.locator("#memoria-inicio-crear").isHidden();
        out.no_sideways_scroll = await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth);
        await page.screenshot({ path: path.join(shots, "memory-ready-360.png"), fullPage: false });
      }
      await page.close();
    }
    const before = fs.readFileSync(db);
    const again = await fetch(`http://127.0.0.1:${p}/api/memoria/inicio`, { method: "POST", headers: { "Content-Type": "application/json", Origin: `http://127.0.0.1:${p}` },
      body: JSON.stringify({ schema: "preceptoros.memory-create/1", confirm: true, phrase: "create my memory" }) });
    out.second_attempt = again.status + ":" + (await again.json()).outcome;
    srv.kill(); await wait(300); p = await port(); srv = await server(home, p);
    const after = await (await fetch(`http://127.0.0.1:${p}/api/memoria/inicio`)).json();
    out.after_restart = after.state + ":memories=" + after.memories;
    out.bytes_unchanged_by_second_attempt = Buffer.compare(before, fs.readFileSync(db)) === 0;
    // A file that is not a memory: shown BLOCKED, no form, and not one byte written, even by a direct request.
    const home2 = fs.mkdtempSync(path.join(os.tmpdir(), "mem-home-")), db2 = path.join(home2, ".preceptoros", "memory.db");
    fs.mkdirSync(path.dirname(db2), { recursive: true });
    require("node:child_process").execFileSync("python3", ["-c", "import sqlite3,sys;c=sqlite3.connect(sys.argv[1]);c.execute('create table notes (x)');c.execute(\"insert into notes values ('mine')\");c.commit()", db2]);
    const foreign = fs.readFileSync(db2), p2 = await port(), srv2 = await server(home2, p2);
    try {
      // 1) this step's own requests, before any page loads: read, then a full consent record. Not one byte may change.
      const o2 = `http://127.0.0.1:${p2}`;
      const read2 = await (await fetch(o2 + "/api/memoria/inicio")).json();
      const direct = await fetch(o2 + "/api/memoria/inicio", { method: "POST", headers: { "Content-Type": "application/json", Origin: o2 },
        body: JSON.stringify({ schema: "preceptoros.memory-create/1", confirm: true, phrase: "create my memory" }) });
      const kept = Buffer.compare(foreign, fs.readFileSync(db2)) === 0;
      // 2) the page: Settings shows it BLOCKED with no form.
      const page = await browser.newPage({ viewport: { width: 420, height: 680 } });
      page.on("pageerror", (e) => errors.push(String(e)));
      await page.goto(o2 + "/app"); await page.click("#tab-ajustes");
      await page.waitForFunction(() => document.getElementById("memoria-inicio").dataset.state !== "loading");
      const st = await page.getAttribute("#memoria-inicio", "data-state"), hidden = await page.locator("#memoria-inicio-crear").isHidden();
      await page.screenshot({ path: path.join(shots, "memory-blocked-420.png") });
      await page.close();
      out.unknown_file = `${read2.state}:${st}:form_hidden=${hidden}:direct_${direct.status}:bytes_unchanged=${kept}`;
      // 3) measured, not this step's: the existing /api/estado (read on every page load) adds the turn register to
      //    whatever file is there. Reported to the server's owner; recorded here as a finding, never hidden.
      out.finding_api_estado_writes_unknown_file = Buffer.compare(foreign, fs.readFileSync(db2)) !== 0;
    } finally { srv2.kill(); fs.rmSync(home2, { recursive: true, force: true }); }
    out.page_errors = errors.length;
    const ok = /^done:CREATED/.test(out.granted.replace(/^verified/, "done")) && out.second_attempt === "200:ALREADY_EXISTS"
      && after.state === "READY" && after.memories === 1 && out.second_view === "done:true" && out.no_sideways_scroll && !errors.length
      && out.memory_usable === "anidar_http_200" && out.file_mode === "600"
      && out.unknown_file === "UNKNOWN:blocked:form_hidden=true:direct_409:bytes_unchanged=true";
    out.result = ok ? "PASS" : "FAIL";
  } catch (e) { out.error = String(e.message || e); }
  finally { await browser.close(); srv.kill(); fs.rmSync(home, { recursive: true, force: true }); }
  out.shots = fs.existsSync(shots) ? fs.readdirSync(shots).filter((f) => /^memory-.*\.png$/.test(f)).sort() : [];
  console.log(JSON.stringify(out));
  process.exit(out.result === "PASS" ? 0 : 1);
})();
