/* <plan_flow> Superbot in the existing panels (contract: odd/tasks/superbot-e2e-contract-20261116.md, PR #310).
 * A plan written in Talk -> tasks proposed by the chosen orchestrator -> the person authorizes each in Command ->
 * claimed and delivered to an agent -> running -> result, shown in Talk, Notebook, Lab and Harness.
 *
 * This file only reads and tells. The plan store, proposal validation, grants, the journal adapter and the orchestrator
 * choice are Codex's (contract #310); until they answer, the real reading is NO_DATA with its cause. With ?plan=synthetic
 * a made-up plan, marked SYNTHETIC on every surface, shows the drawing. Nothing here can authorize: a chat message,
 * a proposal field or a click on a SYNTHETIC row never becomes a grant.
 *
 * Five words never merge: PROPOSED, AUTHORIZED, DISPATCHED, RUNNING, RESULT. Each task is told with the shared state
 * grammar (PreceptorEstado), so eye, screen reader, Acho and machine read the same thing. */
(function (root) {
  "use strict";
  const HEX = /^[0-9a-f]{64}$/, hex = (v) => typeof v === "string" && HEX.test(v);
  const ends = { DONE_CHECKED: "done", DONE_UNCHECKED: "done", FAILED: "blocked", CANCELLED: "no_data", OUTCOME_UNKNOWN: "no_data" };
  const clean = (v, n) => (typeof v === "string" ? v.replace(/[\u0000-\u001f]/g, " ").slice(0, n) : "");

  // task(t, plan, now) -> {stage, state, cause, evidence}: the furthest stage the evidence earns, never the one a field claims.
  function task(t, proposal, now) {
    const out = (stage, state, cause, evidence) => ({ stage, state, cause, evidence: evidence || "NO_DATA" });
    if (!t || !hex(t.task_sha256) || !clean(t.agent, 40)) return out("PROPOSED", "no_data", "task_unreadable");
    const a = t.authorization, bound = a && a.by === "person" && a.task_sha256 === t.task_sha256 && hex(a.grant_sha256);
    if (a && a.state === "DENIED" && a.by === "person") return out("DENIED", "refused", "denied by you", "DECLARED");
    if (!bound) {
      // An agent without a verified card and a live heartbeat can be proposed, never authorized.
      if (!t.agent_ready) return out("PROPOSED", "proposed", "agent not verified or not alive: authorization refused");
      const changed = a && a.by === "person" && a.task_sha256 !== t.task_sha256;
      return out("PROPOSED", "hitl", changed ? "task changed after authorization: authorize again" : "waits for your authorization");
    }
    if (a.expires_at && Date.parse(a.expires_at) < now && !t.dispatch) return out("AUTHORIZED", "hitl", "authorization expired: authorize again");
    const d = t.dispatch;
    if (!d) return out("AUTHORIZED", "authorized", "authorized, not dispatched yet", "DECLARED");
    if (!hex(d.claim_ref)) return out("AUTHORIZED", "no_data", "dispatch_without_journal_claim");
    const r = t.result;
    if (r) {
      if (!hex(r.receipt)) return out("RESULT", "no_data", "receipt_missing");
      if (r.task_sha256 !== t.task_sha256) return out("RESULT", "no_data", "receipt_for_another_task");
      const s = ends[r.state];
      return s ? out("RESULT", s, r.state.toLowerCase().replace(/_/g, " "), r.state === "DONE_CHECKED" ? "VERIFIED" : "DECLARED")
        : out("RESULT", "no_data", "result_state_unknown");
    }
    const run = t.run;
    if (run && run.state === "RUNNING" && hex(run.receipt) && typeof run.at === "string") {
      const age = now - Date.parse(run.at);
      if (age >= 0 && age <= 120000) return out("RUNNING", "working", "running, declared " + Math.round(age / 1000) + " s ago", "DECLARED");
      return out("RUNNING", "stale", "run declaration too old");
    }
    return out("DISPATCHED", "waiting", d.delivered ? "delivered to " + clean(t.agent, 40) + "; no start declared" : "claimed; not delivered yet", "DECLARED");
  }

  // project(raw, now) -> {plan, tasks, counts, synthetic} or {state:"NO_DATA", cause}. The proposal must cite the plan.
  function project(raw, now) {
    if (!raw || raw.schema !== "preceptoros.plan-flow/1") return { state: "NO_DATA", cause: (raw && raw.cause) || "plan_store_not_built" };
    const plan = raw.plan || {}, prop = raw.proposal || {};
    if (!hex(plan.plan_sha256)) return { state: "NO_DATA", cause: "plan_without_ref" };
    if (prop.plan_sha256 !== plan.plan_sha256) return { state: "NO_DATA", cause: "proposal_cites_another_plan" };
    const list = (Array.isArray(prop.tasks) ? prop.tasks : []).slice(0, 24);
    const tasks = list.map((t) => Object.assign({ id: clean(t.task_id, 24), title: clean(t.title, 140), agent: clean(t.agent, 40),
      capability: clean(t.capability, 40), device: clean(t.device, 40), test: clean(t.test, 140), depends_on: Array.isArray(t.depends_on) ? t.depends_on.map((x) => clean(x, 24)) : [] }, task(t, prop, now)));
    const counts = {};
    tasks.forEach((t) => { counts[t.stage] = (counts[t.stage] || 0) + 1; });
    return { state: "shown", synthetic: raw.synthetic === true, plan: { sha: plan.plan_sha256, bytes: plan.bytes, title: clean(plan.title, 120), at: clean(plan.written_at, 25) },
      orchestrator: clean(prop.orchestrator, 60) || "NO_DATA", abstained: !list.length ? clean(prop.cause, 80) || "no_tasks" : "", tasks, counts };
  }

  // next(p) -> up to three continuations, each derived by a stated rule from records shown on screen. They are PROPOSED:
  // a suggestion, never an authorization. The orchestrator's own suggestions: NO_DATA until it can be chosen and asked.
  function next(p) {
    if (!p || p.state !== "shown") return [];
    const out = [], byId = {};
    p.tasks.forEach((t) => { byId[t.id] = t; });
    p.tasks.forEach((t) => {
      if (t.state === "blocked") out.push({ text: "Fix what failed in «" + t.title + "» and run its test again: " + (t.test || "NO_DATA"), grounds: ["task " + t.id + " FAILED"] });
      if (t.stage === "RESULT" && t.cause === "done unchecked") out.push({ text: "Check the output of «" + t.title + "» with its test: " + (t.test || "NO_DATA"), grounds: ["task " + t.id + " DONE_UNCHECKED"] });
    });
    p.tasks.filter((t) => t.state === "hitl" && t.depends_on.every((d) => byId[d] && byId[d].state === "done"))
      .forEach((t) => out.push({ text: (t.depends_on.length ? "Its prerequisites are done: decide" : "Decide") + " on «" + t.title + "» in Command (" + t.cause + ").",
        grounds: t.depends_on.map((d) => "task " + d + " done").concat("task " + t.id + " waits for you") }));
    return out.slice(0, 3);
  }

  const api = Object.freeze({ task, project, next });
  root.PreceptorPlan = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
