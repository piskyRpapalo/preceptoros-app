/* <memory_onboarding> Settings · Your private memory. Reads GET /api/memoria/inicio and, only after the person ticks
 * «I understand» AND types the phrase, sends the exact consent record to POST /api/memoria/inicio. The server decides:
 * it creates from nothing only, never recreates, resets or touches an existing memory, and refuses a file it cannot
 * recognize. Eye, screen reader, Acho and machine read the same state: the sentence in #memoria-inicio-estado,
 * data-state and data-acho on the card. A synthetic event cannot send it (isTrusted). */
(function (root) {
  "use strict";
  const doc = root.document;
  if (!doc || !doc.getElementById) return;
  const $ = (id) => doc.getElementById(id);
  const card = $("memoria-inicio");
  if (!card) return;
  const status = $("memoria-inicio-estado"), form = $("memoria-inicio-crear"), place = $("memoria-inicio-lugar"),
    list = $("memoria-inicio-lista"), ok = $("memoria-inicio-entiendo"), phrase = $("memoria-inicio-frase"), btn = $("memoria-inicio-boton");
  let want = "create my memory", busy = false;

  // state -> [data-state, Acho expression, sentence]. The words are the ones the rest of the APP uses.
  function tell(state, acho, sentence) {
    card.dataset.state = state; card.dataset.acho = acho;
    status.textContent = sentence;
  }
  function paint(r) {
    if (!r || r.schema !== "preceptoros.memory-onboarding/1") {
      form.hidden = true;
      return tell("no_data", "silent", "NO_DATA: the memory state could not be read (" + ((r && (r.causa || r.cause)) || "no answer") + ").");
    }
    if (r.phrase) want = r.phrase;
    place.textContent = r.place || "NO_DATA";
    list.replaceChildren(...(r.will_create || []).map((w) => { const li = doc.createElement("li"); li.textContent = w; return li; }));
    if (r.state === "READY") {
      form.hidden = true;
      const n = r.memories, what = r.empty ? "it is empty" : n + (n === 1 ? " memory" : " memories") + " and " + r.links + (r.links === 1 ? " link" : " links");
      return tell("done", "verified", (r.outcome === "CREATED" ? "CREATED: your private memory now exists at " : "READY: your private memory exists at ")
        + r.place + "; " + what + "; search " + (r.search ? "ready" : "not available on this system") + ".");
    }
    if (r.state === "UNKNOWN") {
      form.hidden = true;
      return tell("blocked", "refused", "BLOCKED: a file is already at " + r.place + " and it is not a memory this app recognizes (" + String(r.cause).replace(/_/g, " ") + "). Nothing was changed. Check it from the terminal.");
    }
    form.hidden = false;
    sync();
    return tell("hitl", "needs_you", "NEEDS YOU: your private memory has not been created yet. Your conversations and notes need it.");
  }
  function sync() { btn.disabled = busy || !ok.checked || phrase.value.trim().toLowerCase() !== want; }

  async function read() {
    try {
      const r = await fetch("/api/memoria/inicio", { cache: "no-store" });
      paint(await r.json());
    } catch { paint({ cause: "server_unreachable" }); }
  }
  async function create(e) {
    if (!e.isTrusted || btn.disabled) return;
    busy = true; sync();
    tell("working", "waiting", "WORKING: creating your private memory…");
    try {
      const r = await fetch("/api/memoria/inicio", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ schema: "preceptoros.memory-create/1", confirm: ok.checked, phrase: phrase.value }) });
      const body = await r.json();
      if (body.outcome === "REFUSED" && body.state !== "UNKNOWN") { busy = false; paint(body); return tell("refused", "refused", "REFUSED: " + String(body.cause).replace(/_/g, " ") + ". Nothing was created."); }
      paint(body);
      if (body.outcome === "CREATED") { const h = $("memoria-inicio-titulo"); if (h) { h.tabIndex = -1; h.focus(); } }
    } catch { tell("no_data", "silent", "NO_DATA: no answer from this device's server. Nothing is known to be created; read again."); }
    busy = false;
  }
  ok.addEventListener("change", sync);
  phrase.addEventListener("input", sync);
  btn.addEventListener("click", create);
  const tab = $("tab-ajustes");
  if (tab) tab.addEventListener("click", read);
  read();
  root.PreceptorMemoria = Object.freeze({ read });
})(typeof window !== "undefined" ? window : globalThis);
