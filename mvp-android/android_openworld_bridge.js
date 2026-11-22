/* Explicit, public visitor handoff. The remote game opens in the system browser,
 * outside the privileged APP WebView and without any native bridge. */
(function () {
  'use strict';
  var link = document.getElementById('openworld-visit');
  var status = document.getElementById('openworld-visit-status');
  var bridge = window.PreceptorAndroidOpenWorld;
  if (!link || !status || !bridge || typeof bridge.open !== 'function' ||
      link.dataset.androidOpenWorldBound === '1') return;

  function announce(text, state, cause) {
    status.textContent = text;
    status.dataset.state = state;
    status.dataset.acho = state;
    status.dataset.cause = cause;
  }

  link.dataset.androidOpenWorldBound = '1';
  link.addEventListener('click', async function (event) {
    event.preventDefault();
    if (!event.isTrusted || link.href !== 'https://preceptoros.org/openworld/') {
      announce('NO_DATA(openworld_user_action_required)', 'NO_DATA', 'user_action_or_route_invalid');
      return;
    }
    try {
      if (await bridge.open(link.href) === true) {
        announce('Visitor game opened in your browser. No account or node was created.',
          'VISITOR_HANDOFF', 'public_openworld_handoff');
      } else {
        announce('NO_DATA(openworld_handoff_rejected)', 'NO_DATA', 'native_policy_rejected');
      }
    } catch (_) {
      announce('NO_DATA(openworld_handoff_unavailable)', 'NO_DATA', 'native_handoff_unavailable');
    }
  });
})();
