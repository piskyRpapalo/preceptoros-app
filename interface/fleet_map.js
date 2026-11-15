/* Fleet · Harness. One hexagon per node the app can actually read; each of its six sides is one fact.
 * A side drawn thick is measured on, thin is measured off, dashed is NO_DATA (with its cause in the list below).
 * Today the app reads one node, its own host (/api/estado); the other nodes need the fleet contract (heartbeat,
 * role, models) from the brain's owner, so the band says NO_DATA instead of drawing devices it cannot see.
 * ?fleet=synthetic adds three SYNTHETIC nodes, dashed and labelled, to check the drawing: never real devices.
 * The picture is aria-hidden; the list under it says the same facts in words. Nothing moves.
 */
(function (root) {
  "use strict";
  const doc = root.document, NS = "http://www.w3.org/2000/svg";
  const sides = ["answers", "brain file", "engine", "heartbeat", "task", "witness"];
  const noContract = "no fleet contract yet";

  // facts(estado) -> the app host's six sides from /api/estado: {side, state: on|off|nodata, word, cause}. Pure.
  function facts(d) {
    const ok = d && d.estado === "ok", c = ok && d.cerebro && typeof d.cerebro === "object" ? d.cerebro : null;
    const nd = (side, cause) => ({ side, state: "nodata", word: "NO_DATA", cause });
    return [
      ok ? { side: "answers", state: "on", word: "yes", cause: "" } : nd("answers", "the host did not answer"),
      !c ? nd("brain file", "not reported")
        : c.causa == null && Number(c.bytes) > 0 ? { side: "brain file", state: "on", word: "present", cause: "" }
          : { side: "brain file", state: "off", word: "missing", cause: "its file is not on this disk" },
      !ok || typeof d.motor !== "boolean" ? nd("engine", "not reported")
        : { side: "engine", state: d.motor ? "on" : "off", word: d.motor ? "running" : "not running", cause: "" },
      nd("heartbeat", noContract), nd("task", noContract), nd("witness", noContract),
    ];
  }

  // node(id, label, sides, synthetic) -> a cell. Its state is the weakest honest word: OBSERVED only when a side
  // was measured; SYNTHETIC whenever the facts are made up, whatever they say.
  function node(id, label, list, synthetic) {
    const seen = list.some((f) => f.state !== "nodata");
    return { id, label, facts: list, synthetic: Boolean(synthetic), state: synthetic ? "SYNTHETIC" : seen ? "OBSERVED" : "NO_DATA" };
  }

  // axial(i) -> [q, r] for the i-th cell: the centre, then the first ring clockwise. Pure.
  const ring = [[0, 0], [1, -1], [1, 0], [0, 1], [-1, 1], [-1, 0], [0, -1]];
  function axial(i) { return ring[i % ring.length]; }

  // corners(cx, cy, s) -> six pointy-top corners, clockwise from the top. Pure.
  function corners(cx, cy, s) {
    return [0, 1, 2, 3, 4, 5].map((k) => { const a = Math.PI / 180 * (60 * k - 90); return [cx + s * Math.cos(a), cy + s * Math.sin(a)]; });
  }

  function synthetic() {
    const fake = (on) => sides.map((side, k) => ({ side, state: on[k], word: on[k] === "nodata" ? "NO_DATA" : on[k], cause: on[k] === "nodata" ? "synthetic gap" : "" }));
    return [node("syn-a", "Synthetic A", fake(["on", "on", "on", "on", "off", "nodata"]), true),
      node("syn-b", "Synthetic B", fake(["on", "off", "off", "nodata", "nodata", "nodata"]), true),
      node("syn-c", "Synthetic C", fake(["nodata", "nodata", "nodata", "nodata", "nodata", "nodata"]), true)];
  }

  function el(tag, cls, text) { const e = doc.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; }

  function draw(box, cells) {
    const s = 34, w = Math.sqrt(3) * s, svg = doc.createElementNS(NS, "svg");
    const at = cells.map((c, i) => { const [q, r] = axial(i); return [1.18 * w * (q + r / 2), 1.18 * s * 1.5 * r]; });
    const xs = at.map((p) => p[0]), ys = at.map((p) => p[1]), m = s + 6; // the frame fits the cells drawn, no more
    svg.setAttribute("viewBox", [Math.min(...xs) - m, Math.min(...ys) - m, Math.max(...xs) - Math.min(...xs) + 2 * m, Math.max(...ys) - Math.min(...ys) + 2 * m].map((v) => v.toFixed(1)).join(" "));
    svg.setAttribute("aria-hidden", "true"); svg.classList.add("fleet-svg"); svg.style.maxWidth = (cells.length > 1 ? 240 : 110) + "px";
    cells.forEach((c, i) => {
      const [cx, cy] = at[i], p = corners(cx, cy, s - 2), g = doc.createElementNS(NS, "g");
      g.setAttribute("class", "fleet-cell" + (c.synthetic ? " is-synthetic" : "")); g.dataset.id = c.id;
      const face = doc.createElementNS(NS, "polygon");
      face.setAttribute("points", p.map((x) => x.map((v) => v.toFixed(1)).join(",")).join(" ")); face.setAttribute("class", "fleet-face");
      g.appendChild(face);
      c.facts.forEach((f, k) => {
        const a = p[k], b = p[(k + 1) % 6], ln = doc.createElementNS(NS, "line");
        ln.setAttribute("x1", a[0].toFixed(1)); ln.setAttribute("y1", a[1].toFixed(1)); ln.setAttribute("x2", b[0].toFixed(1)); ln.setAttribute("y2", b[1].toFixed(1));
        ln.setAttribute("class", "fleet-side side-" + f.state); g.appendChild(ln);
      });
      const t = doc.createElementNS(NS, "text"); t.setAttribute("x", cx.toFixed(1)); t.setAttribute("y", (cy + 4).toFixed(1));
      t.setAttribute("text-anchor", "middle"); t.setAttribute("class", "fleet-label"); t.textContent = c.short || c.label.split(" ").map((x) => x[0]).join("").slice(0, 3);
      g.appendChild(t);
      g.addEventListener("click", () => { const d = doc.getElementById("fleet-" + c.id); if (d) { d.open = true; d.querySelector("summary").focus(); } });
      svg.appendChild(g);
    });
    box.appendChild(svg);
  }

  function list(box, cells) {
    const ul = el("ul", "fleet-list"); ul.setAttribute("aria-label", "Nodes and their six facts");
    cells.forEach((c) => {
      const li = el("li"), d = el("details"), sum = el("summary"), E = root.PreceptorEvidence;
      d.id = "fleet-" + c.id; d.dataset.state = c.state;
      sum.append(c.label + " · ", E ? E.make(doc, c.synthetic ? "NO_DATA" : c.state, c.synthetic ? "synthetic, not a device" : "") : doc.createTextNode(c.state));
      if (c.synthetic) sum.append(el("span", "fleet-syn", " SYNTHETIC"));
      const ol = el("ol", "fleet-facts");
      c.facts.forEach((f) => { const x = el("li", "fact-" + f.state, f.side + ": " + f.word + (f.cause ? " (" + f.cause + ")" : "")); x.dataset.state = f.state; ol.appendChild(x); });
      d.append(sum, ol); li.appendChild(d); ul.appendChild(li);
    });
    box.appendChild(ul);
  }

  async function read() {
    const box = doc.getElementById("fleet"), line = doc.getElementById("fleet-estado");
    if (!box) return null;
    let d = null;
    try { const r = await fetch("/api/estado", { cache: "no-store" }); d = r.ok ? await r.json() : null; } catch { d = null; }
    const cells = [Object.assign(node("host", "App host", facts(d), false), { short: "Host" })];
    if (/[?&]fleet=synthetic\b/.test(root.location ? root.location.search : "")) cells.push(...synthetic());
    box.replaceChildren(); draw(box, cells); list(box, cells);
    if (line) line.textContent = "Fleet · 1 node read (this app's host) · other nodes: NO_DATA · " + noContract + ".";
    return cells;
  }

  if (typeof module === "object" && module.exports) module.exports = { facts, node, axial, corners, synthetic, sides };
  root.PreceptorFleet = Object.freeze({ facts, node, read });
  if (doc && doc.getElementById("fleet")) {
    const panel = doc.getElementById("panel-harness"), again = doc.querySelector('[data-refrescar="harness"]');
    let shown = false;
    const look = () => { const open = panel && !panel.hidden; if (open && !shown) read(); shown = open; };
    if (panel) new root.MutationObserver(look).observe(panel, { attributes: true, attributeFilter: ["hidden"] });
    if (again) again.addEventListener("click", () => read());
    look();
  }
})(typeof window !== "undefined" ? window : globalThis);
