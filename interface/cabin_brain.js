/* Talk cabin · the Brain band: which brain answers now, the choice between the brains the server offers, the heads
 * (NO_DATA until their owner publishes a contract) and how many signatures Boundary has read, as a link there.
 * Reads /api/cerebro and asks it to change; the server decides and the band shows what it says is in use.
 * Never signs: the signatures and their token live in Boundary only. Nothing here moves.
 */
(function (root) {
  "use strict";
  const doc = root.document;
  function say(el, text) { if (el && el.textContent !== text) el.textContent = text; }

  // brainView(d) -> what the Brain band shows from /api/cerebro, or NO_DATA with a cause. Pure. Heads have no
  // contract yet (they need an owner's contract first): they stay NO_DATA here until the owner of the brain delivers one.
  // The server speaks Spanish inside its records; the screen speaks English. Known words are named, anything else
  // keeps its plain id; the server's own reason stays on data-cause for the machine reader.
  const labels = { base: "Base", afinado: "Tuned" };
  const reasons = { "no hay cerebro afinado declarado": "no tuned brain declared",
    "la ruta declarada no existe en el disco": "its file is not on this disk" };
  const word = (k) => labels[k] || k;
  const cause = (c) => reasons[c] || (c ? "the server gave a reason" : "");
  function brainView(d) {
    const use = d && d.en_uso, ops = d && Array.isArray(d.opciones) ? d.opciones : null;
    if (!use || !ops || typeof use.cual !== "string") return { state: "NO_DATA", cause: "the brain did not answer", options: [] };
    const options = ops.filter((o) => o && typeof o.cual === "string").map((o) => ({ which: o.cual, label: word(o.cual),
      name: String(o.nombre || o.cual), available: o.disponible === true, on: o.cual === use.cual,
      cause: o.disponible === true ? "" : (cause(o.causa) || "not available"), raw: o.causa == null ? "" : String(o.causa) }));
    const mine = options.filter((o) => o.on)[0];
    return { state: "OBSERVED", which: use.cual, label: word(use.cual), name: String(use.nombre || use.cual),
      ready: Boolean(mine && mine.available), heads: { state: "NO_DATA", cause: "no heads contract yet" }, options };
  }

  function paintBrain(d) {
    const line = doc.getElementById("brain-uso"), box = doc.getElementById("brain-opciones"), heads = doc.getElementById("brain-heads");
    if (!line || !box) return;
    const v = brainView(d), E = root.PreceptorEvidence;
    box.replaceChildren();
    const detail = doc.getElementById("talk-diagnostics-brain");
    if (v.state === "NO_DATA") {
      line.dataset.state = "NO_DATA"; line.dataset.cause = "brain_unavailable";
      say(line, "Brain · not available yet. See technical evidence.");
      if (detail) detail.textContent = "NO_DATA(brain_unavailable): " + v.cause;
      if (heads) heads.replaceChildren(); return;
    }
    line.dataset.state = "MEASURED"; line.dataset.cause = "source_cerebro";
    if (detail) detail.textContent = "MEASURED(brain_selection) · NO_DATA(heads_contract_not_published)";
    say(line, "Brain · " + v.label + " · " + v.name + (v.ready ? "" : " · not ready: its file is not on this disk"));
    v.options.forEach((o) => {
      const b = doc.createElement("button");
      b.type = "button"; b.className = "brain-op"; b.setAttribute("role", "radio"); b.setAttribute("aria-checked", String(o.on));
      b.dataset.cual = o.which; b.dataset.cause = o.raw; b.textContent = o.label + (o.available ? "" : " · " + (o.on ? "missing" : "unavailable"));
      b.disabled = !o.available;
      b.setAttribute("aria-label", o.label + " brain · " + o.name + (o.available ? (o.on ? " · in use" : " · press to use") : " · " + o.cause));
      b.title = o.available ? o.name : o.cause;
      b.addEventListener("click", () => { if (!o.on) chooseBrain(o.which); });
      box.appendChild(b);
    });
    if (heads) { heads.replaceChildren(doc.createTextNode("Heads · "), E ? E.make(doc, v.heads.state, v.heads.cause) : doc.createTextNode("NO_DATA · " + v.heads.cause)); }
  }

  async function readBrain() {
    try { const r = await fetch("/api/cerebro", { cache: "no-store" }); if (!r.ok) throw new Error("http"); paintBrain(await r.json()); }
    catch { paintBrain(null); }
  }

  // The person chooses; the server decides and says what is in use now (asking for one and getting the base must show).
  async function chooseBrain(which) {
    const line = doc.getElementById("brain-uso");
    say(line, "Brain · changing to " + word(which) + "…");
    try {
      const r = await fetch("/api/cerebro", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ cual: which, motivo: "chosen from Talk" }) });
      const d = await r.json();
      if (!r.ok) { await readBrain(); say(line, line.textContent + " · REFUSED · " + (cause(d.motivo) || "HTTP " + r.status)); return; }
      if (d && d.en_uso) paintBrain(d); else await readBrain();
    } catch { say(line, "Brain · NO_DATA · the brain did not answer; nothing changed."); }
  }

  // The signatures live in Boundary. The cabin only says how many it has read, and takes the person there.
  function wireSignatures() {
    const b = doc.getElementById("brain-firmas"), n = doc.getElementById("hitl-n"), tab = doc.querySelector('[data-panel="gobierno"]');
    if (!b || !n || !tab) return;
    const paint = () => {
      const k = Number(n.textContent);
      b.textContent = Number.isInteger(k) && n.textContent.trim() !== "" ? (k === 0 ? "Signatures · none waiting" : k + " await your signature →") : "Signatures · not read yet →";
      b.dataset.waiting = Number.isInteger(k) && k > 0 ? "1" : "0";
    };
    b.addEventListener("click", () => tab.click());
    new root.MutationObserver(paint).observe(n, { childList: true, characterData: true, subtree: true });
    paint();
  }

  root.PreceptorCabinBrain = Object.freeze({ brainView, readBrain });
  if (typeof module === "object" && module.exports) module.exports = { brainView };
  if (doc && doc.getElementById("brain-uso")) { readBrain(); wireSignatures(); }
})(typeof window !== "undefined" ? window : globalThis);
