/* Local-first node identity and explicit, credential-hiding building action. */
(function (root) {
  "use strict";

  var identitySchema = "preceptoros.pwa-node-identity/1";
  var actionSchema = "preceptoros.pwa-edificio-accion/1";
  var assignedNode = "primer-ancla";

  function text(key, values) {
    return typeof root.PreceptorNodeBuildingText === "function"
      ? root.PreceptorNodeBuildingText(key, values || {}) : key;
  }

  function mount(document, fetchImpl) {
    var fetcher = fetchImpl || root.fetch.bind(root);
    var identityForm = document.getElementById("node-identity-form");
    var buildingForm = document.getElementById("node-building-form");
    if (!identityForm || !buildingForm) return;
    var identityRead = document.getElementById("node-identity-read");
    var nodeInput = document.getElementById("node-identity-id");
    var identityConsent = document.getElementById("node-identity-consent");
    var identityButton = document.getElementById("node-identity-save");
    var identityStatus = document.getElementById("node-identity-status");
    var buildingConsent = document.getElementById("node-building-consent");
    var buildingButton = document.getElementById("node-building-submit");
    var buildingStatus = document.getElementById("node-building-status");
    var configured = false, nodeReady = false;
    var gate = { ok: false, state: "NO_DATA", cause: "node_lifecycle_unread", next: "" };
    var win = document.defaultView || root;
    function enableBuilding() {
      buildingButton.disabled = !configured || !nodeReady || !gate.ok || !buildingConsent.checked;
    }
    function paintGate() {
      buildingStatus.dataset.state = buildingStatus.dataset.acho = gate.state;
      buildingStatus.dataset.cause = gate.cause;
      if (!gate.ok && configured && nodeReady) {
        var line = "NO_DATA(" + gate.cause + "). Next: " + gate.next;
        if (buildingStatus.textContent !== line) buildingStatus.textContent = line;
      }
      enableBuilding();
    }
    function refreshGate() {
      return readEvidence(win).then(function (ev) { gate = buildingGate(ev.lifecycle); paintGate(); },
        function () { gate = buildingGate(null); paintGate(); });
    }
    var buildingToggle = document.getElementById("mynode-building-toggle");
    if (buildingToggle) buildingToggle.addEventListener("click", refreshGate);

    function lockIdentity(nodeId) {
      configured = true;
      nodeInput.value = nodeId;
      nodeInput.disabled = true;
      identityConsent.checked = false;
      identityConsent.disabled = true;
      identityButton.disabled = true;
      identityRead.disabled = true;
      nodeReady = nodeId === assignedNode;
      buildingConsent.disabled = !nodeReady;
      buildingButton.disabled = true;
      refreshGate();
      identityStatus.textContent = text("node_building_saved", { id: nodeId });
      if (nodeId !== assignedNode) {
        buildingStatus.textContent = text("node_building_no_assignment");
      }
    }

    function post(url, body) {
      return fetcher(url, { method: "POST", cache: "no-store", credentials: "same-origin",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) })
        .then(function (response) {
          return response.json().catch(function () { return {}; }).then(function (data) {
            return { ok: response.ok, data: data };
          });
        });
    }

    identityRead.addEventListener("click", function () {
      identityRead.disabled = true;
      fetcher("/api/nodo/identity", { method: "GET", cache: "no-store", credentials: "same-origin" })
        .then(function (response) {
          return response.json().then(function (data) {
            if (response.ok && data && data.estado === "configurada" && typeof data.node_id === "string") {
              lockIdentity(data.node_id);
            } else {
              identityStatus.textContent = text("node_building_cause", { cause: "identidad_no_provisionada" });
              identityRead.disabled = false;
            }
          });
        }).catch(function () {
          identityStatus.textContent = text("node_building_unavailable");
          identityRead.disabled = false;
        });
    });

    identityForm.addEventListener("submit", function (event) {
      event.preventDefault();
      if (configured || !identityConsent.checked || !nodeInput.reportValidity()) return;
      identityButton.disabled = true;
      identityRead.disabled = true;
      identityStatus.textContent = text("node_building_saving");
      post("/api/nodo/identity", { esquema: identitySchema, node_id: nodeInput.value.trim() })
        .then(function (result) {
          if (result.ok && result.data.estado === "provisionada") {
            lockIdentity(result.data.node_id);
          } else {
            identityStatus.textContent = text("node_building_cause", { cause: result.data.causa || "provision_no_confirmada" });
            identityButton.disabled = false;
            identityRead.disabled = false;
          }
        }).catch(function () {
          identityStatus.textContent = text("node_building_cause", { cause: "provision_local_no_confirmada" });
          identityButton.disabled = false;
          identityRead.disabled = false;
        });
    });

    buildingConsent.addEventListener("change", function () {
      enableBuilding();
    });

    buildingForm.addEventListener("submit", function (event) {
      event.preventDefault();
      if (!configured || !nodeReady || !gate.ok || !buildingConsent.checked) return;
      buildingButton.disabled = true;
      buildingStatus.textContent = text("node_building_sending");
      post("/api/nodo/edificio", { esquema: actionSchema, confirmar: true })
        .then(function (result) {
          var data = result.data || {};
          if (result.ok && data.estado === "recibido") {
            buildingStatus.textContent = text("node_building_received", {
              building: data.edificio, node: data.nodo, receipt: data.recibo_sha256
            });
          } else {
            buildingStatus.textContent = text("node_building_failed", { cause: data.causa || "declaracion_no_confirmada" });
          }
          refreshGate();
        }).catch(function () {
          buildingStatus.textContent = text("node_building_not_confirmed");
          refreshGate();
        });
    });
  }

  function boundedCause(value, fallback) {
    return /^[a-z0-9_]{1,96}$/.test(String(value || "")) ? String(value) : fallback;
  }
  // My node · Beelink APP (odd/tasks/online3-pwa-intake.md, Codex): the same form and Aduana contract through the APP's own
  // loopback route. Only on a plain-http loopback page; the APK origin and public pages get null and stay fail-closed.
  var pwaIntakeSchema = 'preceptoros.pwa-node-deployment-request/1';
  function isLoopbackApp(win) {
    var loc = win && win.location;
    return !!loc && loc.protocol === 'http:' && /^(127\.0\.0\.1|localhost|\[::1\])$/.test(loc.hostname) &&
      typeof win.fetch === 'function';
  }
  function loopbackIntake(win) {
    if (!isLoopbackApp(win) || !win.crypto || typeof win.crypto.getRandomValues !== 'function') return null;
    var nonce = null; // one per consented attempt; a retry of that same attempt reuses it
    return { requestPreliminary: async function (request) {
      if (!request || request.consent !== true) throw new Error('explicit_consent_required');
      if (!nonce) {
        var bytes = new Uint8Array(16); win.crypto.getRandomValues(bytes);
        nonce = Array.from(bytes, function (b) { return b.toString(16).padStart(2, '0'); }).join('');
      }
      var response;
      try {
        response = await win.fetch('/api/nodo/identity', { method: 'POST', cache: 'no-store',
          credentials: 'same-origin', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ esquema: pwaIntakeSchema, node: request.node, nonce: nonce, consent: true }) });
      } catch (_error) { throw new Error('app_server_unreachable'); }
      var body; try { body = await response.json(); } catch (_error) { body = {}; }
      if (!response.ok) throw new Error(boundedCause(body.cause || body.causa, 'intake_http_' + response.status));
      return body; // requestDeploymentReview verifies the receipt; purpose stays local
    } };
  }
  // Reads only. A stage is shown done only with the backend's own reading; missing APIs are NO_DATA with cause.
  async function readEvidence(win) {
    if (!isLoopbackApp(win)) {
      return { identity: { state: 'NO_DATA', cause: 'app_server_not_on_this_device' },
        lifecycle: { cause: 'app_server_not_on_this_device' } };
    }
    async function get(path) {
      try {
        var r = await win.fetch(path, { cache: 'no-store', credentials: 'same-origin' });
        var b; try { b = await r.json(); } catch (_e) { b = null; }
        return { status: r.status, body: b };
      } catch (_e) { return { status: 0, body: null }; }
    }
    var id = await get('/api/nodo/identity'), life = await get('/api/nodo/estado');
    var identity = id.status === 200 && id.body && id.body.estado === 'configurada' &&
      /^[a-z0-9][a-z0-9._-]{0,63}$/.test(String(id.body.node_id || ''))
      ? { state: 'MEASURED', node: id.body.node_id, cause: 'local_identity_configured' }
      : { state: 'NO_DATA', cause: id.status === 0 ? 'app_server_unreachable'
        : boundedCause(id.body && (id.body.causa || id.body.cause), 'identity_http_' + id.status) };
    var lifecycle = life.status === 200 && life.body && life.body.schema === 'preceptoros.node-lifecycle/1' &&
      life.body.stages && typeof life.body.stages === 'object'
      ? life.body : { cause: life.status === 404 ? 'node_lifecycle_api_missing'
        : life.status === 0 ? 'app_server_unreachable' : 'node_lifecycle_unverified' };
    return { identity: identity, lifecycle: lifecycle };
  }
  // Create building (Round 4): publish only when the backend lifecycle (preceptoros.node-lifecycle/1) confirms an
  // owner-signed, admitted, unrevoked node AND reports the building stage ready (function tested, policy accepted).
  // The first missing requirement is named; stages.building.cause explains the function/policy part. Pure.
  function buildingGate(life) {
    var st = life && life.stages, m = function (k) { return st && st[k] && st[k].state === "MEASURED"; };
    var no = function (cause, next) { return { ok: false, state: "NO_DATA", cause: boundedCause(cause, "node_lifecycle_unverified"), next: next }; };
    if (!st || typeof st !== "object") return no(life && life.cause, "Open My node on the Beelink APP so it can read your node's lifecycle.");
    if (st.revoke && st.revoke.state === "REVOKED") return no("node_revoked", "Your node was revoked; request admission again first.");
    if (!m("signature")) return no("owner_identity_unverified", "Finish stage 4 in «Getting started»: the owner's SSH signature.");
    if (!m("approval")) return no("node_not_admitted", "Wait for Aduana to admit the node (stage 5).");
    var b = st.building || {};
    if (b.state === "PENDING" || b.state === "MEASURED") return { ok: true, state: b.state, cause: boundedCause(b.cause, "building_ready"), next: "Tick the confirmation and declare the building." };
    return no(b.cause || "building_requirements_unverified", "Install and test the building's function and accept its policy on this node; this APP cannot do that for you.");
  }

  var loopback = Object.freeze({ intake: loopbackIntake, read: readEvidence, buildingGate: buildingGate });

  if (typeof module === "object" && module.exports) {
    module.exports = Object.freeze({ mount: mount, identitySchema: identitySchema, actionSchema: actionSchema,
      loopback: loopback });
  } else if (root.document) {
    root.PreceptorNodeLoopback = loopback;
    mount(root.document, root.fetch.bind(root));
  }
})(typeof globalThis !== "undefined" ? globalThis : this);
