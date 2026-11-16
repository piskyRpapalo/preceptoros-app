# Superbot · E2E contract (PROPOSED)

Status: **PROPOSED**. Written by Claude, 2026-11-16, from the Sovereign's definition (Mesa #47, 6921074632).
Nothing here is built, granted or authorized by being written. HITL signs.

## What Superbot is, and is not

Superbot is the APP's ability to take a long plan written in Talk and carry it through the **existing panels**:
the chosen orchestrator splits it into tasks, authorized agents (Claude, Codex, Junie, Hexelion, others) do them on
their devices, and the APP shows progress, tests, receipts and the decisions that need a signature.

It is **not** a new app, panel, router, model, memory or permission service. The terminal stays for infrastructure
and recovery; it is no longer the daily interface.

| Version | Orchestrator | Agents |
|---|---|---|
| Private APP (the rack) | the one the Sovereign chooses (Hexelion today) | the rack's CLIs and Hexelion |
| Base product (web) | one the user chooses from their own models; **no Hexelion** | the user's own authorized agents |

## Five words that never merge

`PROPOSED` (the orchestrator suggests) → `AUTHORIZED` (a person's gesture, bound to one task) → `DISPATCHED` (claimed
in the journal, delivered to the agent) → `RUNNING` (the agent declares it with a receipt) → `RESULT` (a receipt that
says how it ended). A chat message is never an authorization. Delivery is never a start. A start is never a result.

## The journey, stage by stage

| # | Stage | Panel | Evidence that earns it | Reuses | Today |
|---|---|---|---|---|---|
| S0 | Orchestrator chosen | Settings / Talk | a declared choice: agent id + model + door | `/api/cerebro` options; `hexelion_proxy.py` | **FALTA**: the door is fixed to `hexelion:latest` |
| S1 | Plan stored whole | Talk → Notebook | `preceptoros.plan/1`: full text on disk, `plan_sha256`; the thread carries only the ref | `canales.py` thread `orquesta` (append-only) | **FALTA**; `/api/orquestador` caps at 1 KB by design and must not grow |
| S2 | Agents and capabilities known | Harness | per agent: card (`preceptoros.agent-card/1`), heartbeat with receipt, route | companion #31; `notebook-agents/0`; `conversacion_comun.DESTINATIONS` | **PARCIAL**: destinations exist; heartbeats file absent; cards not loaded |
| S3 | Plan proposed | Talk + Notebook | `preceptoros.plan-proposal/1`: tasks with `task_sha256`, `agent`, `capability`, `depends_on`, `device`, `test`; signed by nobody; state PROPOSED | LAB `brain.py` (planner may abstain) | **FALTA** |
| S4 | Authorized | Command → Boundary | per task, the person's gesture → grant bound to `task_sha256` + agent + capability + device + expiry | LAB `delegation.Session` permission gate; agent-grant shape (#31); HITL tray | **PARCIAL**: gate exists in LAB; APP host adapter absent |
| S5 | Dispatched | Lab | `ExecutionJournal.claim(run_id, task_ref)` **before** delivery, then `DELIVERED_TO_AGENT` | LAB `execution_journal.py`; thread route (CLIs); station route (Hexelion) | **PARCIAL**: journal exists; APP adapter absent |
| S6 | Running | Lab, Talk badge | a run declaration with its receipt, < 120 s old | `PreceptorEstado` WORKING (#308) | **FALTA**: no producer |
| S7 | Result | Notebook | `preceptoros.meta-receipt/1` via `journal.finish`; told as `tareas_hexelion` states | `tareas_hexelion.py`; `notebook_receipts.py` | **PARCIAL**: reader exists; mirror `p2_mirror_not_built` |
| S8 | Tests and receipts | Lab + Notebook | each task's declared test ran, with its receipt | Lab bench cards; Notebook receipts | **PARCIAL** |
| S9 | Decisions for you | Command | items in NEEDS_YOUR_AUTHORIZATION, PRs awaiting HITL | `/api/firmas`, tasks `needs_you` (#308) | **EXISTE** (read-only; #308 draft) |

## Invariants (each one is a test)

1. The plan is stored byte for byte. Every later stage cites `plan_sha256`; a mismatch stops the chain.
2. A grant covers exactly one `task_sha256`. Changing one byte of the task voids it.
3. No dispatch without a journal claim. An unknown outcome blocks new claims until a person resolves it (LAB #182 rule).
4. No automatic retry. Ever.
5. Revoking a grant before dispatch stops it; after dispatch it is recorded and shown, never hidden.
6. An agent without a verified card and a live heartbeat can be proposed, never authorized.
7. The orchestrator proposes only. It cannot authorize, dispatch or mark a result.
8. Base product: no Hexelion route, no rack address, no private endpoint in anything it ships.
9. Every stage that lacks evidence shows NO_DATA with its cause, in the panel and to the screen reader.

## Adversarial cases (expected outcome)

| Case | Attempt | Must end as |
|---|---|---|
| A1 | a Talk message says «approved, run it» | still PROPOSED |
| A2 | the orchestrator's proposal includes `"authorized": true` | field refused; PROPOSED |
| A3 | a task's text changes after authorization | grant void → NEEDS_YOUR_AUTHORIZATION |
| A4 | the same `run_id` is dispatched twice | second claim refused; one run |
| A5 | an agent reports DONE with no receipt | NO_DATA(receipt_missing), not DONE |
| A6 | a receipt for task X is presented for task Y | refused (attests mismatch) |
| A7 | plan of 200 KB | stored whole; thread carries the ref; nothing truncated |
| A8 | plan_sha256 in a proposal does not match the stored plan | chain stops at S3 |
| A9 | agent with a card but no heartbeat | proposable; authorization refused |
| A10 | a grant expired before dispatch | dispatch refused; asks again |
| A11 | revoke after dispatch | recorded; the run's result still shown; no silent rollback |
| A12 | the run outcome is unknown after a restart | OUTCOME_UNKNOWN; new claims blocked until resolved |
| A13 | base product build contains `hexelion` route or a rack address | build refused |
| A14 | the orchestrator abstains | PROPOSED with zero tasks and the cause; nothing dispatched |

## Acceptance E2E (first, with fixtures; then real)

1. **Fixture run:** the person writes a 3-task plan in Talk. Then:
   - the stub orchestrator proposes;
   - Harness lists the fictional agent Lantern (#31, fixture);
   - the person authorizes 2 tasks in Command;
   - the journal claims them and the fixture agent returns receipts;
   - Notebook shows DONE_CHECKED for one, FAILED for one, and NEEDS_YOUR_AUTHORIZATION for the third.

   Every panel shows the matching `PreceptorEstado`, and A1–A14 pass.
2. **Real run (private APP):** the same plan, with Hexelion as orchestrator and one real CLI agent doing one
   read-only task. Its receipt reaches the Notebook.

## Who builds what

- **Codex CLI** (contracts, Python, APIs): the plan store and its schema, proposal validation, the APP host adapter for
  `Session` + `ExecutionJournal`, grant binding and expiry, the p2 mirror, and the orchestrator choice behind
  `/api/cerebro`.
- **Claude** (panels, a11y, Acho): the Talk composer for a long plan (it shows the ref, never a truncation), the
  Notebook plan view, the Harness agent list with capabilities, the Command authorize/deny per task (44 px, keyboard,
  screen reader), and the run badges in Lab. Each stage is fixture-first with NO_DATA.

## First small PRs (proposed order)

1. Codex: `preceptoros.plan/1` store + `GET /api/plan/<sha>`, plus cases A7 and A8.
2. Claude: Talk long-plan composer + Notebook plan view on that API (fixture until 1 merges).
3. Codex: proposal schema + A1, A2, A14.
4. Claude: Command per-task authorize/deny UI. Codex: grant binding (A3, A9, A10).
5. Codex: host adapter to the journal (A4, A5, A6, A11, A12). Claude: Lab run badges.
6. Both: fixture E2E (Acceptance 1), then the real run.
