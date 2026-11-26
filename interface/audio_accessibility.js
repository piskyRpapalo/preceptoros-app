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
    line.dataset.state=state;line.dataset.cause=cause;line.dataset.acho=(state==="NO_DATA"||state==="BLOCKED")?"silent":state==="REQUESTED"?"uncertain":state==="SPEAKING"?"working":"ok";
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

  // Static audited control names; never export values, messages, agent IDs or arbitrary DOM.
  const controlCatalog = [["tab-conversacion","Talk","navigate","local UI",true],["tab-cuaderno","Operations Data","navigate","local UI",true],["tab-lab","Lab","navigate","local UI",true],["tab-ajustes","My node","navigate","local UI",true],["tab-modelos","Open World","navigate","local UI",true],["tab-settings","Settings","navigate","local UI",true],["control-agents","Agents","disclosure","local UI",false],["mvp-first-run-mini","Find local Mini Orchestrator","activate","NO_DATA(action policy)",true],["mvp-first-run-node","Open Node identity","activate","NO_DATA(action policy)",true],["mvp-first-run-finish","Finish introduction","activate","NO_DATA(action policy)",true],["modelos-toggle","Choose model","activate","NO_DATA(action policy)",true],["mini-local-toggle","Use Mini Orchestrator offline","activate","NO_DATA(action policy)",true],["control-available-model-information","Available model information","disclosure","local UI",false],["control-model-preferences-draft-only","Model preferences (draft only)","disclosure","local UI",false],["control-refresh-talk","Refresh Talk","activate","NO_DATA(action policy)",false],["notebook-document-editor-toggle","Document Editor","activate","NO_DATA(action policy)",true],["notebook-plan-toggle","Write a plan","activate","NO_DATA(action policy)",true],["notebook-refresh","Refresh Operations Data","activate","NO_DATA(action policy)",true],["control-refresh-documents","Refresh Documents","activate","NO_DATA(action policy)",false],["documentos-importar-btn","Import document","activate","NO_DATA(action policy)",true],["documentos-nuevo-btn","New document","activate","NO_DATA(action policy)",true],["documentos-guardar","Save locally","activate","NO_DATA(action policy)",true],["documentos-descargar","Download","activate","NO_DATA(action policy)",true],["documentos-cancelar","Cancel","activate","NO_DATA(action policy)",true],["control-write-a-plan","Write a plan","disclosure","local UI",false],["plan-guardar","Store the plan","activate","NO_DATA(action policy)",true],["plan-releer","Read it back","activate","NO_DATA(action policy)",true],["control-the-stored-text","The stored text","disclosure","local UI",false],["control-shared-rack-lab-results-read-only-benchmark-receipts-and-harness-","Shared Rack LAB · Results Read-only benchmark receipts and harness status","disclosure","local UI",false],["control-memory-compass-consent-and-private-memories","Memory Compass, consent and private memories","disclosure","local UI",false],["mando-ir-firmas","Open Boundary","activate","NO_DATA(action policy)",true],["mando-ir-tareas","Open the Notebook","activate","NO_DATA(action policy)",true],["comandos-hexelion-abrir","Hexelion commands","disclosure","local UI",true],["cmd-estado","/estado rack and house services","activate","NO_DATA(action policy)",true],["cmd-capacidades","/capacidades what Hexelion may do","activate","NO_DATA(action policy)",true],["cmd-registro","/registro 5 last receipts","activate","NO_DATA(action policy)",true],["cmd-firmas","/firmas what awaits your signature","activate","NO_DATA(action policy)",true],["cmd-lab","/lab Lab results","activate","NO_DATA(action policy)",true],["cmd-preceptores","/preceptores which preceptors are working","activate","NO_DATA(action policy)",true],["cmd-dispositivos","/dispositivos devices and their roles","activate","NO_DATA(action policy)",true],["cmd-modelos","/modelos models by node","activate","NO_DATA(action policy)",true],["cmd-ejecuta","/ejecuta [@worktree] <command> run one command","activate","owner approval and effect gate",true],["cmd-escribe","/escribe @worktree <path> :: <text> write one file","activate","owner approval and effect gate",true],["cmd-ayuda","@ayuda help for this panel","activate","NO_DATA(action policy)",true],["control-memory-and-consent","Memory and consent","disclosure","local UI",false],["memoria-inicio-boton","Create my private memory","activate","NO_DATA(action policy)",true],["captura-consent-summary","Training consent · captured turns","disclosure","local UI",true],["switch","Redacción","activate","NO_DATA(action policy)",true],["probar","Pasar por el filtro","activate","NO_DATA(action policy)",true],["anidar","Anidar esto en tu memoria","activate","NO_DATA(action policy)",true],["control-el-payload-tal-cual-llego","El payload, tal cual llegó","disclosure","local UI",false],["control-technical-evidence-and-causes","Technical evidence and causes","disclosure","local UI",false],["compass-modo-camino","The Path","activate","NO_DATA(action policy)",true],["compass-modo-detalle","Detail","activate","NO_DATA(action policy)",true],["control-requests-and-answers-requests-responses-and-source-evidence","Requests and answers Requests, responses and source evidence","disclosure","local UI",false],["control-delegated-tasks-delegations-and-their-recorded-outcomes","Delegated tasks Delegations and their recorded outcomes","disclosure","local UI",false],["control-plans-and-their-tasks-saved-plans-and-linked-tasks","Plans and their tasks Saved plans and linked tasks","disclosure","local UI",false],["control-agents-observed-agents-observed-not-assumed-active","Agents observed Agents observed, not assumed active","disclosure","local UI",false],["control-reviews-wbr-mbr-weekly-and-monthly-review-receipts","Reviews · WBR / MBR Weekly and monthly review receipts","disclosure","local UI",false],["control-command-receipts-operational-receipts-from-command","Command receipts Operational receipts from Command","disclosure","local UI",false],["control-studies-and-proposals-proposals-and-external-study-references","Studies and proposals Proposals and external study references","disclosure","local UI",false],["lab-bench-toggle","Benchmarks","activate","NO_DATA(action policy)",true],["control-refresh-the-lab","Refresh the Lab","activate","NO_DATA(action policy)",false],["lab-first-experiment","Write my first experiment plan","activate","NO_DATA(action policy)",true],["control-runs-from-plans-results-of-work-started-from-plans","Runs from plans Results of work started from plans","disclosure","local UI",false],["control-benchmarks-reproducible-runs-reproducible-tests-and-their-evidenc","Benchmarks · reproducible runs Reproducible tests and their evidence","disclosure","local UI",false],["control-canales-recientes-channels-reported-by-this-device","Canales recientes Channels reported by this device","disclosure","local UI",false],["control-modelos-locales-local-model-inventory-when-available","Modelos locales Local model inventory, when available","disclosure","local UI",false],["control-lab-loops-loop-runs-timing-and-measured-outcomes","Lab loops Loop runs, timing and measured outcomes","disclosure","local UI",false],["control-connection-details-availability-and-connection-causes","Connection details Availability and connection causes","disclosure","local UI",false],["control-boundary-approvals-signatures-and-permissions","Boundary Approvals, signatures and permissions","disclosure","local UI",false],["control-refresh-the-signature-list","Refresh the signature list","activate","NO_DATA(action policy)",false],["hitl-cabecera","Firmas HITL · …","activate","NO_DATA(action policy)",true],["hitl-recargar","Actualizar lista","activate","NO_DATA(action policy)",true],["hitl-si","Sí, firmo y fusiono","activate","owner approval and effect gate",true],["hitl-no","No","activate","NO_DATA(action policy)",true],["control-harness-agents-tools-and-execution-evidence","Harness Agents, tools and execution evidence","disclosure","local UI",false],["control-refresh-the-loops-and-the-team","Refresh the loops and the team","activate","NO_DATA(action policy)",false],["control-operator-visibility-local-agents","Operator visibility · local agents","disclosure","local UI",false],["control-agent-questions-to-hexelion","Agent questions to Hexelion","disclosure","local UI",false],["control-engine-measured-cycles","Engine: measured cycles","disclosure","local UI",false],["openworld-retry","Reintentar OpenWorld","activate","NO_DATA(action policy)",true],["mynode-identity-toggle","Node identity","activate","NO_DATA(action policy)",true],["mynode-building-toggle","Create building","activate","NO_DATA(action policy)",true],["control-refresh-my-node","Refresh My node","activate","NO_DATA(action policy)",false],["control-getting-started-installation-guide-first-steps-instructions-and-i","Getting started · installation guide First steps, instructions and installation","disclosure","local UI",false],["mvp-first-run-reopen","Show three-step introduction again","activate","NO_DATA(action policy)",true],["mvp-open-node","Open node identity setup","activate","NO_DATA(action policy)",true],["control-node-identity-local-node-id-and-identity-controls","Node identity Local node ID and identity controls","disclosure","local UI",false],["mini-recovery-preview-button","Preview MINI recovery","activate","NO_DATA(action policy)",true],["mini-recovery-import","Recover project locally","activate","NO_DATA(action policy)",true],["node-default-save","Keep these defaults on this device","activate","NO_DATA(action policy)",true],["node-default-reset","Restore example","activate","NO_DATA(action policy)",true],["node-default-id","Suggest my node ID","activate","NO_DATA(action policy)",true],["node-admission-open","Prepare admission request","activate","NO_DATA(action policy)",true],["node-identity-read","Leer identidad local","activate","NO_DATA(action policy)",true],["node-identity-save","Provisionar identidad local","activate","NO_DATA(action policy)",true],["control-declare-an-assigned-building-requires-verified-local-service","Declare an assigned building (requires verified local service)","disclosure","local UI",false],["node-building-submit","Declarar edificio asignado","activate","owner approval and effect gate",true],["control-advanced-admission-tools-review-required","Advanced admission tools (review required)","disclosure","local UI",false],["nodo-export-send","Enviar a la aduana","activate","owner approval and effect gate",true],["control-preview-deployment-request","Preview deployment request","activate","NO_DATA(action policy)",false],["node-registration-submit","Sign deployment · request review","activate","owner approval and effect gate",true],["node-admission-finish","Finish admission on this device","activate","owner approval and effect gate",true],["node-heartbeat-start","Create my heartbeat key","activate","NO_DATA(action policy)",true],["node-heartbeat-send","Send one heartbeat now","activate","owner approval and effect gate",true],["companion-generate","Prepare one-building draft","activate","NO_DATA(action policy)",true],["companion-copy","Copy draft","activate","NO_DATA(action policy)",true],["companion-download","Download draft","activate","NO_DATA(action policy)",true],["companion-reset","Clear form","activate","NO_DATA(action policy)",true],["control-create-your-building-create-a-building-draft-on-this-device","Create your building Create a building draft on this device","disclosure","local UI",false],["room-building-create","Create my building draft","activate","NO_DATA(action policy)",true],["room-building-download","Download my draft","activate","NO_DATA(action policy)",true],["room-building-clear","Clear draft","activate","NO_DATA(action policy)",true],["control-this-device-and-privacy-updates-storage-and-privacy-choices","This device and privacy Updates, storage and privacy choices","disclosure","local UI",false],["update-check","Check for update","activate","NO_DATA(action policy)",true],["update-reload","Reload to use the update","activate","NO_DATA(action policy)",true],["install-app","Install PreceptorOS","activate","NO_DATA(action policy)",true],["energy-read","Read energy","activate","NO_DATA(action policy)",true],["control-machine-readable-receipt","Machine-readable receipt","disclosure","local UI",false],["keep-device","Keep it","activate","NO_DATA(action policy)",true],["control-voice-and-creations-optional-voice-and-creation-tools","Voice and creations Optional voice and creation tools","disclosure","local UI",false],["creation-voice-generate","Generate voice downloads","activate","NO_DATA(action policy)",true],["creation-publish-send","Verify and import","activate","owner approval and effect gate",true],["control-public-gate-and-local-tray-admission-status-and-local-tray","Public gate and local tray Admission status and local tray","disclosure","local UI",false],["tx-24","Public gate","disclosure","local UI",true],["puerta-copiar-llave","Copiar llave","activate","NO_DATA(action policy)",true],["puerta-copiar-documento","Copiar documento fuente","activate","NO_DATA(action policy)",true],["tray-read","Read local tray","activate","NO_DATA(action policy)",true],["control-appearance-day-night-or-device-preference","Appearance Day, night or device preference","disclosure","local UI",false],["control-accessibility-text-size-and-optional-animation","Accessibility Text size and optional animation","disclosure","local UI",false],["settings-speech-rate","Native speech speed","select","NO_DATA(action policy)",true],["settings-sound-test","Test sound","activate","NO_DATA(action policy)",true],["settings-speech-read","Read current area","activate","NO_DATA(action policy)",true],["settings-speech-stop","Stop speech","activate","NO_DATA(action policy)",true],["control-connection-and-privacy-pause-my-node-and-open-world-without-delet","Connection and privacy Pause My node and Open World without deleting data","disclosure","local UI",false],["connection-kill","Kill switch · Pause My node and Open World","activate","NO_DATA(action policy)",true],["control-about-this-app-what-s-local-what-needs-a-service","About this APP What's local, what needs a service","disclosure","local UI",false],["settings-reset","Restore display defaults","activate","NO_DATA(action policy)",true],["ayuda-efimera-cerrar","Close help","activate","NO_DATA(action policy)",true],["talk-crab-check","Check Talk activity","activate","NO_DATA(action policy)",true],["enviar","Dilo","activate","NO_DATA(action policy)",true],["detener-chat","Stop waiting for Hexelion","activate","NO_DATA(action policy)",true]];
  function createControlReader(doc,root,catalog){
  const table=new Map(catalog.map(row=>[row[0],row]));
  const panels=new Set(["conversacion","cuaderno","lab","ajustes","modelos","settings"]);
  const normalize=s=>typeof s==="string"?s.replace(/\s+/g," ").trim():"";
  const fail=cause=>({state:"NO_DATA",cause,authorization:"NOT_GRANTED_BY_READ"});
  function locate(row){return row[4]?doc.getElementById(row[0]):doc.querySelector('[data-acho-control="'+row[0]+'"]');}
  function visibility(el){
    for(let n=el;n;n=n.parentElement){
      if(n.hidden||n.inert||n.getAttribute("aria-hidden")==="true")return "HIDDEN";
      const style=root.getComputedStyle?.(n);
      if(style&&(style.display==="none"||style.visibility==="hidden"||style.visibility==="collapse"))return "HIDDEN";
      if(n.tagName==="DETAILS"&&!n.open&&n!==el){
        const summary=Array.from(n.children).find(c=>c.tagName==="SUMMARY");
        if(!summary||!summary.contains(el))return "HIDDEN";
      }
    }
    return "VISIBLE";
  }
  function read(id){
    if(!doc||typeof id!=="string"||!table.has(id))return fail("control_not_in_static_catalog");
    const row=table.get(id),el=locate(row);
    if(!el)return fail("control_mount_missing");
    let available=visibility(el);
    if(available==="VISIBLE"&&(el.matches(":disabled")||el.getAttribute("aria-disabled")==="true"||el.closest('[aria-disabled="true"]')))available="DISABLED";
    const states=[];
    for(const a of ["aria-selected","aria-expanded","aria-pressed","aria-checked"]){
      const v=el.getAttribute(a);if(v==="true"||v==="false"||v==="mixed")states.push(a.slice(5)+"="+v);
    }
    if(el.tagName==="SUMMARY"&&el.parentElement?.tagName==="DETAILS")states.push("expanded="+String(el.parentElement.open));
    const raw=el.hasAttribute("aria-labelledby")?null:normalize(el.getAttribute("aria-label")||el.textContent);
    // Publish only audited labels; translated/dynamic names need reviewed scope.
    const nameVerified=raw===row[1];
    const scope=el.closest('[role="tabpanel"]')?.id?.replace(/^panel-/,"")||"global";
    const panel=panels.has(scope)?scope:"global", state=states.join(", ")||"NO_DATA(control state)";
    const sentence=row[1]+". "+row[2]+". "+available+". "+state+". "+
      (nameVerified?"":"NO_DATA(current accessible name). ")+"Requirement: "+row[3]+". Read grants no action.";
    const frame={v:"preceptoros.acho/1",id,t:0,cv:[1024,160],seal:nameVerified?"STATIC":"NO_DATA",
      atoms:[{k:"control",r:sentence,i:[{o:"text",x:12,y:35,tx:sentence,sz:12,f:"paper",s:"ink"}]}],
      bands:["paper","ink"],change:[],sound:"NO_DATA",soundCause:"audible output not measured",motion:"NO_DATA"};
    if(typeof root.TextEncoder!=="function")return fail("utf8_encoder_unavailable");
    const frameBytes=new root.TextEncoder().encode(JSON.stringify(frame)).length;
    if(frameBytes>=1024||sentence.length>420)return fail("acho_frame_exceeds_limit");
    return {id,panel,name:row[1],accessible_name:nameVerified?row[1]:null,function:row[2],
      state,availability:available,authorization:"NOT_GRANTED_BY_READ",requirement:row[3],
      source:"APP static control and current DOM",cause:nameVerified?null:"current_accessible_name_not_verified",
      text:sentence,frame,frame_bytes:frameBytes};
  }
  function focused(){
    if(!doc)return fail("document_unavailable");
    const el=doc.activeElement?.closest?.("button,summary,select");
    return el?read(el.id||el.getAttribute("data-acho-control")):fail("no_focused_control");
  }
  return Object.freeze({read,focused,ids:()=>Array.from(table.keys())});
}
  const controls=createControlReader(doc,root,controlCatalog);
  function read(){
    const control=controls.focused();
    if(!control.frame)return speak(area());
    const description=$("acho-control-description");
    if(description){description.textContent=control.text;description.hidden=false;}
    return speak(control.text);
  }
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
  const api=Object.freeze({mount,read,stop,setEnabled,area,speak,hasSpeech,tone,controls});
  root.PreceptorAudioAccessibility=api;
  if(typeof module==="object"&&module.exports)module.exports=api;
  if(doc){if(doc.readyState==="loading")doc.addEventListener("DOMContentLoaded",mount,{once:true});else mount();}
})(typeof window==="object"?window:globalThis);
