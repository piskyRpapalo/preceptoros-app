function installLocalBridge(version) {
  'use strict';
  const port = window.PreceptorLocalNative;
  if (window !== window.top || window.location.href !== 'https://preceptoros.mvp.local/app.html' || !port) return;

  const pending = new Map();
  let nextId = 0;
  port.onmessage = ({ data }) => {
    let reply;
    try { reply = JSON.parse(data); } catch (_) { return; }
    const request = reply && pending.get(reply.id);
    if (!request) return;
    request.finish(reply.value);
  };

  function ask(operation, value, timeout, refusal) {
    if (typeof value !== 'string' || pending.size >= 2) return Promise.resolve(refusal);
    return new Promise(resolve => {
      const id = ++nextId;
      const timer = setTimeout(() => finish(refusal), timeout);
      function finish(result) {
        clearTimeout(timer);
        pending.delete(id);
        resolve(typeof result === typeof refusal ? result : refusal);
      }
      pending.set(id, { finish });
      try { port.postMessage(JSON.stringify({ id, operation, value })); }
      catch (_) { finish(refusal); }
    });
  }

  window.PreceptorAndroidMiniModel = Object.freeze({
    version: () => version,
    generate: prompt => ask('mini', prompt, 90000, 'NO_DATA(mini_native_unavailable)')
  });
  window.PreceptorAndroidReview = Object.freeze({
    openReview: url => ask('review', url, 5000, false)
  });
}
