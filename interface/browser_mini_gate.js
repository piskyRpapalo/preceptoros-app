/* app-dayd-mini · opt-in browser control for the shared offline router.
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
  }
  function paint(active) {
    button.setAttribute('aria-pressed', String(active));
    button.textContent = active ? 'Use my configured model' : 'Try offline mini';
    const mini = document.getElementById('offline-mini-status');
    if (mini) mini.hidden = !active;
    say(active
      ? 'DRAFT_ONLY · MINI-LOCAL is a deterministic router, NOT Hexelion. No bundled large model, tools or network. Unverified free prompts: NO_DATA. Switch off to try your own model.'
      : 'NO_DATA(mini_inactive) · Talk uses your configured model if one exists. No model turn has been verified.',
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
      say('NO_DATA(private_rack_mini_switch_blocked) · Private rack Talk keeps its authorized backend.',
        'NO_DATA', 'rack_profile_read_only');
      return;
    }
    if (!root.PreceptorOfflineMini ||
        typeof root.PreceptorOfflineMini.mount !== 'function') {
      root.PreceptorMiniBrowserEnabled = false;
      paint(false);
      say('NO_DATA(mini_module_unavailable). Your Chat was not changed.',
        'NO_DATA', 'mini_module_not_loaded');
      return;
    }
    root.PreceptorMiniBrowserEnabled = !root.PreceptorMiniBrowserEnabled;
    root.PreceptorOfflineMini.mount();
    paint(root.PreceptorMiniBrowserEnabled);
  });
})(window);
