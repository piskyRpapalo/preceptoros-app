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

/* Online3 · private Talk route selector (consumes odd/tasks/online3-private-talk.md, Codex).
 * Shown only when the owner APK exposes PreceptorPrivateTalkNative; public/v7 builds keep today's UI.
 * Local Mini stays the default and keeps answering offline. Private is an explicit user choice,
 * reversible, never persisted. The private address lives in Android settings via a system dialog;
 * this page never sees, stores or sends it. A saved address is NO_DATA until a measured turn.
 * One state, four readers: visible text, aria-live status, data-state/acho/cause/stage, acho:event.
 */
(function (root) {
  'use strict';
  const doc = root.document;
  const native = root.PreceptorPrivateTalkNative;
  const localGroup = doc && doc.getElementById('mini-local-toggle') &&
    doc.getElementById('mini-local-toggle').closest('.mini-mode-switch');
  const form = doc && doc.getElementById('form-chat');
  const input = doc && doc.getElementById('dicho');
  const thread = doc && doc.getElementById('hilo');
  if (!native || typeof native.postMessage !== 'function' || !localGroup || !form || !input || !thread) return;

  const replyWaitMs = 150000; // contract: wait at least 145 s before declaring no confirmed reply
  const pending = new Map();
  let privateOn = false;
  let busy = false;

  const group = doc.createElement('div');
  group.className = 'mini-mode-switch';
  group.id = 'private-talk-switch';
  group.setAttribute('role', 'group');
  group.setAttribute('aria-label', 'Private orchestrator route');
  const toggle = doc.createElement('button');
  toggle.type = 'button'; toggle.id = 'private-talk-toggle';
  const configure = doc.createElement('button');
  configure.type = 'button'; configure.id = 'private-talk-configure';
  configure.textContent = 'Private address…';
  configure.title = 'Opens an Android system dialog. The address stays on this phone, outside the page.';
  [toggle, configure].forEach(function (b) { b.style.minHeight = '44px'; b.style.minWidth = '44px'; });
  const status = doc.createElement('p');
  status.className = 'pie'; status.id = 'private-talk-status';
  status.setAttribute('role', 'status'); status.setAttribute('aria-live', 'polite');
  group.append(toggle, configure, status);
  localGroup.insertAdjacentElement('afterend', group);
  const label = doc.querySelector('#modelos-toggle span');

  function say(message, state, cause, stage) {
    status.textContent = message;
    status.dataset.state = state;
    status.dataset.acho = state === 'MEASURED' ? 'ok' : state;
    status.dataset.cause = cause;
    status.dataset.stage = stage || '';
    const detail = doc.getElementById('talk-diagnostics-mini');
    if (detail) detail.textContent = 'private_talk ' + state + '(' + (stage ? stage + ':' : '') + cause + ')';
    if (typeof root.CustomEvent === 'function') {
      doc.dispatchEvent(new root.CustomEvent('acho:event', { detail: {
        id: 'talk/private-route', state: state, cause: cause, stage: stage || null, sentence: message } }));
    }
  }
  function paint() {
    toggle.setAttribute('aria-pressed', String(privateOn));
    toggle.textContent = privateOn ? 'Use Local Mini on this phone' : 'Use private orchestrator (Hexelion)';
    toggle.disabled = busy;
    form.dataset.talkRoute = privateOn ? 'private_orchestrator' : 'local_mini';
    if (label) label.textContent = privateOn ? 'Model · Private Hexelion' : 'Model · Local Mini';
  }
  function hex32() {
    const bytes = new Uint8Array(16);
    root.crypto.getRandomValues(bytes);
    return Array.from(bytes, function (v) { return v.toString(16).padStart(2, '0'); }).join('');
  }
  function onReply(event) {
    let msg = null;
    try { msg = JSON.parse(event && event.data); } catch (_) { return; }
    const done = msg && typeof msg.id === 'string' && pending.get(msg.id);
    if (!done) return;
    pending.delete(msg.id);
    done(msg.result && typeof msg.result === 'object' ? msg.result
      : { estado: 'NO_DATA', stage: 'request', causa: 'private_talk_reply_malformed' });
  }
  if (typeof native.addEventListener === 'function') native.addEventListener('message', onReply);
  else native.onmessage = onReply;
  function ask(body, timeoutMs) {
    const id = hex32();
    return new Promise(function (resolve) {
      const timer = root.setTimeout(function () {
        if (!pending.delete(id)) return;
        resolve({ estado: 'NO_DATA', stage: 'connection', causa: 'private_talk_reply_unconfirmed' });
      }, timeoutMs);
      pending.set(id, function (result) { root.clearTimeout(timer); resolve(result); });
      try { native.postMessage(JSON.stringify(Object.assign({ id: id }, body))); }
      catch (_) {
        root.clearTimeout(timer); pending.delete(id);
        resolve({ estado: 'NO_DATA', stage: 'connection', causa: 'private_talk_bridge_error' });
      }
    });
  }
  function clean(v, n) { return String(v == null ? '' : v).replace(/[\u0000-\u001f]/g, ' ').trim().slice(0, n); }
  function noData(result) {
    const stage = /^(connection|authentication|model|context|request)$/.test(result.stage) ? result.stage : 'request';
    const cause = /^[a-z0-9_]{1,96}$/.test(result.causa || '') ? result.causa : 'private_talk_unverified';
    return { stage: stage, cause: cause };
  }
  async function refresh() {
    const r = await ask({ op: 'status' }, 15000);
    const n = noData(r);
    if (!privateOn) {
      say('Private orchestrator is off. Local Mini answers on this phone, with or without network.',
        'NO_DATA', 'private_talk_off', null);
      return;
    }
    say('Private orchestrator selected · NO_DATA(' + n.stage + ': ' + n.cause + '). ' +
      (n.cause === 'private_talk_serve_not_configured'
        ? 'Set the private address first; it stays in Android settings.'
        : 'Only a measured Hexelion reply proves the link.'), 'NO_DATA', n.cause, n.stage);
  }
  function row(who, text, state, cause, source) {
    const li = doc.createElement('li');
    li.className = who === 'You' ? 'mio' : 'hilo-msg';
    li.dataset.state = state; li.dataset.acho = state === 'MEASURED' ? 'ok' : state;
    li.dataset.cause = cause; li.dataset.source = source;
    const name = doc.createElement('strong'); name.className = 'quien';
    name.textContent = who === 'You' ? 'You · ' : who + ' · ';
    const body = doc.createElement('span'); body.textContent = text;
    li.append(name, body); thread.append(li);
    while (thread.childElementCount > 36) thread.firstElementChild.remove();
    thread.scrollTop = thread.scrollHeight;
    return li;
  }

  toggle.addEventListener('click', function () {
    if (busy) return;
    privateOn = !privateOn;
    paint();
    refresh();
  });
  configure.addEventListener('click', async function () {
    configure.disabled = true;
    say('Waiting for your decision in the Android dialog. Nothing is sent.', 'NO_DATA', 'awaiting_owner_decision', 'connection');
    const r = await ask({ op: 'configure' }, 300000);
    configure.disabled = false;
    const n = noData(r);
    say('Private address · NO_DATA(' + n.stage + ': ' + n.cause + '). A saved address is not a verified link.',
      'NO_DATA', n.cause, n.stage);
  });

  // Capture phase on the document: it runs before any listener on the form itself, including the offline Mini
  // capture listener that offline_mini.js registers earlier. Only when private is chosen.
  doc.addEventListener('submit', async function (event) {
    if (event.target !== form || !privateOn) return; // Local Mini (or the configured server) handles it, unchanged.
    event.preventDefault();
    event.stopImmediatePropagation();
    const text = String(input.value || '').trim();
    if (!text || busy) return;
    busy = true; paint();
    input.value = '';
    row('You', text, 'DRAFT_ONLY', 'private_talk_request', 'private_orchestrator');
    say('Sending to the private orchestrator… a reply can take up to 2.5 minutes.', 'NO_DATA', 'private_talk_in_flight', 'connection');
    const r = await ask({ op: 'send', texto: text }, replyWaitMs);
    busy = false; paint();
    const answer = r && r.respuesta, machine = answer && answer.maquina;
    if (r && r.estado === 'MEASURED' && answer && answer.estado === 'MEASURED' && machine &&
        clean(answer.texto, 4000) && Number(machine.ms) > 0 && Array.isArray(answer.fuentes) && answer.fuentes.length) {
      const meta = clean(machine.modelo, 48) + ' · ' + Math.round(Number(machine.ms)) + ' ms · ' + answer.fuentes.length + ' sources';
      row('Hexelion · private orchestrator', clean(answer.texto, 4000), 'MEASURED', 'private_talk_turn_measured', 'private_orchestrator');
      say('Private orchestrator · MEASURED · ' + meta + '. Not your on-device model.', 'MEASURED', 'private_talk_turn_measured', null);
    } else {
      const n = noData(r || {});
      row('Hexelion · private orchestrator', 'NO_DATA(' + n.stage + ': ' + n.cause + ')', 'NO_DATA', n.cause, 'private_orchestrator');
      input.value = text; // keep the words; never answered by inference
      say('Private orchestrator · NO_DATA(' + n.stage + ': ' + n.cause + '). Your words are back in the box; ' +
        'switch to Local Mini to answer on this phone.', 'NO_DATA', n.cause, n.stage);
    }
    input.focus();
  }, true);

  root.addEventListener('offline', function () {
    if (privateOn) say('Network lost · NO_DATA(connection: device_offline). Local Mini still answers on this phone.',
      'NO_DATA', 'device_offline', 'connection');
  });
  root.addEventListener('online', function () { if (privateOn) refresh(); });
  paint();
  say('Private orchestrator is off. Local Mini answers on this phone, with or without network.', 'NO_DATA', 'private_talk_off', null);
  root.PreceptorPrivateTalkRoute = Object.freeze({ isPrivate: function () { return privateOn; } });
})(window);
