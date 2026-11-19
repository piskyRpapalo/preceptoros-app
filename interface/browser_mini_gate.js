/* app-dayd-mini · opt-in browser control for the shared offline router.
 * It performs deterministic routing only, not a model inference.
 * No duplicate intent parser, storage, credential, model or execution API.
 */
(function (root) {
  'use strict';
  const button = document.getElementById('mini-local-toggle');
  const status = document.getElementById('mini-local-mode-status');
  if (!button || !status) return;

  // Android's bundled mini is already active and has an optional JNI model;
  // never offer a switch to an unavailable /api backend there.
  if (root.PreceptorAndroidMiniModel) {
    button.hidden = true;
    status.hidden = true;
    return;
  }

  root.PreceptorMiniBrowserEnabled = false; // fresh tab: explicit opt-in
  function say(message, state, cause) {
    status.textContent = message;
    status.dataset.state = state;
    status.dataset.acho = state;
    status.dataset.cause = cause;
    const detail = document.getElementById("talk-diagnostics-mini");
    if (detail) detail.textContent = state + "(" + cause + ")";
  }
  function paint(active) {
    button.setAttribute('aria-pressed', String(active));
    button.textContent = active ? 'Use my configured model' : 'Use Mini Orchestrator offline';
    const mini = document.getElementById('offline-mini-status');
    if (mini) mini.hidden = !active;
    say(active
      ? 'Mini Orchestrator offline mode is on: deterministic routing only. No external model, network or tools. Switch off to use your configured model.'
      : 'Mini Orchestrator offline mode is off. Talk uses your configured model if available; no model reply is verified yet.',
      active ? 'DRAFT_ONLY' : 'NO_DATA',
      active ? 'browser_mini_opted_in_no_model' : 'browser_mini_off');
  }

  paint(false);
  button.addEventListener('click', function () {
    // Prevent the UI from silencing a verified rack conversation. A local
    // profile preference cannot create or revoke any authority in either mode.
    if (root.PreceptorProfile === 'private_rack') {
      root.PreceptorMiniBrowserEnabled = false;
      paint(false);
      say('The current connection keeps its configured backend; switching Mini Orchestrator offline mode is not authorized here.',
        'NO_DATA', 'rack_profile_read_only');
      return;
    }
    if (!root.PreceptorOfflineMini ||
        typeof root.PreceptorOfflineMini.mount !== 'function') {
      root.PreceptorMiniBrowserEnabled = false;
      paint(false);
      say('Mini Orchestrator offline mode is unavailable; your Talk connection was not changed.',
        'NO_DATA', 'mini_module_not_loaded');
      return;
    }
    root.PreceptorMiniBrowserEnabled = !root.PreceptorMiniBrowserEnabled;
    root.PreceptorOfflineMini.mount();
    paint(root.PreceptorMiniBrowserEnabled);
  });
})(window);
