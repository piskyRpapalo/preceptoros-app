# Round 5 · 44 px touch targets measured on the live Beelink APP

**State: PROPOSED · HITL.** CSS only; no panel, flow or API changed.

Live read-only audit of `127.0.0.1:8742/app` (2026-11-21, 390/420/780 px, ×2): six panels, headings, version line,
ten-stage ladder, locked Create building, model dialog and NO_DATA causes all correct; no page error, no write.
One defect class: controls under 44 px in Operations Data (training-consent summary 19, privacy switch 24,
nested summary 15, Path/Detail 19), Lab (Rack Lab link 18) and My node (consent rows 13, Send to Aduana 19).

Fix: one block at the end of `interface/app.css`; the switch keeps its 24 px pill with a transparent 10 px border
(44 px hit area). `app.css?v=57`, shell cache v243.

Test: `tests/app_touch_targets.browser.cjs` opens every section of the three panels and measures every visible
control at three widths (3/3 ×2); `test_app_touch_targets.py` in the gate. Sabotage: drop the button rule or the
switch rule → red.

Seen, not fixed here: the privacy switch pill does not paint on `main` either (before/after screenshots equal).
