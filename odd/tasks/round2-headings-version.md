# Round 2 · Five duplicate titles and the real version in Settings

**State: PROPOSED · HITL.** Stacked on #398 (shell cache v239 → v240).

- Operations Data, Lab, Open World, My node, Settings: the panel `h2` repeated the tab name. The header keeps its
  `h2` and ids (tabs still name their panel; the accessibility tree still has `heading level=2`) but takes no
  visual box or space (`.panel-cabecera.sr`). Talk is untouched.
- Settings now starts with one line naming the product release **only from a verifiable source**:
  Android versionCode 7 → «PreceptorOS APP 1.0 · Android build 7»; 8 → «PreceptorOS APP 1.1 · Android build 8»
  (Android installs v8 over v7 only with the same owner signing key); other codes → `NO_DATA(release_not_named)`;
  Beelink → «Shell <12hex> · NO_DATA(release_manifest_unverified)»; nothing → `NO_DATA(release_manifest_unverified)`.
  It reuses the existing version script; the Talk version line stays the single live announcement.
- Contract asked of Codex (optional): a read-only release manifest for the Beelink shell (product name, edition,
  artefact provenance) if the Beelink should ever name «APP 1.1 · in preparation».
- Reaches the phones only inside a signed v8: the signed v7 keeps its bundled v7 interface.
