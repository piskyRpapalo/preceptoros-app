// Cabin cases (HEXELION V1, Talk). Run: node tests/cabin_brain_cases.cjs
// The band and the answer's foot show what the server and the thread say; they never guess a model or a state.
const assert = require("assert");
const C = Object.assign({}, require("../interface/conversacion.js"), require("../interface/cabin_brain.js"));
// Provenance: a model only when the thread names one; a door or sensor is «not a model»; the person has no foot.
assert.strictEqual(C.provenance({ kind: "private", model: "hexelion:latest" }), "model · hexelion:latest");
assert.strictEqual(C.provenance({ kind: "door" }), "not a model");
assert.strictEqual(C.provenance({ kind: "sensor" }), "not a model");
assert.strictEqual(C.provenance({ kind: "private" }), "model not recorded");
assert.strictEqual(C.provenance({ kind: "private", model: "" }), "model not recorded");
assert.strictEqual(C.provenance({ kind: "person", model: "x" }), "");
// Brain: the server's own package (shape measured on the local app 2026-11-15).
const pkg = { estado: "ok", en_uso: { cual: "base", motivo: "no hay cerebro afinado declarado", nombre: "qwen3-4b.gguf" },
  opciones: [{ cual: "base", disponible: true, causa: null, nombre: "qwen3-4b.gguf" },
             { cual: "afinado", disponible: false, causa: "no hay cerebro afinado declarado", nombre: null }] };
const v = C.brainView(pkg);
assert.strictEqual(v.state, "OBSERVED");
assert.strictEqual(v.which, "base");
assert.strictEqual(v.options.length, 2);
assert.deepStrictEqual(v.options.map((o) => [o.which, o.available, o.on]), [["base", true, true], ["afinado", false, false]]);
assert.strictEqual(v.options[1].cause, "no tuned brain declared");
// What a person reads is English; the server's own words stay for the machine (data-cause).
assert.deepStrictEqual(v.options.map((o) => o.label), ["Base", "Tuned"]);
assert.strictEqual(v.options[1].raw, "no hay cerebro afinado declarado");
assert.strictEqual(v.ready, true);
for (const o of v.options) assert.ok(!/cerebro|afinado|hay|ruta|disco/.test(o.label + o.cause), "spanish on screen: " + o.label + o.cause);
// A reason the band does not know is never shown raw.
assert.strictEqual(C.brainView({ en_uso: { cual: "base" }, opciones: [{ cual: "x", disponible: false, causa: "motivo raro" }] }).options[0].cause,
  "the server gave a reason");
// In use but its file is missing: the band says it is not ready instead of looking fine.
const missing = C.brainView({ en_uso: { cual: "base" }, opciones: [{ cual: "base", disponible: false, causa: "la ruta declarada no existe en el disco" }] });
assert.strictEqual(missing.ready, false);
assert.strictEqual(missing.options[0].cause, "its file is not on this disk");
// An option that does not say it is available is not available (no field = no claim).
const silent = C.brainView({ en_uso: { cual: "base" }, opciones: [{ cual: "afinado" }] });
assert.strictEqual(silent.options[0].available, false);
assert.strictEqual(silent.options[0].cause, "not available");
// Heads have no contract yet: always NO_DATA with its cause, never invented.
assert.deepStrictEqual(v.heads, { state: "NO_DATA", cause: "no heads contract yet" });
// Anything else is NO_DATA with a cause, never a brain.
for (const bad of [null, {}, { en_uso: null, opciones: [] }, { en_uso: { cual: 3 }, opciones: [] }, { en_uso: { cual: "base" } }]) {
  const b = C.brainView(bad);
  assert.strictEqual(b.state, "NO_DATA");
  assert.ok(b.cause.length > 0);
  assert.strictEqual(b.options.length, 0);
}
console.log(JSON.stringify({ schema: "preceptoros.cabin-brain-cases/1", ok: true }));
