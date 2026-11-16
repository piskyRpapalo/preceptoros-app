/* Evidence chip (visual-coherence commission). One visual word for how much a figure can be trusted.
 * Presentation only: the state comes from the data (Codex CLI owns it); this file never decides a state.
 * Shape + word + colour, never colour alone: the shape survives forced-colors and greyscale, and the word
 * is what a screen reader hears (aria-label is the same text the eye reads). English labels: the MVP is English.
 */
(function (root) {
  "use strict";
  // Input words from the data (MEDIDO/DECLARADO come from the records) and the Mesa's vocabulary.
  var tabla = {
    VERIFIED: { word: "VERIFIED", glyph: "■", tone: "ok", says: "checked again by this app" },
    OBSERVED: { word: "OBSERVED", glyph: "●", tone: "ok", says: "measured on this device or rack" },
    MEDIDO: { word: "OBSERVED", glyph: "●", tone: "ok", says: "measured on this device or rack" },
    DECLARED: { word: "DECLARED", glyph: "◇", tone: "warn", says: "declared by a person, not measured" },
    DECLARADO: { word: "DECLARED", glyph: "◇", tone: "warn", says: "declared by a person, not measured" },
    STALE: { word: "STALE", glyph: "▲", tone: "warn", says: "was true, but too old to count now" },
    NO_DATA: { word: "NO DATA", glyph: "□", tone: "quiet", says: "not measured; the cause is shown" },
    REFUSED: { word: "REFUSED", glyph: "✕", tone: "stop", says: "asked for, and the rule said no" },
    DENEGADO: { word: "REFUSED", glyph: "✕", tone: "stop", says: "asked for, and the rule said no" }
  };

  function normal(state) {
    var key = String(state || "").trim().toUpperCase().replace(/[\s-]+/g, "_");
    return tabla[key] ? key : "NO_DATA";
  }

  // Returns the text the person reads and hears, e.g. "NO DATA · lab federated not on ref".
  function text(state, cause) {
    var t = tabla[normal(state)];
    var c = cause ? String(cause).replace(/_/g, " ").slice(0, 80) : "";
    return t.word + (c ? " · " + c : "");
  }

  function make(doc, state, cause) {
    var key = normal(state), t = tabla[key];
    var span = doc.createElement("span");
    span.className = "evidence-chip evidence-" + t.tone;
    span.dataset.state = key;
    span.setAttribute("aria-label", text(state, cause));
    var glyph = doc.createElement("span");
    glyph.className = "evidence-glyph";
    glyph.setAttribute("aria-hidden", "true");
    glyph.textContent = t.glyph;
    span.appendChild(glyph);
    span.appendChild(doc.createTextNode(" " + text(state, cause)));
    span.title = t.says;
    return span;
  }

  var api = { text: text, normal: normal, make: make, table: tabla };
  if (typeof module !== "undefined" && module.exports) { module.exports = api; }
  root.PreceptorEvidence = api;

  /* PreceptorEstado · one grammar for what a participant (preceptor, task, loop, run) is doing, shared by Talk, Lab,
   * Notebook and Command. Real state -> visual (glyph + word + tone + line) -> accessible sentence -> Acho reading.
   * It never decides from a clock, an open conversation or a guess: only typed rows of existing contracts count
   *   heartbeat  notebook-agents/0 (OBSERVADO / STALE / NO_DATA, with its receipt sha256)
   *   task       hexelion-tasks/1 (tareas_hexelion states)
   *   turn       turnos_hexelion states
   *   receipt    notebook receipts (result ok / refused / failed, status DECLARED / STALE)
   *   loop       Harness loop sensor (systemd Result word, read under 5 minutes old)
 *   bench      a Lab benchmark run (attempted and failed counts, as measured)
   *   hitl       a pending signature count the tray reports for this participant
   *   run        a declared running run with its receipt: no producer exists yet, so in real use it never appears
 *   absent     no row exists, and the reader says why (its cause is shown as given)
   * Anything else (a message in the thread, a timer, the UI) is not evidence: NO_DATA with that cause.
   * Words stay on screen; the glyph and the line survive greyscale and forced colours; motion only for WORKING, and
   * none under prefers-reduced-motion. Glyphs agree with the evidence chip: ■ verified, ✕ refused, ▲ stale, □ no data. */
  var estados = {
    available: { word: "AVAILABLE", glyph: "○", tone: "ok", line: "solid", acho: "answer", says: "declared ready: a recent heartbeat with its receipt" },
    working: { word: "WORKING", glyph: "◉", tone: "ok", line: "double", acho: "answer", says: "a run declared in progress, with its receipt, seconds ago" },
    waiting: { word: "WAITING", glyph: "◌", tone: "quiet", line: "dotted", acho: "waiting", says: "claimed or asked, and no result is recorded yet" },
    blocked: { word: "BLOCKED", glyph: "⊘", tone: "stop", line: "dashed", acho: "refused", says: "it stopped and cannot continue on its own" },
    hitl: { word: "NEEDS YOU", glyph: "◆", tone: "warn", line: "solid", acho: "needs_you", says: "waiting for your signature or decision" },
    done: { word: "DONE", glyph: "■", tone: "ok", line: "double", acho: "verified", says: "a result is recorded" },
    refused: { word: "REFUSED", glyph: "✕", tone: "stop", line: "solid", acho: "refused", says: "asked for, and the rule said no" },
    stale: { word: "STALE", glyph: "▲", tone: "warn", line: "dotted", acho: "uncertain", says: "was true, but too old to count now" },
    loading: { word: "READING", glyph: "⋯", tone: "quiet", line: "dashed", acho: "waiting", says: "this screen is reading the sources now" },
    no_data: { word: "NO DATA", glyph: "□", tone: "quiet", line: "dotted", acho: "silent", says: "no source says what it is doing" }
  };
  var taskWords = { DONE_CHECKED: ["done", "VERIFIED"], DONE_UNCHECKED: ["done", "DECLARED"], NEEDS_YOUR_AUTHORIZATION: ["hitl", "DECLARED"],
    FAILED: ["blocked", "DECLARED"], NO_RESULT_RECORDED: ["waiting", "DECLARED"] };
  var turnWords = { ANSWERED: ["done", "OBSERVED"], ACTED: ["done", "VERIFIED"], REPLIED: ["done", "OBSERVED"], LOCAL_SENSOR: ["done", "OBSERVED"],
    ACTION_REFUSED: ["refused", "OBSERVED"] };
  var hex64 = /^[0-9a-f]{64}$/, stampRe = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$/;
  var order = ["working", "hitl", "refused", "blocked", "waiting", "done", "available", "stale", "loading", "no_data"];

  function nodata(cause, source) { return { state: "no_data", cause: String(cause || "no_source").slice(0, 72), source: source || "", evidence: "NO_DATA" }; }
  function when(e, now) {
    if (e.at === undefined) return { ok: true, t: null };
    if (typeof e.at !== "string" || !stampRe.test(e.at)) return { ok: false, cause: "timestamp_invalid" };
    var t = Date.parse(e.at);
    return t > now + 5000 ? { ok: false, cause: "future_timestamp" } : { ok: true, t: t };
  }
  // one(e, now) -> {state, cause, source, evidence, t} for one typed row, or NO_DATA with the reason it was not believed.
  function one(e, now) {
    if (!e || typeof e !== "object") return nodata("not_evidence");
    var s = e.source, w = when(e, now);
    if (!w.ok) return nodata(w.cause, s);
    var r = function (state, evidence, cause) { return { state: state, cause: cause || "", source: s, evidence: evidence, t: w.t }; };
    if (s === "heartbeat") {
      if (typeof e.receipt !== "string" || !hex64.test(e.receipt)) return nodata("heartbeat_without_receipt", s);
      if (e.status === "OBSERVADO") return r("available", "DECLARED", "recent declared heartbeat");
      if (e.status === "STALE") return r("stale", "STALE", "heartbeat expired");
      return nodata(e.cause || "heartbeat_no_data", s);
    }
    if (s === "task") return taskWords[e.state] ? r(taskWords[e.state][0], taskWords[e.state][1], String(e.state).toLowerCase()) : nodata("task_" + String(e.state || "unknown").toLowerCase(), s);
    if (s === "turn") return turnWords[e.state] ? r(turnWords[e.state][0], turnWords[e.state][1], String(e.state).toLowerCase()) : nodata("turn_" + String(e.state || "unknown").toLowerCase(), s);
    if (s === "receipt") {
      if (typeof e.receipt !== "string" || !hex64.test(e.receipt)) return nodata("receipt_without_sha", s);
      if (e.status === "STALE") return r("stale", "STALE", "receipt too old");
      if (e.status !== "DECLARED") return nodata("receipt_no_data", s);
      if (e.result === "ok") return r("done", "DECLARED", "command ended ok");
      if (e.result === "refused") return r("refused", "DECLARED", "command refused by its fence");
      return r("blocked", "DECLARED", "command failed");
    }
    if (s === "loop") {
      if (e.fresh !== true) return nodata("loop_sensor_stale_or_missing", s);
      if (e.result === "success") return r("done", "OBSERVED", "last run ended with success");
      if (/^(exit-code|signal|core-dump|timeout|start-limit-hit|resources|watchdog)$/.test(String(e.result))) return r("blocked", "OBSERVED", "last run ended: " + e.result);
      return nodata("loop_result_unknown", s);
    }
    if (s === "bench") {
      if (!Number.isSafeInteger(e.attempted) || !Number.isSafeInteger(e.failed) || e.attempted < 1 || e.failed < 0 || e.failed > e.attempted) return nodata("bench_counts_invalid", s);
      return e.failed ? r("blocked", "OBSERVED", e.failed + " of " + e.attempted + " runs failed") : r("done", "OBSERVED", e.attempted + " runs, none failed");
    }
    if (s === "hitl") {
      if (!Number.isSafeInteger(e.pending) || e.pending < 0) return nodata("pending_count_invalid", s);
      if (e.pending > 0) return r("hitl", "OBSERVED", e.pending + " awaiting you");
      // A counted zero is information; a zero nobody counted is not (measured must be said, never assumed).
      return e.measured === true ? r("done", "OBSERVED", "nothing awaits you") : nodata("zero_not_measured", s);
    }
    if (s === "run") {
      if (e.state !== "RUNNING" || typeof e.receipt !== "string" || !hex64.test(e.receipt) || w.t === null) return nodata("run_without_receipt_or_time", s);
      return now - w.t <= 120000 ? r("working", "DECLARED", "run declared in progress") : r("stale", "STALE", "run declaration too old");
    }
    if (s === "loading") return r("loading", "NO_DATA", "reading");
    if (s === "absent") return nodata(String(e.cause || "no_source"), s);   // the reader knows why there is no row
    return nodata("not_evidence:" + String(s || "none").slice(0, 24), s);
  }
  // fromEvidence(rows, now) -> one state. The live overlays (a running run, a pending signature) win; then the newest
  // result; then presence (heartbeat). Nothing believed -> NO_DATA with the first cause seen.
  function fromEvidence(rows, now) {
    now = typeof now === "number" ? now : Date.now();
    var all = (Array.isArray(rows) ? rows : [rows]).map(function (e) { return one(e, now); });
    var real = all.filter(function (x) { return x.state !== "no_data"; });
    if (!real.length) return all[0] || nodata("no_source");
    var pick = function (names) { return real.filter(function (x) { return names.indexOf(x.state) >= 0; }); };
    var live = pick(["working", "hitl"]);
    if (live.length) return live.sort(function (a, b) { return order.indexOf(a.state) - order.indexOf(b.state); })[0];
    var results = pick(["refused", "blocked", "waiting", "done"]);
    if (results.length) return results.sort(function (a, b) { return (b.t || 0) - (a.t || 0) || order.indexOf(a.state) - order.indexOf(b.state); })[0];
    return real.sort(function (a, b) { return order.indexOf(a.state) - order.indexOf(b.state); })[0];
  }
  function sentence(name, x) {
    var e = estados[x.state] || estados.no_data;
    return (name ? name + ": " : "") + e.word + (x.cause ? " · " + String(x.cause).replace(/_/g, " ") : "") + " · evidence " + text(x.evidence);
  }
  // makeEstado(doc, x, name) -> the badge. The same sentence is what the eye reads in full, the reader hears, and
  // data-* carries for Acho and the machine (data-estado, data-acho, data-tone, data-line, data-source, data-cause).
  function makeEstado(doc, x, name) {
    x = x && estados[x.state] ? x : nodata("no_source");
    var e = estados[x.state], span = doc.createElement("span");
    span.className = "part-estado estado-" + x.state + " estado-" + e.tone;
    span.dataset.estado = x.state; span.dataset.acho = e.acho; span.dataset.tone = e.tone; span.dataset.line = e.line;
    span.dataset.source = x.source || ""; span.dataset.cause = x.cause || ""; span.dataset.evidence = x.evidence || "NO_DATA";
    var g = doc.createElement("span"); g.className = "estado-glyph"; g.setAttribute("aria-hidden", "true"); g.textContent = e.glyph;
    var AM = root.AchoMotion;
    if (AM && AM.spectrum && AM.vector) { var mark = AM.spectrum(AM.vector("estado|" + x.state, AM.expressions[e.acho] ? AM.expressions[e.acho].form : undefined), "estado-mark", "sky"); g.appendChild(mark); }
    var w = doc.createElement("span"); w.className = "estado-word"; w.textContent = e.word;
    var sr = doc.createElement("span"); sr.className = "sr"; sr.textContent = " · " + sentence("", x).replace(/^[A-Z ]+ · ?/, "");
    span.append(g, w, sr);
    span.title = e.says + (x.cause ? " (" + x.cause + ")" : "");
    return span;
  }
  var estadoApi = { states: estados, order: order, one: one, fromEvidence: fromEvidence, sentence: sentence, make: makeEstado };
  if (typeof module !== "undefined" && module.exports) { module.exports.estado = estadoApi; }
  root.PreceptorEstado = estadoApi;
})(typeof window !== "undefined" ? window : globalThis);
