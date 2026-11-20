"use strict";
const assert = require("node:assert/strict");
const N = require("../interface/notebook.js");

const receipt = "a".repeat(64);
const fixture = {
  schema: "preceptoros.notebook-readonly/0",
  agents_status: "DECLARADO",
  shared_source_ref: receipt,
  agents_cause: null,
  agents: [{ id: "claude-1", name: "Claude", role: "Builder",
             status: "OBSERVADO", cause: "recent_declared_heartbeat",
             last_seen: "2026-11-11T10:00:00Z", receipt_sha256: receipt }],
  reports: [{ kind: "WBR", status: "DECLARADO",
              summary: "1 tested PR", period: "2026-W46",
              measured_at: "2026-11-11T10:00:00Z", receipt_sha256: receipt,
              cause: "origin_receipt_not_independently_verified" }]
};
const state = N.projectNotebook(fixture);
assert.equal(state.agents[0].status, "OBSERVADO");
assert.equal(state.reports[0].status, "DECLARADO");
assert.equal(state.reports[0].summary, "1 tested PR");
assert.equal(N.projectNotebook({ agents: [], reports: [] }), null);
assert.equal(N.projectNotebook({ ...fixture, agents: [{ ...fixture.agents[0], status: "LIVE" }] }).agents[0].status, "NO_DATA");

const now = Date.parse("2026-11-11T10:00:00Z");
const fresh = N.projectHarness({
  estado: "MEDIDO", medido: "2026-11-11T09:59:50Z",
  bucles: [{ unidad: "weekly", ultima: "yesterday", proxima: "tomorrow" }]
}, now);
assert.equal(fresh.rows.length, 1);
const stale = N.projectHarness({
  estado: "MEDIDO", medido: "2026-11-11T08:30:00Z", bucles: [{ unidad: "weekly" }]
}, now);
assert.equal(stale.rows.length, 0);
assert.equal(stale.cause, "sensor_stale_or_missing");
assert.equal(N.projectHarness(null, now).cause, "sensor_invalid");

const shared = N.projectSharedRack({
  ...fixture,
  observed_at: "2026-11-11T10:00:00Z",
  agents_status: "DECLARADO",
  bench: [{ state: "RECHECKED", sentence: "Fixture only" }],
  receipts: [{ status: "DECLARED", tool: "read" }]
}, {
  estado: "ok", medido: "2026-11-11T09:59:50Z",
  bucles: [
    { unidad: "daily", activo: true, resultado: "DECLARED" },
    { unidad: "weekly", activo: false, resultado: "NO_DATA" }
  ]
}, now);
assert.equal(shared.state, "DECLARED");
assert.equal(shared.sourceRef, receipt);
assert.equal(N.projectSharedRack({ ...fixture, shared_source_ref: "forged", bench: [], receipts: [] }, null, now).sourceRef, null);
assert.equal(shared.benchmarks, 1);
assert.equal(shared.receipts, 1);
assert.equal(shared.timers, 2);
assert.equal(shared.enabledTimers, 1);
assert.equal(shared.processState, "NO_DATA");
assert.equal(shared.processCause, "live_process_binding_missing");
assert.equal(shared.agentsState, "DECLARED");
assert.equal(N.projectSharedRack(null, null, now).state, "NO_DATA");
assert.equal(N.projectSharedRack({ ...fixture, bench: [] }, null, now).state, "NO_DATA");
const staleShared = N.projectSharedRack({
  ...fixture, bench: [], receipts: [], observed_at: "2026-11-11T10:00:00Z"
}, {
  estado: "ok", medido: "2026-11-11T08:30:00Z",
  bucles: [{ unidad: "expired", activo: true }]
}, now);
assert.equal(staleShared.timers, 0);
assert.equal(staleShared.harnessCause, "sensor_stale_or_missing");
assert.equal(staleShared.processState, "NO_DATA");


const cast = N.projectLabCast({
  estado: "MEDIDO", medido: "2026-11-11T09:59:50Z",
  bucles: [
    { unidad: "weekly", descripcion: "Synthetic report", activo: true,
      resultado: "DECLARED", ultima: "yesterday" },
    { unidad: "monthly", descripcion: "Synthetic review", activo: false, resultado: "NO_DATA" }
  ]
}, { ...fixture, observed_at: "2026-11-11T10:00:00Z",
  agents_status: "DECLARADO", shared_source_ref: receipt, receipts: [], bench: [] },
  { schema: "preceptoros.hexelion-tasks/1", state: "NO_DATA",
    cause: "p2_mirror_not_built", tasks: [] },
  { modelos: { mini: { tag: "synthetic-mini", disponible: true },
    grande: { disponible: false, causa: "model_file_missing" },
    soberano_coder: { disponible: false } } },
  { schema: "preceptoros.federated-view/1", backends: [
    { state: "STALE" }, { state: "NO_DATA" }
  ] }, now);
assert.equal(cast.loops.length, 2);
assert.equal(cast.loopsCount, 2);
assert.equal(cast.loops[0].state, "DECLARED");
assert.equal(cast.loops[0].cause, "timer_not_live_process");
assert.match(cast.loops[0].detail, /Synthetic report/);
assert.match(cast.loops[0].detail, /Enabled in timer declaration/);
assert.match(cast.loops[1].detail, /Disabled in timer declaration/);
assert.equal(cast.researchers.length, 1);
assert.equal(cast.researchers[0].state, "DECLARED");
assert.equal(cast.goals.length, 0);
assert.equal(cast.goalsCause, "p2_mirror_not_built");
assert.equal(cast.brains.length, 5);
assert.equal(cast.brains[0].state, "DECLARED");
assert.equal(cast.brains[0].cause, "installed_is_not_inference");
assert.equal(cast.brains[1].state, "NO_DATA");
assert.equal(cast.brains[3].state, "STALE");
assert.equal(cast.brains[4].cause, "android_model_runtime_not_benchmarked");
assert.equal(cast.sourceRef, receipt);
assert.equal(cast.loops.some(x => x.state === "LIVE"), false);
const absentCast = N.projectLabCast(null, null, null, null, null, now);
assert.equal(absentCast.loops.length, 0);
assert.equal(absentCast.researchers.length, 0);
assert.equal(absentCast.goals.length, 0);
assert.equal(absentCast.brains[3].state, "NO_DATA");
assert.equal(absentCast.sourceRef, null);

console.log("notebook_cases: OK (schema, status, loop freshness, fail-closed)");
