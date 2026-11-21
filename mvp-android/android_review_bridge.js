/* PreceptorOS Android-only public Companion review handoff.
 * Injected into the APK shell; browser/PWA assets are untouched.
 * This never submits an issue and never reads credentials or private memory.
 */
(function () {
  'use strict';
  var link = document.getElementById('companion-request-review');
  var draft = document.getElementById('companion-draft');
  var status = document.getElementById('companion-status');
  var bridge = window.PreceptorAndroidReview;
  if (!link || !draft || !status || !bridge ||
      typeof bridge.openReview !== 'function' ||
      link.dataset.androidReviewBound === '1') return;

  function announce(message, state, cause) {
    status.textContent = message;
    status.setAttribute('data-state', state);
    status.setAttribute('data-acho', state);
    status.setAttribute('data-cause', cause);
  }

  link.dataset.androidReviewBound = '1';
  link.addEventListener('click', async function (event) {
    event.preventDefault(); // Android has no implicit browser popup support.
    if (link.hidden || !link.href ||
        !draft.textContent.includes('Status: DRAFT_ONLY') ||
        status.getAttribute('data-state') !== 'DRAFT_ONLY') {
      announce('NO_DATA: prepare a valid draft before review. Nothing sent.',
        'NO_DATA', 'android_review_draft_missing');
      return;
    }
    try {
      if (await bridge.openReview(link.href) === true) {
        announce('DRAFT_ONLY · external GitHub form requested. Not submitted or received.',
          'DRAFT_ONLY', 'external_review_requested_not_submitted');
      } else {
        announce('NO_DATA: Android rejected review handoff. Nothing sent.',
          'NO_DATA', 'android_review_handoff_rejected');
      }
    } catch (error) {
      announce('NO_DATA: Android review handoff unavailable. Nothing sent.',
        'NO_DATA', 'android_review_handoff_error');
    }
  });
})();
