/* <plan_composer> Talk: write a long plan. It is never cut; its size and SHA-256 ref are shown as you write. Storing
 * it is the plan store's job (Codex, contract #310): until it exists the button says so and sends nothing. */
(function (root) {
  "use strict";
  // Talk composer for a long plan: never truncated; its ref is computed here; it is stored only by the plan store.
  function mountComposer() {
    const doc = root.document, ta = doc.getElementById("plan-texto"), info = doc.getElementById("plan-ref"), btn = doc.getElementById("plan-guardar");
    if (!ta || !info || !btn) return;
    let seq = 0;
    const update = async () => {
      const mine = ++seq, bytes = new TextEncoder().encode(ta.value);
      let ref = "NO_DATA";
      try { if (root.crypto && root.crypto.subtle && bytes.length) ref = [...new Uint8Array(await root.crypto.subtle.digest("SHA-256", bytes))].map((b) => b.toString(16).padStart(2, "0")).join(""); } catch { ref = "NO_DATA"; }
      if (mine !== seq) return;
      info.textContent = bytes.length ? bytes.length + " B · ref " + ref.slice(0, 16) + (ref.length > 16 ? "…" : "") + " · kept whole, never cut" : "Empty.";
      btn.dataset.ref = ref;
    };
    ta.addEventListener("input", update);
    btn.addEventListener("click", () => {
      const s = doc.getElementById("plan-guardar-estado");
      if (s) s.textContent = "NO_DATA: the plan store is not built yet (Codex, contract #310). Nothing was sent; your text stays here.";
    });
    update();
  }

  if (root.document && root.document.getElementById) mountComposer();
})(typeof window !== "undefined" ? window : globalThis);
