/* Hexelion conversational avatar · 02 · reuse the existing PreceptorOS Talk panel and its illustration.
 * No new app, router, model, server, credential, or permission.
 * On-device speech recognition only. Never calls SpeechRecognition.install().
 */
(function (root) {
  'use strict';
  const doc = root.document;
  const controls = doc && doc.getElementById('talk-actions');
  const input = doc && doc.getElementById('dicho');
  const form = doc && doc.getElementById('form-chat');
  const thread = doc && doc.getElementById('hilo');
  if (!controls || !input || !form || !thread || doc.getElementById('hex-avatar-voice')) return;
  const descriptions = Object.freeze({
    idle: 'Disponible para interacción local',
    listening: 'Escuchando con permiso explícito',
    thinking: 'Petición enviada por el formulario Talk existente; respuesta no confirmada',
    awaiting_authorization: 'Esperando autorización o perfil propietario; no se ha concedido ningún permiso',
    speaking: 'Síntesis local solicitada; audición física sin testigo',
    interrupted: 'Interrumpida la captura y la lectura locales; el servidor puede continuar',
    error: 'La operación no se completó',
    no_data: 'Capacidad no acreditada en este dispositivo',
    muted: 'Micrófono y reproducción voluntaria bloqueados'
  });
  const reasons = new Set([
    'not_started', 'local_stt_unavailable', 'local_stt_pack_missing',
    'local_stt_host_failed', 'local_stt_thermal_hold', 'local_stt_receipt_invalid',
    'local_stt_hardware_off', 'local_stt_busy', 'local_stt_sensor_unavailable',
    'local_stt_permission_refused', 'local_stt_error', 'local_stt_no_text',
    'mic_local_started', 'transcript_submitted_via_existing_talk',
    'talk_processing_observed', 'talk_reply_not_attested',
    'local_speech_requested_audition_unverified', 'local_speech_unavailable',
    'local_speech_finished_audition_unverified', 'operator_interrupted',
    'operator_muted', 'operator_unmuted', 'no_visible_response',
    'no_voice_reader', 'local_voice_error', 'owner_profile_required',
    'owner_approval_pending', 'unexpected_error'
  ]);
  const panel = doc.createElement('div');
  panel.id = 'hex-avatar-voice';
  panel.setAttribute('role', 'group');
  panel.setAttribute('aria-label', 'Hexelion · voz y avatar locales');
  panel.style.cssText = 'display:flex;align-items:center;gap:.5rem;flex-wrap:wrap;max-width:100%';
  // The illustration is an existing, served APP asset (no duplicate avatar artwork).
  const image = doc.createElement('img');
  image.id = 'hex-avatar-face';
  image.setAttribute('src', '/assets/avatar-github.png');
  image.setAttribute('width', '64');
  image.setAttribute('height', '64');
  image.setAttribute('loading', 'lazy');
  image.setAttribute('decoding', 'async');
  image.setAttribute('draggable', 'false');
  image.setAttribute('aria-label', 'Hexelion · disponible');
  // CSS-only expressions. Respect reduced-motion and do not request a renderer or GPU.
  const style = doc.createElement('style');
  style.textContent = `
    #hex-avatar-face {height:64px;width:64px;object-fit:contain;border-radius:8px;transition:filter .2s,transform .2s;}
    #hex-avatar-voice[data-state="listening"] #hex-avatar-face {animation:hex-avatar-listening .7s ease-in-out infinite alternate;}
    #hex-avatar-voice[data-state="thinking"] #hex-avatar-face {animation:hex-avatar-thinking 1.1s ease-in-out infinite alternate;}
    #hex-avatar-voice[data-state="speaking"] #hex-avatar-face {animation:hex-avatar-speaking .28s ease-in-out infinite alternate;}
    #hex-avatar-voice[data-state="awaiting_authorization"] #hex-avatar-face {filter:grayscale(.7) brightness(.85);}
    #hex-avatar-voice[data-state="interrupted"] #hex-avatar-face {filter:grayscale(.8);}
    #hex-avatar-voice[data-state="muted"] #hex-avatar-face {filter:grayscale(1);}
    #hex-avatar-voice[data-state="error"] #hex-avatar-face {filter:grayscale(1) contrast(1.4);}
    @keyframes hex-avatar-listening {to{transform:scale(1.07);}}
    @keyframes hex-avatar-thinking {to{transform:rotate(3deg);}}
    @keyframes hex-avatar-speaking {to{transform:translateY(-3px);}}
    @media(prefers-reduced-motion:reduce) {#hex-avatar-face{animation:none!important;transition:none!important;}}
  `;
  const status = doc.createElement('p');
  status.id = 'hex-avatar-state'; status.tabIndex = 0;
  status.setAttribute('aria-live', 'off'); // existing #estado owns the live announcement
  status.style.cssText = 'flex-basis:100%;margin:0;font-size:.9em';
  const button = (id, label) => {
    const el = doc.createElement('button'); el.type = 'button'; el.id = id;
    el.textContent = label; el.setAttribute('aria-label', label);
    // Meet the existing APP touch target contract without changing shared CSS.
    el.style.minHeight = '44px'; el.style.minWidth = '44px';
    return el;
  };
  const listen = button('hex-avatar-listen', 'Hablar y enviar · solo STT local');
  const read = button('hex-avatar-read', 'Leer último mensaje visible · voz local');
  const stop = button('hex-avatar-stop', 'Interrumpir voz');
  const mute = button('hex-avatar-mute', 'Silenciar voz');
  mute.setAttribute('aria-pressed', 'false');
  panel.append(style, image, listen, read, stop, mute, status);
  controls.appendChild(panel);
  let epoch = 0, mic = null, muted = false, voice = null, speechRun = 0;
  let lastLocalSTT = Object.freeze({state:'NO_DATA',cause:'not_measured'});
  const state = {
    schema: 'hexelion.avatar-state/1', intent: 'conversation', state: 'idle',
    cause: 'not_started', source_ref: 'local_ui_only', epoch: 0,
    authority: 'none', render_effects: 'none'
  };
  function sentence() {
    return 'Hexelion: ' + descriptions[state.state] + '. Causa: ' + state.cause +
      '. Fuente: ' + state.source_ref + '. STT: ' +
      (lastLocalSTT.state === 'MEASURED' ? lastLocalSTT.inference_ms + ' milisegundos locales' : 'NO_DATA') +
      '. La interfaz no concede permisos.';
  }
  function project(next, cause, source) {
    if (!Object.prototype.hasOwnProperty.call(descriptions, next) || !reasons.has(cause)) {
      next = 'error'; cause = 'unexpected_error'; source = 'local_ui_only';
    }
    state.state = next; state.cause = cause;
    state.source_ref = source || 'local_ui_only'; state.epoch = ++epoch;
    panel.dataset.state = state.state; panel.dataset.cause = state.cause;
    panel.dataset.epoch = String(state.epoch);
    image.dataset.state = state.state; image.dataset.cause = state.cause;
    const line = sentence();
    status.textContent = line; image.setAttribute('aria-label', line);
    return Object.freeze(Object.assign({}, state));
  }
  function interrupt(cause) {
    speechRun++;
    if (mic) { try { mic.abort(); } catch (_) {} mic = null; }
    if (voice) { try { voice.stop(); } catch (_) {} }
    project('interrupted', cause || 'operator_interrupted', 'operator_local_only');
  }
  function setMute() {
    muted = !muted;
    if (muted) { interrupt('operator_interrupted'); project('muted', 'operator_muted', 'operator_local_only'); }
    else project('idle', 'operator_unmuted', 'operator_local_only');
    mute.setAttribute('aria-pressed', String(muted));
    mute.textContent = muted ? 'Activar voz' : 'Silenciar voz';
  }

  // Browser owns explicit capture. STT remains inside the same loopback APP,
  // with no SpeechRecognition remote fallback and no second Talk client.
  function hostSTTAllowed() {
    const loc = root.location;
    return !!(loc && loc.protocol === 'http:' &&
      ['127.0.0.1', 'localhost', '::1'].includes(loc.hostname) &&
      root.navigator && root.navigator.mediaDevices &&
      typeof root.navigator.mediaDevices.getUserMedia === 'function' &&
      (root.AudioContext || root.webkitAudioContext) &&
      typeof root.fetch === 'function' && root.crypto && root.crypto.subtle &&
      root.AbortController && root.TextEncoder);
  }
  async function hexSha(bytes) {
    const hash = await root.crypto.subtle.digest('SHA-256', bytes);
    return [...new Uint8Array(hash)].map(n => n.toString(16).padStart(2, '0')).join('');
  }
  function makeWav(segments, frames, rate) {
    if (!Number.isFinite(rate) || rate < 8000 || rate > 192000) throw Error('invalid_sample_rate');
    const merged = new Float32Array(frames);
    let offset = 0;
    for (const seg of segments) { merged.set(seg, offset); offset += seg.length; }
    const count = Math.floor(frames * 16000 / rate);
    if (count < 8000 || count > 80000) throw Error('capture_duration_out_of_range');
    const bytes = new ArrayBuffer(44 + count * 2), v = new DataView(bytes);
    const fourcc = (at, text) => { for (let i = 0; i < text.length; i++) v.setUint8(at+i, text.charCodeAt(i)); };
    fourcc(0,'RIFF'); v.setUint32(4, 36+count*2, true); fourcc(8,'WAVE');
    fourcc(12,'fmt '); v.setUint32(16,16,true); v.setUint16(20,1,true);
    v.setUint16(22,1,true); v.setUint32(24,16000,true); v.setUint32(28,32000,true);
    v.setUint16(32,2,true); v.setUint16(34,16,true);
    fourcc(36,'data'); v.setUint32(40,count*2,true);
    for (let i=0;i<count;i++) {
      const pos = i*rate/16000, low = Math.min(frames-1, Math.floor(pos));
      const high = Math.min(frames-1, low+1);
      const sample = Math.max(-1, Math.min(1, merged[low] + (merged[high]-merged[low]) * (pos-low)));
      v.setInt16(44+i*2, sample < 0 ? Math.round(sample*32768) : Math.round(sample*32767), true);
    }
    return bytes;
  }
  async function startHostMic() {
    if (!hostSTTAllowed()) return project('no_data', 'local_stt_unavailable', 'browser_local_mic_probe');
    const token = ++speechRun;
    const Controller = root.AbortController;
    const abort = new Controller();
    let stream = null, context = null, source = null, processor = null, timer = null;
    let recording = false, resolveCapture = null;
    const closeCapture = () => {
      recording = false;
      if (timer) { root.clearTimeout(timer); timer = null; }
      if (resolveCapture) { const resume = resolveCapture; resolveCapture = null; resume(); }
      if (processor) { processor.onaudioprocess = null; try { processor.disconnect(); } catch (_) {} }
      if (source) { try { source.disconnect(); } catch (_) {} }
      if (stream) { for (const track of stream.getTracks()) try { track.stop(); } catch (_) {} }
      if (context) { try { Promise.resolve(context.close()).catch(() => {}); } catch (_) {} }
    };
    mic = {abort: () => {abort.abort(); closeCapture();}};
    listen.disabled = true;
    try {
      const granted = await root.navigator.mediaDevices.getUserMedia({
        audio: {channelCount:1, echoCancellation:true, noiseSuppression:true},
        video:false
      });
      if (token !== speechRun || muted) {
        for (const track of granted.getTracks()) track.stop();
        return;
      }
      stream = granted;
      const Ctx = root.AudioContext || root.webkitAudioContext;
      context = new Ctx();
      const rate = context.sampleRate;
      if (typeof context.createScriptProcessor !== 'function') throw Error('local_audio_processing_unavailable');
      source = context.createMediaStreamSource(stream);
      processor = context.createScriptProcessor(4096,1,1);
      const segments = [];
      let frames = 0;
      const maxFrames = Math.floor(rate * 5);
      processor.onaudioprocess = event => {
        if (!recording || token !== speechRun) return;
        const channel = event.inputBuffer.getChannelData(0);
        if (frames + channel.length > maxFrames) return;
        segments.push(new Float32Array(channel));
        frames += channel.length;
      };
      source.connect(processor); processor.connect(context.destination);
      recording = true;
      project('listening', 'mic_local_started', 'browser_capture_to_beelink_stt');
      await new Promise(resolve => {
        resolveCapture = resolve;
        timer = root.setTimeout(() => { timer = null; resolveCapture = null; resolve(); }, 2200);
      });
      if (token !== speechRun || muted) return;
      closeCapture();
      const wav = makeWav(segments, frames, rate);
      const audioHash = await hexSha(wav);
      if (token !== speechRun || muted) return;
      const res = await root.fetch('/api/voz/stt', {
        method:'POST', credentials:'same-origin', cache:'no-store', redirect:'error',
        headers: {'Content-Type':'audio/wav', 'X-Hexelion-STT-Command':'transcribe_es_pcm16_v1'},
        body:wav, signal:abort.signal
      });
      const receipt = await res.json();
      if (token !== speechRun || muted) return;
      if (!res.ok) {
        const causes = {
          beelink_cpu_thermal_hold: 'local_stt_thermal_hold',
          beelink_cpu_thermal_hold_after_transcription: 'local_stt_thermal_hold',
          cpu_thermal_sensor_unavailable: 'local_stt_sensor_unavailable',
          hardware_declared_off: 'local_stt_hardware_off',
          local_stt_busy: 'local_stt_busy'
        };
        return project('no_data', causes[receipt.cause] || 'local_stt_host_failed', 'beelink_local_whisper');
      }
      if (receipt.state !== 'LOCAL_TRANSCRIPT_ONLY' ||
          receipt.source !== 'beelink_existing_oido_py_whisper_cpp' ||
          receipt.audio_sha256 !== audioHash || receipt.language !== 'es' ||
          typeof receipt.text !== 'string' || !receipt.text.trim() ||
          receipt.text.length > 600 ||
          receipt.text_sha256 !== await hexSha(new root.TextEncoder().encode(receipt.text))) {
        return project('error', 'local_stt_receipt_invalid', 'beelink_local_whisper');
      }
      lastLocalSTT = Object.freeze(
        Number.isFinite(receipt.inference_ms) && Number.isFinite(receipt.duration_ms)
        ? {state:'MEASURED',source:'beelink_existing_oido_py_whisper_cpp',
           inference_ms:receipt.inference_ms, duration_ms:receipt.duration_ms,
           model_sha256:receipt.model_sha256 || 'NO_DATA', audio_sha256:audioHash,
           text_sha256:receipt.text_sha256}
        : {state:'NO_DATA',cause:'measurement_fields_missing'});
      input.value = receipt.text;
      input.dispatchEvent(new root.Event('input', {bubbles:true}));
      project('thinking', 'transcript_submitted_via_existing_talk', 'beelink_local_whisper+Talk_existing');
      form.requestSubmit();
    } catch (error) {
      if (token === speechRun) project('no_data',
        error && error.name === 'NotAllowedError' ? 'local_stt_permission_refused' : 'local_stt_host_failed',
        'browser_capture_to_beelink_stt');
    } finally {
      closeCapture();
      if (token === speechRun) mic = null;
      listen.disabled = false;
    }
  }

  async function startMic() {
    if (muted) return project('muted', 'operator_muted', 'operator_local_only');
    if (mic) return;
    const Recognition = root.SpeechRecognition || root.webkitSpeechRecognition;
    // Never instantiate legacy remote-capable recognition without an explicit local check.
    if (!Recognition || typeof Recognition.available !== 'function') {
      return startHostMic();
    }
    listen.disabled = true;
    const token = ++speechRun;
    let hostFallback = false;
    try {
      const availability = await Recognition.available({ langs: ['es-ES'], processLocally: true });
      if (token !== speechRun) return;
      if (availability !== 'available') {
        hostFallback = true;
        return await startHostMic();
      }
      const instance = new Recognition();
      if (!('processLocally' in instance)) return project('no_data', 'local_stt_unavailable', 'browser_local_stt_probe');
      instance.processLocally = true; instance.lang = 'es-ES';
      instance.continuous = false; instance.interimResults = false;
      mic = instance;
      instance.onstart = () => { if (token === speechRun) project('listening', 'mic_local_started', 'browser_local_stt'); };
      instance.onresult = (event) => {
        if (token !== speechRun || muted) return;
        const transcript = String(event.results?.[0]?.[0]?.transcript || '').trim().slice(0, 600);
        if (!transcript) return project('no_data', 'local_stt_no_text', 'browser_local_stt');
        input.value = transcript;
        input.dispatchEvent(new Event('input', { bubbles: true }));
        mic = null;
        project('thinking', 'transcript_submitted_via_existing_talk', 'browser_local_stt+Talk');
        // The existing Talk form determines profile, model, permissions and the only network route.
        form.requestSubmit();
      };
      instance.onerror = (event) => {
        if (token !== speechRun) return;
        mic = null;
        project(event && event.error === 'not-allowed' ? 'no_data' : 'error',
          event && event.error === 'not-allowed' ? 'local_stt_permission_refused' : 'local_stt_error', 'browser_local_stt');
      };
      instance.onend = () => {
        if (token !== speechRun) return;
        mic = null;
        if (state.state === 'listening') project('no_data', 'local_stt_no_text', 'browser_local_stt');
      };
      instance.start(); // user clicked. Microphone permission remains browser-owned.
    } catch (_) { if (token === speechRun) project('no_data', 'local_stt_unavailable', 'browser_local_stt_probe'); }
    finally { if (!hostFallback) listen.disabled = false; }
  }
  function latestMessage() {
    const items = [...thread.querySelectorAll('li')].filter(el =>
      !el.classList.contains('mio') && !el.classList.contains('espera') &&
      el.textContent && el.textContent.trim());
    return items.length ? items[items.length - 1].textContent.trim() : '';
  }
  async function speakLast() {
    if (muted) return project('muted', 'operator_muted', 'operator_local_only');
    // Do not requeue the same utterance while a local reader is already active.
    // Repeated clicks previously replayed the spoken 'Hexelion' state preamble.
    if (state.state === 'speaking') return;
    const phrase = latestMessage();
    if (!phrase) return project('no_data', 'no_visible_response', 'Talk_visible_thread');
    if (mic) { try { mic.abort(); } catch (_) {} mic = null; }
    const token = ++speechRun;
    try {
      if (!root.HexelionNativeVoice) await import('/native_voice.js');
      if (token !== speechRun) return;
      voice = root.HexelionNativeVoice;
      if (!voice || typeof voice.read !== 'function') return project('no_data', 'no_voice_reader', 'native_voice.js');
      project('speaking', 'local_speech_requested_audition_unverified', 'native_voice.js');
      // Read the actual visible reply once, not the changing state sentence:
      // the state remains available in accessible labels and machine JSON without recursive narration.
      const utterance = 'Último mensaje visible, autoría no acreditada: ' + phrase;
      voice.read(utterance.slice(0, 32768), 'es-ES', message => {
        if (token !== speechRun) return;
        if (/Reading visible text/.test(message)) project('speaking', 'local_speech_requested_audition_unverified', 'native_voice.js');
        else if (/Software playback ended/.test(message)) project('idle', 'local_speech_finished_audition_unverified', 'native_voice.js');
        else if (/NO_DATA/.test(message)) project('no_data', 'local_speech_unavailable', 'native_voice.js');
      }, 'browser');
    } catch (_) { if (token === speechRun) project('no_data', 'no_voice_reader', 'native_voice.js'); }
  }
  listen.addEventListener('click', startMic);
  read.addEventListener('click', speakLast);
  stop.addEventListener('click', () => interrupt('operator_interrupted'));
  mute.addEventListener('click', setMute);
  const processing = doc.getElementById('talk-processing');
  if (processing && typeof root.MutationObserver === 'function') {
    new root.MutationObserver(() => {
      if (mic || muted || state.state === 'speaking' || state.state === 'interrupted') return;
      if (processing.dataset.state === 'PROCESSING') project('thinking', 'talk_processing_observed', 'Talk_existing');
      else if (state.state === 'thinking') project('idle', 'talk_reply_not_attested', 'Talk_existing');
    }).observe(processing, { attributes: true, attributeFilter: ['data-state'] });
  }
  // Only a typed cause published by the *existing* Talk status may request this
  // state. Never promote arbitrary model text to an authorization grant.
  const talkStatus = doc.getElementById('estado');
  if (talkStatus && typeof root.MutationObserver === 'function') {
    new root.MutationObserver(() => {
      const cause = talkStatus.dataset.cause;
      if (cause !== 'personal_profile_private_route_denied' && cause !== 'owner_approval_required') return;
      // A later, typed denial always supersedes a prior interrupted/muted/
      // speaking presentation state, but never grants a permission.
      speechRun++;
      if (mic) { try { mic.abort(); } catch (_) {} mic = null; }
      if (voice) { try { voice.stop(); } catch (_) {} }
      if (cause === 'personal_profile_private_route_denied') {
        project('awaiting_authorization', 'owner_profile_required', 'Talk_existing');
      } else {
        project('awaiting_authorization', 'owner_approval_pending', 'Talk_existing');
      }
    }).observe(talkStatus, { attributes: true, attributeFilter: ['data-state', 'data-cause'] });
  }
  root.addEventListener('pagehide', () => { speechRun++; if (mic) try { mic.abort(); } catch (_) {} if (voice) try { voice.stop(); } catch (_) {} });
  project('idle', 'not_started', 'local_ui_only');
  root.HexelionAvatarVoice = Object.freeze({
    state: () => Object.freeze(Object.assign({}, state)),
    lastSTT: () => Object.freeze(Object.assign({}, lastLocalSTT)),
    stop: () => interrupt('operator_interrupted'),
    mute: setMute
  });
})(globalThis);