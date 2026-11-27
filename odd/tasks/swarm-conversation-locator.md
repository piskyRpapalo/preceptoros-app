# R13 — Private SWARM conversation locator

Status: PROPOSED / documentation only. Scope: one feature, no runtime or permission changes.

## Objective and sources

Make existing preceptors easy to locate from the private APP Talk surface when provider conversation titles change. Reuse `interface/superbot_talk.js` (plan references, not verified roster), `interface/app.html` Agents disclosure, existing plan/roster and receipt projection, and the canonical Acho state. No duplicate registry, chat, daemon or endpoint. Source: repository AGENTS.md, current main 868e04d3; existing Talk idempotency task; SWARM R13 I/H/E/B responsibility delta. The owner requested documentation of this feature; no execution or deployment approval is implied.

## Proposed view

Extend the existing Agents disclosure on the private Talk panel. Each row identifies a stable preceptor, optional title/alias, provider and Web/CLI type, mission, last receipt and observed time, dependency and state/cause/source. Keep chat identity distinct from CLI session, CLAIM, GOAL and model. A receipt or link never proves activity.

- Search by stable identity, alias and receipt reference. Rename locally without changing agent identity.
- Optional owner-confirmed private conversation link, stored locally under existing authorized storage rules; absent or ambiguous link shows a search fallback and NO_DATA with cause. No fabricated link, public share link, external discovery, scraping or provider API assumption.
- Opening is user-initiated navigation only, not dispatch, authentication, awakening a chat or approval. Validate the provider destination and show the target when ambiguous; no arbitrary scheme or redirect acceptance. No credentials, prompts, private link IDs or telemetry in GitHub, export, logs, public UI or receipts. CLI controls keep existing gates.
- Accessible keyboard and TalkBack focus, labelled actions, same source/state/cause/freshness in visual, voice and machine projections. Do not speak private URLs unless explicitly requested. No second Acho renderer.

## Acceptance plan (not executed)

1. 12/12 existing roster identities discoverable via verified link or explicit search fallback; zero invented identities or links.
2. Rename/title collision, missing or revoked link, malformed/foreign destination, stale receipt, duplicate mapping, offline/provider unavailable: fail closed with explicit cause; no false LIVE or grant.
3. Open only on explicit selection; no message sent, new chat or session created, or GOAL consumed. Verify private data stays local and is excluded from exports/logs.
4. Compare p50/p95 time to locate a known agent against manual provider search with the same tasks; report failures and denominators. Target 20/20 physical accessibility parity cases on the private mobile surface; measure focus/voice/visual semantics independently.
5. Implement only after owners reconcile existing roster and storage contract. Apply repository served-asset alignment and canonical tests to future code changes; independent judge checks exact HEAD.

## Responsibilities and limits

I: APP integration; H: Acho/accessibility; E/B: transport and identity/source reconciliation; D: independent evaluation; NEXO: coordination. No new authority. NO_DATA(actual private conversation links, Web conversation activity adapter, runtime storage integration, physical mobile/voice test, baseline timing). The next artifact is an isolated view/fixture proposal against existing Talk, not a deployment. This document changes no served assets.
