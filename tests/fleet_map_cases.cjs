// Fleet cases (Harness). Run: node tests/fleet_map_cases.cjs
// Six sides, six facts; only what /api/estado measures is drawn as measured; synthetic is always synthetic.
const assert = require("assert");
const F = require("../interface/fleet_map.js");
const live = { estado: "ok", motor: false, cerebro: { nombre: "q.gguf", bytes: 2497281120, causa: null } };
const f = F.facts(live);
assert.deepStrictEqual(f.map((x) => x.side), F.sides);
assert.deepStrictEqual(f.map((x) => x.state), ["on", "on", "off", "nodata", "nodata", "nodata"]);
assert.strictEqual(f[2].word, "not running");
for (const x of f.slice(3)) assert.strictEqual(x.cause, "no fleet contract yet");
// A brain file the server says is missing is off, never present.
assert.strictEqual(F.facts({ estado: "ok", motor: true, cerebro: { bytes: null, causa: "x" } })[1].state, "off");
assert.strictEqual(F.facts({ estado: "ok", motor: true, cerebro: { bytes: null, causa: null } })[1].state, "off", "no bytes, no file");
assert.strictEqual(F.facts({ estado: "ok", motor: true, cerebro: { bytes: 5, causa: "gone" } })[1].state, "off", "a cause wins");
// No answer: every side NO_DATA with a cause; the node is NO_DATA, never OBSERVED.
for (const bad of [null, {}, { estado: "error" }]) {
  const g = F.facts(bad);
  assert.ok(g.every((x) => x.state === "nodata" && x.cause.length > 0));
  assert.strictEqual(F.node("host", "App host", g, false).state, "NO_DATA");
}
// An engine flag that is not a boolean is not a measurement.
assert.strictEqual(F.facts({ estado: "ok", motor: "yes" })[2].state, "nodata");
assert.strictEqual(F.node("host", "App host", f, false).state, "OBSERVED");
// Synthetic nodes are SYNTHETIC whatever their sides say, and are never named like a device.
const syn = F.synthetic();
assert.strictEqual(syn.length, 3);
for (const s of syn) { assert.strictEqual(s.state, "SYNTHETIC"); assert.ok(s.synthetic); assert.ok(/^Synthetic /.test(s.label)); }
// Geometry: distinct cells, and six corners at the same distance from the centre.
const cells = [0, 1, 2, 3, 4, 5, 6].map((i) => F.axial(i).join(","));
assert.strictEqual(new Set(cells).size, 7);
const c = F.corners(10, 20, 30);
assert.strictEqual(c.length, 6);
for (const [x, y] of c) assert.ok(Math.abs(Math.hypot(x - 10, y - 20) - 30) < 1e-9);
assert.ok(Math.abs(c[0][0] - 10) < 1e-9 && c[0][1] < 20, "the first corner is the top");
console.log(JSON.stringify({ schema: "preceptoros.fleet-map-cases/1", ok: true }));
