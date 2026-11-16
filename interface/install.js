(function (root) {
  'use strict';
  function mount(button, status) {
    var prompt = null, busy = false, installed = !!root.navigator.standalone || !!(root.matchMedia && root.matchMedia('(display-mode: standalone)').matches);
    function show(text, enabled) { status.textContent = text; button.disabled = !enabled; }
    if (installed) show('Running as an installed app.', false);
    else if (!root.isSecureContext) show('NO_DATA · installation requires HTTPS or trusted loopback.', false);
    else show('Install is not offered yet. Use the browser installation menu if available.', false);
    root.addEventListener('beforeinstallprompt', function (event) {
      if (installed || !root.isSecureContext || busy) return;
      event.preventDefault(); prompt = event;
      show('Ready: choose Install, then confirm in the browser.', true);
    });
    root.addEventListener('appinstalled', function () {
      installed = true; prompt = null; busy = false; show('Browser reported app installed.', false);
    });
    button.addEventListener('click', async function (event) {
      if (!event.isTrusted || !prompt || busy || installed) return;
      var current = prompt; prompt = null; busy = true;
      show('Confirm installation in the browser dialog.', false);
      try {
        await current.prompt();
        var choice = await current.userChoice;
        if (installed) return;
        show(choice.outcome === 'accepted' ? 'Browser accepted. Waiting for installation confirmation.' : 'Installation dismissed. Nothing was installed by this button.', false);
      } catch (_) { if (!installed) show('NO_DATA · browser installation could not be confirmed.', false); }
      finally { busy = false; }
    });
  }
  // Update state (update-state slice). Every line comes from a browser or rack signal, never from a guess:
  // installed = the cache the controlling service worker reports; served = /api/estado.version of the rack;
  // an update is offered only after the new worker installed, and install is all-or-nothing (cache.addAll).
  // The page never reloads by itself: the person chooses when, so nothing they are typing is lost.
  function mountUpdate(el) {
    var nav = root.navigator || {}, sw = nav.serviceWorker, busy = false, offered = false, hadController = !!(sw && sw.controller);
    function say(text) { el.state.textContent = text; }
    function offer() {
      offered = true; el.reload.disabled = false;
      say('Update ready: every file of the new app was downloaded and kept on this device. Choose Reload to use it.');
    }
    function track(worker) {
      if (!worker) return;
      say('Downloading the new app. Nothing changes until every file has arrived.');
      worker.addEventListener('statechange', function () {
        if (worker.state === 'redundant' && !offered) say('Update refused: a file of the new app did not download. The installed app stays as it was.');
      });
    }
    function installed() {
      if (!sw) { el.installed.textContent = 'NO_DATA · this browser keeps no offline copy (no service worker).'; return Promise.resolve(); }
      if (!sw.controller) { el.installed.textContent = 'NO_DATA · no offline copy controls this page yet (first visit or forced reload).'; return Promise.resolve(); }
      return new Promise(function (done) {
        var channel = new root.MessageChannel(), timer = root.setTimeout(function () {
          el.installed.textContent = 'An offline copy from before v197 · it does not report its number.'; done();
        }, 2000);
        channel.port1.onmessage = function (event) {
          root.clearTimeout(timer);
          var d = event.data || {}, m = /^preceptoros-armazon-v(\d{1,5})$/.exec(String(d.cache || ''));
          el.installed.textContent = m ? 'App v' + m[1] + ' · ' + (d.files | 0) + ' files kept on this device.' : 'NO_DATA · the offline copy answered without a valid number.';
          done();
        };
        sw.controller.postMessage({type: 'shell-version'}, [channel.port2]);
      });
    }
    function served() {
      if (typeof root.fetch !== 'function') { el.served.textContent = 'NO_DATA · this browser cannot ask the rack.'; return Promise.resolve(); }
      return root.fetch('/api/estado', {cache: 'no-store'}).then(function (r) {
        if (!r.ok) throw new Error('http ' + r.status);
        return r.json();
      }).then(function (d) {
        var v = d && d.version, h = v && /^[0-9a-f]{12}$/.test(v.huella) ? v.huella : null;
        el.served.textContent = h ? 'Shell ' + h.slice(0, 8) + ' · ' + String(v.fecha).slice(0, 10) + ' · ' + (v.ficheros | 0) + ' files.' : 'NO_DATA · the rack did not report its version.';
      }, function () {
        el.served.textContent = 'NO_DATA · the rack is not reachable now. The installed app keeps working from this device.';
      });
    }
    function check(event) {
      if (event && event.isTrusted === false) return Promise.resolve();
      if (busy) return Promise.resolve();
      if (!sw || typeof sw.getRegistration !== 'function') { say('NO_DATA · this browser cannot check for updates (no service worker).'); return Promise.resolve(); }
      busy = true; el.check.setAttribute('aria-busy', 'true'); say('Checking the rack for a newer app…');
      return sw.getRegistration().then(function (reg) {
        if (!reg) { say('NO_DATA · this app is not registered for offline use in this browser yet.'); return; }
        return Promise.resolve(reg.update()).then(function () {
          if (offered) return;
          if (reg.installing) track(reg.installing);
          else if (reg.waiting) offer();
          else say('Up to date: the rack has no newer app than this device.');
        }, function () { say('NO_DATA · could not reach the rack to check. The installed app stays as it is.'); });
      }).then(function () { return Promise.all([installed(), served()]); })
        .finally(function () { busy = false; el.check.removeAttribute('aria-busy'); });
    }
    el.reload.disabled = true;
    el.check.addEventListener('click', check);
    el.reload.addEventListener('click', function (event) {
      if (!event.isTrusted || !offered) return;
      root.location.reload();
    });
    if (sw) {
      sw.addEventListener('controllerchange', function () {
        // A first visit is claimed by its first worker: that is the app becoming offline, not an update.
        if (!hadController) { hadController = true; say('This app is now kept on this device for offline use.'); installed(); return; }
        offer();
        installed().then(function () {
          el.installed.textContent += ' This page still shows the previous version until you reload.';
        });
      });
      if (typeof sw.getRegistration === 'function') sw.getRegistration().then(function (reg) {
        if (reg) reg.addEventListener('updatefound', function () { track(reg.installing); });
      }, function () {});
    }
    return Promise.all([installed(), served()]).then(function () { return {check: check}; });
  }
  root.HexelionInstall = Object.freeze({mount:mount, mountUpdate:mountUpdate});
  if (root.document) {
    var d = root.document, button = d.getElementById('install-app'), status = d.getElementById('install-state');
    if (button && status) mount(button, status);
    var u = {installed: d.getElementById('update-installed'), served: d.getElementById('update-served'),
             state: d.getElementById('update-state'), check: d.getElementById('update-check'), reload: d.getElementById('update-reload')};
    if (u.installed && u.served && u.state && u.check && u.reload) mountUpdate(u);
  }
})(globalThis);
