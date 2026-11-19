/* PreceptorOS APP · accessible device audio, local-only. Tones reuse Acho.
 * Spoken guidance is on demand; never records audio or reads private prompts.
 * Existing screen-reader support stays primary. No network, microphone or scheduler. */
(function (root) {
  "use strict";
  const KEY = "preceptoros.audio-guidance/1";
  const doc = root.document;
  let enabled = false, rate = 1, sequence = 0;
  const $ = (id) => doc && doc.getElementById(id);
  const TONE = Object.freeze({class:"ok", motif:{portadora:440, moduladora:180, indice:30, dur:0.28, vibrato:false}});
  const clean = (v,n=120) => typeof v==="string" ? v.replace(/[\u0000-\u001f\u007f]/g," ").replace(/\s+/g," ").trim().slice(0,n) : "";
  const hasSpeech = () => !!(root.speechSynthesis && typeof root.speechSynthesis.speak==="function" && typeof root.SpeechSynthesisUtterance==="function");
  function status(state,cause,words) {
    const line=$("settings-audio-status");
    if (!line) return {state,cause};
    line.dataset.state=state;line.dataset.cause=cause;line.dataset.acho=state==="NO_DATA"?"silent":state==="SPEAKING"?"working":"ok";
    line.textContent=words;return {state,cause};
  }
  function persist(){
    try {root.localStorage.setItem(KEY,JSON.stringify({enabled,rate}));return true;}catch{return false;}
  }
  function stop(){
    ++sequence;
    try{root.speechSynthesis?.cancel();}catch{return status("NO_DATA","speech_cancel_unavailable","This device could not stop speech. Use the device screen reader or audio controls.");}
    return status("LOCAL","speech_stopped","Speech stopped.");
  }
  function setEnabled(next){
    enabled=next===true;
    if(!enabled)stop();
    const box=$("settings-speech-enable");if(box)box.checked=enabled;
    const saved=persist();
    const read=$("settings-speech-read");if(read)read.disabled=!enabled;
    return status(saved?"LOCAL":"NO_DATA",saved?"speech_setting_updated":"settings_storage_unavailable",
      (enabled?"Spoken guidance enabled. Press Read current area to hear it.":"Spoken guidance off. Native screen readers remain available.")
      +(saved?"":" This preference may not survive a reload."));
  }
  function area(){
    const active=doc?.querySelector('.pestanas [role="tab"][aria-selected="true"]');
    const label=clean(active?.getAttribute("aria-label")||active?.textContent||"Talk",55);
    const panel=doc?.getElementById(active?.getAttribute("aria-controls")||"");
    const actions=panel?[...panel.querySelectorAll(':scope > .panel-actions button')].filter(b=>!b.disabled&&!b.hidden).map(b=>clean(b.getAttribute("aria-label")||b.textContent,55)).filter(Boolean).slice(0,5):[];
    const rest=label==="Talk"?"Use Choose model for an optional model, or use Mini Orchestrator locally. Open Agents to inspect agents referenced by plans.":
      label==="Settings"?"Use Accessibility for turn sounds, speech and text size. Use Tab and Enter to navigate.":
      "Use Tab to move through actions and disclosure sections. Press Enter to open a section.";
    return "PreceptorOS. "+label+". "+(actions.length?"Available actions: "+actions.join(", ")+". ":"")+rest;
  }
  function speak(text){
    if (!enabled)return status("BLOCKED","user_disabled","Enable spoken guidance before asking for speech.");
    if (!hasSpeech())return status("NO_DATA","native_speech_unavailable","NO_DATA: this device has no available native speech synthesis. Use a screen reader.");
    const safe=clean(text,420);if(!safe)return status("NO_DATA","speech_text_empty","No readable guidance is available.");
    const id=++sequence;
    try{
      root.speechSynthesis.cancel();
      const utterance=new root.SpeechSynthesisUtterance(safe);
      utterance.lang="en";utterance.rate=rate;utterance.volume=0.8;
      utterance.onstart=()=>{if(id===sequence)status("SPEAKING","device_speech_started","Reading guidance aloud. Press Stop speech to interrupt.");};
      utterance.onend=()=>{if(id===sequence)status("LOCAL","speech_finished","Speech completed on this device.");};
      utterance.onerror=()=>{if(id===sequence)status("NO_DATA","speech_failed","NO_DATA: this device could not play speech.");};
      root.speechSynthesis.speak(utterance);
      return status("REQUESTED","native_speech_requested","Speech requested on this device. Audible output is not independently verified.");
    }catch{return status("NO_DATA","speech_refused","NO_DATA: speech synthesis was refused on this device.");}
  }
  function read(){return speak(area());}
  async function tone(){
    if(!root.PreceptorAchoSonido)return status("NO_DATA","acho_engine_missing","NO_DATA: Acho sound engine is unavailable.");
    const out=await root.PreceptorAchoSonido.play(TONE);
    return status(out.state==="played"?"LOCAL":out.state==="off"?"BLOCKED":"NO_DATA",
      out.cause||"test_tone_requested",out.state==="played"?"Test tone requested from the native audio engine.":"Tone unavailable: "+(out.cause||"unknown")+".");
  }
  function mount(){
    if(!doc||!$("settings-speech-enable"))return false;
    try{
      const data=JSON.parse(root.localStorage.getItem(KEY)||"null");
      if(data&&typeof data==="object"){enabled=data.enabled===true;rate=[0.8,1,1.2].includes(data.rate)?data.rate:1;}
    }catch{/* private storage inaccessible; defaults remain off */}
    const check=$("settings-speech-enable"),rateControl=$("settings-speech-rate");
    check.checked=enabled;
    if(rateControl)rateControl.value=String(rate);
    const btn=$("settings-speech-read");if(btn)btn.disabled=!enabled;
    check.addEventListener("change",()=>setEnabled(check.checked));
    rateControl?.addEventListener("change",()=>{
      const next=Number(rateControl.value);rate=[0.8,1,1.2].includes(next)?next:1;persist();
      status("LOCAL","speech_rate_changed","Speech speed: "+rate+" times normal.");
    });
    btn?.addEventListener("click",read);
    $("settings-speech-stop")?.addEventListener("click",stop);
    $("settings-sound-test")?.addEventListener("click",tone);
    doc.addEventListener("keydown",(event)=>{
      if(!event.altKey||!event.shiftKey||event.ctrlKey||event.metaKey||event.repeat)return;
      const target=event.target;
      if(target?.matches?.('input,textarea,select,[contenteditable="true"]'))return;
      if(event.key.toLowerCase()==="r"){event.preventDefault();read();}
      if(event.key.toLowerCase()==="s"){event.preventDefault();stop();}
    });
    status("LOCAL",enabled?"speech_user_enabled":"speech_user_disabled",
      enabled?"Spoken guidance enabled by this browser. Use Read current area.":"Spoken guidance is off until you enable it. Screen readers work independently.");
    return true;
  }
  const api=Object.freeze({mount,read,stop,setEnabled,area,speak,hasSpeech,tone});
  root.PreceptorAudioAccessibility=api;
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(doc){if(doc.readyState==="loading")doc.addEventListener("DOMContentLoaded",mount,{once:true});else mount();}
})(typeof window==="object"?window:globalThis);
