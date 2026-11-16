/* <plan_fixture> The made-up plan behind ?plan=synthetic: six tasks that walk every stage of the Superbot contract
 * (#310) so the panels can be checked before the plan store exists. Every surface that paints it says SYNTHETIC;
 * nothing in it is real, measured or authorized, and its rows can never act. */
(function (root) {
  "use strict";
  const SYNTHETIC = () => {
    const now = Date.now(), iso = (s) => new Date(now - s * 1000).toISOString().replace(/\.\d+Z$/, "Z"), h = (c) => c.repeat(64);
    const t = (id, title, agent, extra) => Object.assign({ task_id: id, task_sha256: h(id.slice(-1)), title, agent, capability: "lab.propose", device: "rack", test: "the gate twice", agent_ready: true }, extra);
    const auth = (c) => ({ by: "person", state: "AUTHORIZED", task_sha256: h(c), grant_sha256: h("e") });
    return { schema: "preceptoros.plan-flow/1", synthetic: true,
      plan: { plan_sha256: h("a"), bytes: 4812, title: "SYNTHETIC · Build the next version and bring me the signatures", written_at: iso(900) },
      proposal: { plan_sha256: h("a"), orchestrator: "SYNTHETIC orchestrator", authorized: true, tasks: [
        t("t1", "Read the open missions", "codex", { authorization: auth("1"), dispatch: { claim_ref: h("c"), delivered: true }, result: { state: "DONE_CHECKED", receipt: h("d"), task_sha256: h("1") } }),
        t("t2", "Draw the plan view in the Notebook", "claude", { authorization: auth("2"), dispatch: { claim_ref: h("c"), delivered: true }, run: { state: "RUNNING", receipt: h("d"), at: iso(20) } }),
        t("t3", "Run the gate twice", "lantern", { authorization: auth("3"), dispatch: { claim_ref: h("c"), delivered: true }, result: { state: "FAILED", receipt: h("d"), task_sha256: h("3") } }),
        t("t4", "Open the draft PR for signature", "codex", { depends_on: ["t1"] }),
        t("t5", "Ask a model with no card", "unknown-agent", { agent_ready: false }),
        t("t6", "Measure the bench again", "junie", { authorization: { by: "person", state: "AUTHORIZED", task_sha256: h("0"), grant_sha256: h("e") } })] } };
  };

  const api = Object.freeze({ synthetic: SYNTHETIC });
  root.PreceptorPlanFixture = api;
  if (typeof module === "object" && module.exports) module.exports = api;
})(typeof window !== "undefined" ? window : globalThis);
