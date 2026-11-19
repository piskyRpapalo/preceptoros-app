/* <plan_panels> Paints the Superbot plan (plan_flow.js) into elements that already exist in Talk, Command, Notebook,
 * Lab and Harness; adds no panel. Reads /api/plan/flow (Codex, contract #310); until it answers, NO_DATA with
 * its cause. Authorize/Deny stay disabled on real rows (grants are not built) and never act on SYNTHETIC ones. */
(function (root) {
  "use strict";
  async function read() {
    const synthetic = typeof location !== "undefined" && /[?&]plan=synthetic\b/.test(location.search);
    if (synthetic) return root.PreceptorPlanFixture ? root.PreceptorPlanFixture.synthetic() : { cause: "fixture_not_loaded" };
    try { const r = await fetch("/api/plan/flow", { cache: "no-store" }); return r.ok ? await r.json() : { cause: r.status === 404 ? "plan_store_not_built" : "plan_store_http_" + r.status }; }
    catch { return { cause: "plan_store_unreachable" }; }
  }

  // --- painters: each writes into an element that already exists in its panel; none adds a panel ---
  const doc = root.document;
  const el = (tag, cls, text) => { const e = doc.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
  const badge = (t, name) => root.PreceptorEstado ? root.PreceptorEstado.make(doc, { state: t.state, cause: t.cause, evidence: t.evidence, source: "plan" }, name) : el("span", "", t.state);
  const mark = (p, box) => { box.dataset.synthetic = p.synthetic ? "true" : "false"; if (p.synthetic) box.prepend(el("p", "plan-synthetic", "SYNTHETIC · made-up plan to check the drawing; nothing here is real or authorized")); };
  function say(id, p, real) { const s = doc.getElementById(id); if (s) s.textContent = p.state === "shown" ? real() : "NO_DATA: " + String(p.cause).replace(/_/g, " ") + "."; }

  function paintNotebook(p) {
    const box = doc.getElementById("notebook-plans"); if (!box) return;
    box.replaceChildren();
    say("notebook-plans-status", p, () => (p.synthetic ? "SYNTHETIC · " : "") + "Plan " + p.plan.sha.slice(0, 12) + " · " + p.plan.bytes + " B stored whole · " + p.tasks.length + " tasks proposed by " + p.orchestrator + ".");
    if (p.state !== "shown") return;
    mark(p, box);
    const head = el("article", "notebook-card plan-card");
    head.append(el("h4", "", p.plan.title), el("p", "notebook-fact", "Plan ref " + p.plan.sha + " · written " + p.plan.at.replace("T", " ")));
    if (p.abstained) head.append(el("p", "notebook-fact", "The orchestrator proposed no task: " + p.abstained));
    box.append(head);
    p.tasks.forEach((t) => {
      const c = el("article", "notebook-card plan-task");
      c.dataset.stage = t.stage; c.dataset.task = t.id;
      const top = el("div", "notebook-top"); top.append(el("h4", "", t.id + " · " + t.title), badge(t, t.id));
      c.append(top, el("p", "notebook-fact", "Stage: " + t.stage + " · agent " + t.agent + " · capability " + (t.capability || "NO_DATA") + " · device " + (t.device || "NO_DATA")),
        el("p", "notebook-fact", "Test: " + (t.test || "NO_DATA") + (t.depends_on.length ? " · after " + t.depends_on.join(", ") : "")));
      box.append(c);
    });
  }
  function paintCommand(p) {
    const ul = doc.getElementById("mando-plan-tareas"); if (!ul) return;
    ul.replaceChildren();
    const wait = p.state === "shown" ? p.tasks.filter((t) => t.state === "hitl") : [];
    say("mando-plan-estado", p, () => (p.synthetic ? "SYNTHETIC · " : "") + (wait.length ? wait.length + " task(s) wait for your decision." : "No task waits for your decision in this plan."));
    ul.dataset.synthetic = p.synthetic ? "true" : "false";
    wait.forEach((t) => {
      const li = el("li", "plan-decide"); li.dataset.task = t.id;
      const yes = el("button", "plan-si", "Authorize"), no = el("button", "plan-no", "Deny");
      [yes, no].forEach((b) => { b.type = "button"; b.setAttribute("aria-describedby", "mando-plan-nota"); });
      yes.setAttribute("aria-label", "Authorize " + t.id + ": " + t.title); no.setAttribute("aria-label", "Deny " + t.id + ": " + t.title);
      // Real grants are Codex's (contract #310). Until then the buttons say why they cannot act; SYNTHETIC rows never act.
      if (!p.synthetic) { yes.disabled = no.disabled = true; }
      [yes, no].forEach((b) => b.addEventListener("click", (e) => {
        if (!e.isTrusted) return;
        const n = doc.getElementById("mando-plan-nota");
        if (n) n.textContent = "SYNTHETIC · nothing was authorized or denied: the grant service is not built (NO_DATA).";
      }));
      li.append(badge(t, t.id), el("span", "", t.id + " · " + t.title + " → " + t.agent), yes, no);
      ul.append(li);
    });
  }
  function paintLab(p) {
    const box = doc.getElementById("lab-runs"); if (!box) return;
    box.replaceChildren();
    const runs = p.state === "shown" ? p.tasks.filter((t) => ["DISPATCHED", "RUNNING", "RESULT"].includes(t.stage)) : [];
    say("lab-runs-status", p, () => runs.length + " run(s) from plan " + p.plan.sha.slice(0, 12) + (p.synthetic ? " · SYNTHETIC" : "") + ".");
    if (p.state === "shown") mark(p, box);
    runs.forEach((t) => { const c = el("article", "notebook-card"); const top = el("div", "notebook-top"); top.append(el("h4", "", t.id + " · " + t.agent), badge(t, t.id)); c.append(top, el("p", "notebook-fact", t.title + " · test: " + (t.test || "NO_DATA"))); box.append(c); });
  }
  function paintHarness(p) {
    const ul = doc.getElementById("harness-plan-agents"); if (!ul) return;
    ul.replaceChildren();
    const agents = {};
    if (p.state === "shown") p.tasks.forEach((t) => { (agents[t.agent] = agents[t.agent] || { caps: new Set(), ready: t.cause.indexOf("agent not verified") < 0 }).caps.add(t.capability || "NO_DATA"); });
    say("harness-plan-status", p, () => Object.keys(agents).length + " agent(s) in this plan" + (p.synthetic ? " · SYNTHETIC" : "") + ". Verified capabilities come from agent cards (NO_DATA until loaded).");
    Object.keys(agents).sort().forEach((a) => ul.append(el("li", "", a + " · " + [...agents[a].caps].join(", ") + (agents[a].ready ? "" : " · not verified: can be proposed, never authorized"))));
  }
  function paintTalk(p, sug) {
    const box = doc.getElementById("talk-plan"); if (!box) return;
    if (p.state !== "shown") { box.hidden = true; return; }
    box.hidden = false; box.replaceChildren();
    const c = p.counts, line = ["PROPOSED", "AUTHORIZED", "DISPATCHED", "RUNNING", "RESULT", "DENIED"].filter((k) => c[k]).map((k) => c[k] + " " + k).join(" · ");
    // A stored plan with no tasks is said as what it is: stored, not proposed, not authorized.
    box.append(el("p", "plan-line", (p.synthetic ? "SYNTHETIC · " : "") + "Plan " + p.plan.sha.slice(0, 12) + ": "
      + (line || "PLAN_STORED · " + p.plan.bytes + " B · no task proposed (" + String(p.abstained || "NO_DATA").replace(/_/g, " ") + ")") + "."));
    if (sug.length) {
      box.append(el("p", "plan-next-title", "What could come next (suggestions from the records, not authorizations):"));
      const ol = el("ol", "plan-next");
      sug.forEach((s) => { const li = el("li", "", s.text); li.append(el("span", "plan-grounds", " · from: " + s.grounds.join("; "))); ol.append(li); });
      box.append(ol, el("p", "plan-next-note", "The orchestrator's own suggestions: NO_DATA (it cannot be chosen and asked yet)."));
    }
  }

  async function load() {
    const p = root.PreceptorPlan.project(await read(), Date.now());
    paintNotebook(p); paintCommand(p); paintLab(p); paintHarness(p); paintTalk(p, root.PreceptorPlan.next(p));
    if (root.PreceptorSuperbotTalk) root.PreceptorSuperbotTalk.fromPlan(p);
    return p;
  }
  root.PreceptorPlanPanels = Object.freeze({ load });
  if (doc && doc.getElementById && root.PreceptorPlan) {
    if (doc.readyState === "loading") doc.addEventListener("DOMContentLoaded", load); else load();
    ["tab-mando", "tab-conversacion", "tab-cuaderno", "tab-lab", "tab-harness"].forEach((id) => { const t = doc.getElementById(id); if (t) t.addEventListener("click", load); });
  }
})(typeof window !== "undefined" ? window : globalThis);
