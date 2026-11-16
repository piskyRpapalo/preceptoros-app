// Plans in the panels: the five words of the Superbot contract (#310) are earned by evidence, never by a field.
// Runs with: node --test tests/plan_cases.cjs
const test = require("node:test");
const assert = require("node:assert/strict");
const P = require("../interface/plan_flow.js");
const F = require("../interface/plan_fixture.js");

const h = (c) => c.repeat(64), NOW = Date.parse("2026-11-16T16:00:00Z");
const base = (extra) => Object.assign({ task_id: "t1", task_sha256: h("1"), title: "Read", agent: "codex", agent_ready: true }, extra);
const auth = (sha) => ({ by: "person", state: "AUTHORIZED", task_sha256: sha || h("1"), grant_sha256: h("e") });
const flow = (tasks, extra) => Object.assign({ schema: "preceptoros.plan-flow/1", plan: { plan_sha256: h("a"), bytes: 10 },
  proposal: { plan_sha256: h("a"), tasks } }, extra);

test("a fresh task waits for the person: PROPOSED + NEEDS YOU", () => {
  const t = P.task(base(), {}, NOW);
  assert.equal(t.stage, "PROPOSED"); assert.equal(t.state, "hitl");
});
test("A1/A2: a chat word or a proposal field never authorizes", () => {
  for (const a of [{ by: "chat", state: "AUTHORIZED", task_sha256: h("1"), grant_sha256: h("e") },
    { by: "orchestrator", state: "AUTHORIZED", task_sha256: h("1"), grant_sha256: h("e") }, { state: "AUTHORIZED" }, true, "approved"]) {
    assert.equal(P.task(base({ authorization: a }), {}, NOW).stage, "PROPOSED", JSON.stringify(a));
  }
  const p = P.project(flow([base()], { proposal: { plan_sha256: h("a"), authorized: true, tasks: [base()] } }), NOW);
  assert.equal(p.tasks[0].stage, "PROPOSED");
});
test("A3: a grant for another byte of the task is void and asks again", () => {
  const t = P.task(base({ authorization: auth(h("2")) }), {}, NOW);
  assert.equal(t.stage, "PROPOSED"); assert.equal(t.state, "hitl"); assert.match(t.cause, /changed after authorization/);
});
test("A9: an agent not verified or not alive can be proposed, never authorized", () => {
  const t = P.task(base({ agent_ready: false }), {}, NOW);
  assert.equal(t.stage, "PROPOSED"); assert.equal(t.state, "proposed"); assert.match(t.cause, /authorization refused/);
});
test("A10: an expired grant before dispatch asks again", () => {
  const t = P.task(base({ authorization: Object.assign(auth(), { expires_at: "2026-11-16T15:00:00Z" }) }), {}, NOW);
  assert.equal(t.stage, "AUTHORIZED"); assert.equal(t.state, "hitl");
});
test("authorized and not dispatched is its own word", () => {
  const t = P.task(base({ authorization: auth() }), {}, NOW);
  assert.equal(t.stage, "AUTHORIZED"); assert.equal(t.state, "authorized");
});
test("no dispatch without a journal claim; delivery is not a start", () => {
  assert.equal(P.task(base({ authorization: auth(), dispatch: { delivered: true } }), {}, NOW).cause, "dispatch_without_journal_claim");
  const d = P.task(base({ authorization: auth(), dispatch: { claim_ref: h("c"), delivered: true } }), {}, NOW);
  assert.equal(d.stage, "DISPATCHED"); assert.equal(d.state, "waiting");
});
test("RUNNING needs a receipt and freshness; an old declaration is STALE", () => {
  const d = { authorization: auth(), dispatch: { claim_ref: h("c"), delivered: true } };
  assert.equal(P.task(base(Object.assign({ run: { state: "RUNNING", receipt: h("d"), at: "2026-11-16T15:59:30Z" } }, d)), {}, NOW).state, "working");
  assert.equal(P.task(base(Object.assign({ run: { state: "RUNNING", receipt: h("d"), at: "2026-11-16T15:50:00Z" } }, d)), {}, NOW).state, "stale");
  assert.equal(P.task(base(Object.assign({ run: { state: "RUNNING", at: "2026-11-16T15:59:30Z" } }, d)), {}, NOW).stage, "DISPATCHED");
});
test("A5/A6: a result without a receipt, or for another task, is NO_DATA", () => {
  const d = { authorization: auth(), dispatch: { claim_ref: h("c") } };
  assert.equal(P.task(base(Object.assign({ result: { state: "DONE_CHECKED", task_sha256: h("1") } }, d)), {}, NOW).cause, "receipt_missing");
  assert.equal(P.task(base(Object.assign({ result: { state: "DONE_CHECKED", receipt: h("d"), task_sha256: h("9") } }, d)), {}, NOW).cause, "receipt_for_another_task");
  const ok = P.task(base(Object.assign({ result: { state: "DONE_CHECKED", receipt: h("d"), task_sha256: h("1") } }, d)), {}, NOW);
  assert.equal(ok.state, "done"); assert.equal(ok.evidence, "VERIFIED");
  assert.equal(P.task(base(Object.assign({ result: { state: "FAILED", receipt: h("d"), task_sha256: h("1") } }, d)), {}, NOW).state, "blocked");
  assert.equal(P.task(base(Object.assign({ result: { state: "OUTCOME_UNKNOWN", receipt: h("d"), task_sha256: h("1") } }, d)), {}, NOW).state, "no_data");
});
test("A8: a proposal that cites another plan stops the chain; no store is NO_DATA with its cause", () => {
  assert.equal(P.project(flow([base()], { proposal: { plan_sha256: h("b"), tasks: [base()] } }), NOW).cause, "proposal_cites_another_plan");
  assert.equal(P.project(null, NOW).cause, "plan_store_not_built");
  assert.equal(P.project({ cause: "plan_store_http_500" }, NOW).cause, "plan_store_http_500");
});
test("A14: the orchestrator abstains -> zero tasks and the cause", () => {
  const p = P.project(flow([], { proposal: { plan_sha256: h("a"), tasks: [], cause: "plan_too_vague" } }), NOW);
  assert.equal(p.tasks.length, 0); assert.equal(p.abstained, "plan_too_vague");
});
test("continuations: at most three, each with its grounds, never an authorization", () => {
  const p = P.project(F.synthetic(), Date.now());
  const n = P.next(p);
  assert.ok(n.length >= 1 && n.length <= 3);
  for (const s of n) { assert.ok(s.grounds.length >= 1); assert.doesNotMatch(s.text, /authorized|approved/i); }
  assert.ok(n.some((s) => /Fix what failed/.test(s.text)));
  assert.ok(n.some((s) => /decide on «Open the draft PR/.test(s.text)));
  assert.deepEqual(P.next({ state: "NO_DATA" }), []);
});
test("the synthetic drawing walks every stage and says SYNTHETIC", () => {
  const p = P.project(F.synthetic(), Date.now());
  assert.equal(p.synthetic, true); assert.match(p.plan.title, /^SYNTHETIC/);
  const stages = new Set(p.tasks.map((t) => t.stage));
  for (const s of ["PROPOSED", "RUNNING", "RESULT"]) assert.ok(stages.has(s), s);
  const states = new Set(p.tasks.map((t) => t.state));
  for (const s of ["done", "working", "blocked", "hitl", "proposed"]) assert.ok(states.has(s), s);
});
