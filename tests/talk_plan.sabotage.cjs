// Sabotage for Talk's plan storing: break plan_composer.js on purpose and require tests/talk_plan.browser.cjs to fail.
// Each break is a way the page could lie: cutting the plan, trusting the server's ref without checking it, saying
// PLAN_STORED without reading it back, or calling a stored plan a task. The repository is copied (without .git) to
// a temporary folder, one file is mutated, and the real browser E2E runs against that copy.
// Usage: NODE_PATH=<playwright-core> CHROME_PATH=<chromium> node tests/talk_plan.sabotage.cjs
const { execFileSync, spawnSync } = require("node:child_process");
const fs = require("node:fs"), os = require("node:os"), path = require("node:path");
const ROOT = path.resolve(__dirname, "..");
const SRC = fs.readFileSync(path.join(ROOT, "interface", "plan_composer.js"), "utf8");
const MUTATIONS = {
  cut_the_plan: ['body: JSON.stringify({ schema: SCHEMA, title: t, text: x })', 'body: JSON.stringify({ schema: SCHEMA, title: t, text: x.slice(0, 1000) })'],
  trust_server_ref: ['} else if (mine !== "NO_DATA" && d.plan_sha256 !== mine) {', '} else if (false) {'],
  skip_read_back: ["if (!back.ok) tell(", "if (false) tell("],
  call_it_a_task: ['tell("stored", "verified", "PLAN_STORED: "', 'tell("authorized", "verified", "AUTHORIZED: "'],
};
const out = {}; let caught = true;
for (const [name, [a, b]] of Object.entries(MUTATIONS)) {
  if (SRC.split(a).length !== 2) { out[name] = "NO_DATA:anchor_missing"; caught = false; continue; }
  const copy = fs.mkdtempSync(path.join(os.tmpdir(), "talk-sab-"));
  try {
    execFileSync("rsync", ["-a", "--exclude", ".git", "--exclude", "node_modules", ROOT + "/", copy + "/"]);
    fs.writeFileSync(path.join(copy, "interface", "plan_composer.js"), SRC.replace(a, b));
    const r = spawnSync("node", [path.join(copy, "tests", "talk_plan.browser.cjs")], { env: process.env, encoding: "utf8", timeout: 300000 });
    out[name] = r.status !== 0 ? "caught" : "MISSED";
    caught = caught && r.status !== 0;
  } finally { fs.rmSync(copy, { recursive: true, force: true }); }
}
console.log(JSON.stringify({ sabotage: caught ? "caught" : "MISSED", cases: out }));
process.exit(caught ? 0 : 1);
