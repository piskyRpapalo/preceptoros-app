/* preceptoros.mvp-connection/1 · local UI guard.
 * It pauses this browser's My node requests and Open World iframe/navigation.
 * It is NOT a remote hardware power switch, firewall or credential revocation.
 * Talk, Lab and local documents stay usable. State is reversible on this device.
 */
"use strict";
(function (win, doc) {
  const status = doc.getElementById("connection-status");
  const button = doc.getElementById("connection-kill");
  const node = doc.getElementById("panel-ajustes");
  const world = doc.getElementById("panel-modelos");
  const frame = doc.getElementById("openworld-frame");
  const fallback = doc.querySelector(".openworld-fallback");
  const nodeMessage = doc.getElementById("mynode-paused");
  const worldMessage = doc.getElementById("openworld-paused");
  if (!status || !button || !node || !world || !frame) return;
  const storeKey = "preceptoros.mvp.paused/1";
  const originalFetch = win.fetch.bind(win);
  const pending = new Set();
  let paused = false;
  let confirmed = false;
  let cause = "service_not_checked";
  let checkSeq = 0;
  let linkOriginal = fallback && fallback.getAttribute("href");
  const nodeInteractive = [...node.querySelectorAll("button,input,textarea,select,a,form,details")];
  const baselineInert = new Map(nodeInteractive.map(el => [el, el.inert]));

  try { paused = win.localStorage.getItem(storeKey) === "paused"; }
  catch { /* Inaccessible storage is not a reason to claim persistence. */ }

  function isNodeOrWorld(value) {
    let url;
    try {
      url = new win.URL(value instanceof win.Request ? value.url : value, win.location.href);
    } catch { return false; }
    if (url.origin === win.location.origin) {
      return /^\/api\/(?:nodo(?:\/|$)|empieza-aqui(?:\/|$)|bandeja(?:\/|$)|creaciones(?:\/|$)|energia(?:\/|$)|voz(?:\/|$)|perfil(?:\/|$))/.test(url.pathname);
    }
    return url.origin === "https://preceptoros.org" &&
      (url.pathname === "/openworld" || url.pathname.startsWith("/openworld/"));
  }
  win.fetch = function guardedFetch(input, init) {
    if (!isNodeOrWorld(input)) return originalFetch(input, init);
    if (paused) return Promise.reject(new win.DOMException("Node and World paused by owner", "AbortError"));
    const controller = new win.AbortController();
    pending.add(controller);
    const signal = (init && init.signal) || (input instanceof win.Request && input.signal);
    const forwardAbort = () => controller.abort();
    if (signal) {
      if (signal.aborted) forwardAbort();
      else signal.addEventListener("abort", forwardAbort, { once: true });
    }
    return originalFetch(input, { ...(init || {}), signal: controller.signal }).finally(() => {
      pending.delete(controller);
      if (signal) signal.removeEventListener("abort", forwardAbort);
    });
  };

  function paint() {
    status.dataset.state = paused ? "PAUSED" : confirmed ? "CONNECTED" : "NO_DATA";
    status.dataset.acho = paused ? "paused" : confirmed ? "ok" : "silent";
    status.dataset.cause = paused ? "owner_paused_node_and_world" :
      confirmed ? "local_service_answer_verified" : cause;
    status.textContent = paused ? "Paused" : confirmed ? "Connected" : "Not connected";
    status.title = paused
      ? "My node and Open World paused in this browser; local service may still be running"
      : confirmed
        ? "Local service answered /api/estado; model inference not independently verified"
        : "NO_DATA(" + cause + ")";
    button.setAttribute("aria-pressed", String(paused));
    button.setAttribute("aria-label", paused
      ? "Reconnect My node and Open World"
      : "Kill switch · Pause My node and Open World");
    button.title = "Browser-level pause. It does not turn off devices or revoke access.";
    button.textContent = paused ? "Reconnect" : "Kill switch";
  }

  function markPaused(target, message) {
    target.dataset.connectionPaused = String(paused);
    if (message) message.hidden = !paused;
  }

  function applyPause() {
    markPaused(node, nodeMessage);
    markPaused(world, worldMessage);
    // A paused My node cannot create identities, submit forms or open any external flow.
    // Restore only states we changed; existing disabled controls remain disabled.
    nodeInteractive.forEach(el => { el.inert = paused ? true : baselineInert.get(el); });
    if (paused) {
      for (const controller of pending) controller.abort();
      pending.clear();
      frame.removeAttribute("src");
      frame.hidden = true;
      if (fallback) {
        if (fallback.hasAttribute("href")) linkOriginal = fallback.getAttribute("href");
        fallback.removeAttribute("href");
        fallback.setAttribute("aria-disabled", "true");
        fallback.tabIndex = -1;
      }
    } else if (fallback) {
      if (linkOriginal) fallback.setAttribute("href", linkOriginal);
      fallback.removeAttribute("aria-disabled");
      fallback.removeAttribute("tabindex");
    }
    doc.dispatchEvent(new win.CustomEvent("mvp-connection-change", { detail: { paused } }));
    paint();
  }
  function setPaused(value) {
    paused = !!value;
    try {
      if (paused) win.localStorage.setItem(storeKey, "paused");
      else win.localStorage.removeItem(storeKey);
    } catch { /* Ephemeral state still works for this page. */ }
    applyPause();
  }
  function isPaused() { return paused; }

  async function probe() {
    const seq = ++checkSeq;
    const controller = new win.AbortController();
    const timer = win.setTimeout(() => controller.abort(), 5000);
    try {
      const response = await originalFetch("/api/estado", {
        method: "GET", cache: "no-store", credentials: "same-origin",
        signal: controller.signal,
      });
      if (seq !== checkSeq) return;
      if (!response.ok) {
        confirmed = false;
        cause = "local_service_http_" + response.status;
      } else {
        let body = null;
        try { body = await response.json(); } catch { /* Schema is required. */ }
        confirmed = !!body && body.estado === "ok" && typeof body.turnos === "object" &&
          body.turnos !== null;
        cause = confirmed ? "local_service_answer_verified" : "local_service_contract_unverified";
      }
    } catch (error) {
      if (seq !== checkSeq) return;
      confirmed = false;
      cause = error && error.name === "AbortError" ? "local_service_timeout" : "local_service_unreachable";
    } finally {
      win.clearTimeout(timer);
      if (seq === checkSeq) paint();
    }
  }

  button.addEventListener("click", () => setPaused(!paused));
  doc.addEventListener("visibilitychange", () => { if (!doc.hidden) probe(); });
  win.addEventListener("online", probe);
  win.addEventListener("offline", () => {
    confirmed = false; cause = "browser_offline"; paint();
  });
  applyPause();
  probe();
  const ticker = win.setInterval(() => { if (!doc.hidden) probe(); }, 30000);
  win.addEventListener("pagehide", () => win.clearInterval(ticker), { once: true });
  win.PreceptorConnectionGuard = Object.freeze({ isPaused, setPaused, probe, getCause: () => cause });
})(window, document);
