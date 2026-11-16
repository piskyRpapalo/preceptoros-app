/* <plan_composer> Talk: write a long plan and store it whole in the private Plan Store (Codex, #314: POST /api/plan).
 * Never cut. The ref is the SHA-256 of the canonical document {schema, text, title}; this page computes it too and
 * shows PLAN_STORED only when the server's ref equals ours AND reading it back (GET /api/plan/<sha>) returns the same
 * title and text. Storing is not proposing, authorizing or running anything: the reply says authority "none".
 * Eye, screen reader, Acho and machine read one state: the sentence in #plan-guardar-estado and data-state / data-acho
 * on #plan-escribir. Talk never creates the person's memory: plans live apart from it. */
(function (root) {
  "use strict";
  const doc = root.document;
  if (!doc || !doc.getElementById) return;
  const $ = (id) => doc.getElementById(id);
  const box = $("plan-escribir"), ta = $("plan-texto"), title = $("plan-titulo"), info = $("plan-ref"), btn = $("plan-guardar"),
    say = $("plan-guardar-estado"), again = $("plan-releer"), shown = $("plan-leido"), shownText = $("plan-leido-texto");
  if (!box || !ta || !title || !info || !btn || !say) return;
  const SCHEMA = "preceptoros.plan/1", MAX = 1024 * 1024, enc = new TextEncoder();
  let seq = 0, busy = false, stored = null;

  // canonical(doc): the store's bytes — sorted keys, compact, UTF-8 (Python json.dumps sort_keys, ensure_ascii=False).
  const canonical = (t, x) => enc.encode(JSON.stringify({ schema: SCHEMA, text: x, title: t }));
  async function sha(bytes) {
    try { return [...new Uint8Array(await root.crypto.subtle.digest("SHA-256", bytes))].map((b) => b.toString(16).padStart(2, "0")).join(""); }
    catch { return "NO_DATA"; }
  }
  function tell(state, acho, sentence) { box.dataset.state = state; box.dataset.acho = acho; say.textContent = sentence; }
  const words = (c) => String(c || "no_answer").replace(/_/g, " ");

  async function update() {
    const mine = ++seq, t = title.value, x = ta.value, bytes = canonical(t, x), ref = x.trim() ? await sha(bytes) : "";
    if (mine !== seq) return;
    btn.dataset.ref = ref;
    const ok = x.trim() && t.trim() && t.length <= 240 && bytes.length <= MAX;
    btn.disabled = busy || !ok;
    info.textContent = !x.trim() ? "Empty." : bytes.length + " B · ref " + ref.slice(0, 16) + (ref.length > 16 ? "…" : "") + " · kept whole, never cut"
      + (!t.trim() ? " · it needs a title" : t.length > 240 ? " · the title is over 240 characters" : bytes.length > MAX ? " · over the 1 MiB the store keeps: nothing is cut, shorten it yourself" : "");
    if (stored && stored.ref !== ref) { stored = null; if (again) again.hidden = true; tell("writing", "waiting", "Changed since it was stored: store it again to keep this version."); }
  }

  async function readBack(ref, t, x) {
    const r = await fetch("/api/plan/" + ref, { cache: "no-store" });
    const d = await r.json();
    return { ok: r.ok && d.plan_sha256 === ref && d.title === t && d.text === x, d, status: r.status };
  }

  async function store(e) {
    if (!e.isTrusted || btn.disabled) return;
    const t = title.value, x = ta.value, mine = await sha(canonical(t, x));
    busy = true; btn.disabled = true;
    tell("working", "waiting", "WORKING: storing your plan (" + canonical(t, x).length + " B)…");
    try {
      const r = await fetch("/api/plan", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ schema: SCHEMA, title: t, text: x }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok || d.stored !== true) {
        tell("refused", "refused", "REFUSED: " + words(d.cause || d.causa || "http_" + r.status) + ". Nothing was stored; your text stays here.");
      } else if (mine !== "NO_DATA" && d.plan_sha256 !== mine) {
        tell("blocked", "refused", "BLOCKED: the store answered a ref that is not this text's (" + String(d.plan_sha256).slice(0, 12) + "). Not shown as stored.");
      } else {
        const back = await readBack(d.plan_sha256, t, x);
        if (!back.ok) tell("blocked", "refused", "BLOCKED: stored, but reading it back did not return the same text (" + words(back.d.cause || "http_" + back.status) + ").");
        else {
          stored = { ref: d.plan_sha256 };
          tell("stored", "verified", "PLAN_STORED: " + (d.created ? "" : "already stored, same ") + "ref " + d.plan_sha256.slice(0, 16) + "… · " + d.bytes
            + " B · read back identical. Not a task: nothing was proposed, authorized or run.");
          if (again) again.hidden = false;
          if (root.PreceptorPlanPanels) root.PreceptorPlanPanels.load();
        }
      }
    } catch { tell("no_data", "silent", "NO_DATA: no answer from this device's server. Nothing is known to be stored; your text stays here."); }
    busy = false; update();
  }

  async function show(e) {
    if (!e.isTrusted || !stored || !shown || !shownText) return;
    try {
      const back = await readBack(stored.ref, title.value, ta.value);
      shownText.textContent = back.d.text || "";
      shown.hidden = false; shown.open = true;
      tell(back.ok ? "stored" : "blocked", back.ok ? "verified" : "refused", back.ok
        ? "PLAN_STORED: read back from the store · " + back.d.bytes + " B · identical to what you wrote."
        : "BLOCKED: the store did not return the same text (" + words(back.d.cause || "http_" + back.status) + ").");
    } catch { tell("no_data", "silent", "NO_DATA: the stored plan could not be read back now."); }
  }

  ta.addEventListener("input", update);
  title.addEventListener("input", update);
  btn.addEventListener("click", store);
  if (again) again.addEventListener("click", show);
  tell("writing", "waiting", "");
  update();
})(typeof window !== "undefined" ? window : globalThis);
