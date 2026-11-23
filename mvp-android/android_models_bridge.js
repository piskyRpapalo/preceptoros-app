/* Android-only: the EXISTING model picker (#modelos-menu) gains the rack models, and the EXISTING Talk form and
 * thread (#form-chat, #hilo) talk to the chosen one. No second chat, no second orchestrator.
 * Every visible state comes from a native event (sent, loading, token, done, error, cancelled, speech start/end):
 * the crab (#talk-processing data-state), Acho (data-acho + sentence + voice) and the JSON say the same thing.
 */
(function(root){
 "use strict";
 const doc=root.document, native=root.PreceptorModelsNative;
 const menu=doc&&doc.getElementById("modelos-menu"), toggle=doc&&doc.getElementById("modelos-toggle");
 const form=doc&&doc.getElementById("form-chat"), thread=doc&&doc.getElementById("hilo");
 const crab=doc&&doc.getElementById("talk-processing");
 if(!native||typeof native.postMessage!=="function"||!menu||!form||!thread||doc.getElementById("rack-models"))return;
 const input=form.querySelector("textarea,input[type=text]");
 const el=(t,p)=>Object.assign(doc.createElement(t),p||{});
 const KEY="preceptoros.rack-model/1";
 const box=el("section",{id:"rack-models"});
 box.setAttribute("aria-labelledby","rack-models-title");
 const title=el("h4",{id:"rack-models-title",textContent:"Rack models"});
 const help=el("p",{className:"pie",textContent:"Choose the AI that answers in Talk. A model runs on the rack device shown; READY means loaded now. Only a completed answer from this APP marks it verified."});
 const setup=el("button",{type:"button",id:"rack-models-setup",textContent:"Connect to my rack"});
 const refresh=el("button",{type:"button",id:"rack-models-refresh",textContent:"Refresh models"});
 const list=el("div",{id:"rack-models-list",role:"radiogroup"});
 list.setAttribute("aria-labelledby","rack-models-title");
 const status=el("p",{id:"rack-model-status"});
 status.setAttribute("role","status");status.setAttribute("aria-live","polite");
 const json=el("pre",{id:"rack-model-json"});json.setAttribute("aria-label","Model state as JSON");
 const speakToggle=el("button",{type:"button",id:"rack-model-speak",textContent:"Read answers aloud"});
 speakToggle.setAttribute("aria-pressed","false");
 const stop=el("button",{type:"button",id:"rack-model-stop",textContent:"Stop",hidden:true});
 for(const b of [setup,refresh,speakToggle,stop])b.style.minHeight="44px";
 box.append(title,help,setup,refresh,list,speakToggle,status,json);
 menu.append(box);
 form.append(stop);

 // ---- one state, every reading ----
 const SAY={
  NO_MODEL:"Mini Orchestrator is answering locally. Open the model picker to choose a rack model.",
  NOT_CONNECTED:"Not connected to your rack yet. Press Connect to my rack.",
  LISTING:"Asking your rack which models it has…",
  READY:"Ready. {m} will answer your next message.",
  SENT:"Question sent to {m}.",
  LOADING:"{m} is loading on {d}. The crab walks while it loads.",
  GENERATING:"{m} is answering.",
  SPEAKING:"Reading the answer aloud.",
  DONE:"{m} answered.",
  CANCELLED:"Stopped. No more of this answer will arrive.",
  ERROR:"Not answered: {c}."
 };
 const CRAB={LOADING:"LOADING",SENT:"LOADING",GENERATING:"GENERATING",SPEAKING:"SPEAKING"};
 const ACHO={NO_MODEL:"silent",NOT_CONNECTED:"needs_you",LISTING:"thinking",READY:"ok",SENT:"thinking",LOADING:"thinking",
   GENERATING:"thinking",SPEAKING:"speaking",DONE:"ok",CANCELLED:"silent",ERROR:"uncertain"};
 let chosen=null,catalog=null,run=null,speaking=false;
 const conversation=[];
 const pub={};
 function show(state,extra){
   Object.keys(pub).forEach(k=>delete pub[k]);
   Object.assign(pub,{state,model:chosen?chosen.key:null,device:chosen?chosen.device:null},extra||{});
   const c=typeof pub.cause==="string"&&/^[a-z0-9_]{1,96}$/.test(pub.cause)?pub.cause:"unknown";
   status.textContent=SAY[state].replace("{m}",chosen?chosen.name:"Mini").replace("{d}",chosen?chosen.device:"").replace("{c}",c.replace(/_/g," "));
   status.dataset.state=state;status.dataset.acho=ACHO[state];
   if(pub.cause)status.dataset.cause=c;else delete status.dataset.cause;
   json.textContent=JSON.stringify(pub,null,1);
   if(crab){
     crab.dataset.state=CRAB[state]||"IDLE";
     crab.dataset.acho=ACHO[state];
     const label=doc.getElementById("talk-processing-label");
     if(label){label.hidden=!CRAB[state];label.textContent=CRAB[state]?status.textContent:"";}
   }
   stop.hidden=!(run||speaking);
 }
 const rid=()=>Array.from(root.crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");
 const waiting=new Map();
 native.onmessage=evt=>{
   let d;try{d=JSON.parse(evt.data);}catch(e){return;}
   const h=waiting.get(d.id);if(h)h(d);
 };
 function ask(msg,handler){const id=rid();waiting.set(id,handler);native.postMessage(JSON.stringify(Object.assign({id},msg)));return id;}

 // ---- the picker ----
 function label(m){
   const parts=[m.name,m.device,m.where==="RACK"?"rack":"local",m.state];
   if(m.parameters)parts.push(m.parameters);
   if(Array.isArray(m.capabilities))parts.push("declares: "+m.capabilities.join(", "));
   parts.push(m.e2e?"verified from this APP":"not verified yet");
   parts.push("needs network");
   return parts.join(" · ");
 }
 function paintList(){
   list.textContent="";
   const mini=el("label",{className:"fila-switch"});
   const r0=el("input",{type:"radio",name:"rack-model",value:"",checked:!chosen});
   mini.append(r0," Mini Orchestrator · local, deterministic");list.append(mini);
   r0.addEventListener("change",()=>{chosen=null;save();toggle.textContent="Mini Orchestrator · local";show("NO_MODEL");});
   for(const d of (catalog&&catalog.devices)||[])if(d.state!=="ONLINE"){
     list.append(el("p",{className:"pie",textContent:d.id+" · OFFLINE · "+(d.cause||"").replace(/_/g," ")}));
   }
   for(const m of (catalog&&catalog.models)||[]){
     const row=el("label",{className:"fila-switch"});
     const r=el("input",{type:"radio",name:"rack-model",value:m.key,checked:!!chosen&&chosen.key===m.key,disabled:!m.chat});
     row.append(r," "+label(m)+(m.chat?"":" · not a chat model"));
     r.addEventListener("change",()=>{chosen={key:m.key,name:m.name,device:m.device};save();
       toggle.textContent=m.name+" · "+m.device;show("READY");});
     list.append(row);
   }
 }
 function save(){try{root.localStorage.setItem(KEY,JSON.stringify(chosen));}catch(e){}}
 try{const s=JSON.parse(root.localStorage.getItem(KEY)||"null");if(s&&typeof s.key==="string")chosen=s;}catch(e){}
 function load(){
   show("LISTING");
   ask({op:"list"},d=>{
     if(!d.ok){show(d.cause==="serve_not_configured"?"NOT_CONNECTED":"ERROR",{cause:d.cause});return;}
     catalog=d.catalog;
     if(chosen&&!catalog.models.some(m=>m.key===chosen.key&&m.chat))chosen=null;
     paintList();
     if(chosen)toggle.textContent=chosen.name+" · "+chosen.device;
     show(chosen?"READY":"NO_MODEL",{models:catalog.models.length,chat_models:catalog.models.filter(m=>m.chat).length,
       devices:catalog.devices.map(x=>x.id+":"+x.state)});
   });
 }
 setup.addEventListener("click",()=>ask({op:"configure"},d=>{if(d.configured)load();else show("NOT_CONNECTED",{cause:d.cause});}));
 refresh.addEventListener("click",load);
 speakToggle.addEventListener("click",()=>speakToggle.setAttribute("aria-pressed",String(speakToggle.getAttribute("aria-pressed")!=="true")));

 // ---- Talk: the same form and thread ----
 function bubble(who,text){
   const li=el("li",{className:who==="user"?"yo":"hexelion"});
   const p=el("p",{textContent:text});li.append(p);thread.append(li);thread.scrollTop=thread.scrollHeight;return p;
 }
 form.addEventListener("submit",e=>{
   if(!chosen||!input)return;           // Mini keeps its own deterministic route
   e.preventDefault();e.stopImmediatePropagation();
   const text=input.value.trim();
   if(!text||run)return;
   input.value="";
   bubble("user",text);
   conversation.push({role:"user",content:text});
   const answer=bubble("assistant","");
   answer.parentNode.dataset.model=chosen.key;
   let got="";
   show("SENT");
   run=ask({op:"chat",modelo:chosen.key,mensajes:conversation.slice(-12)},d=>{
     const ev=d.ev||{};
     if(ev.e==="loading")show("LOADING");
     else if(ev.e==="token"){got+=ev.t;answer.textContent=got;thread.scrollTop=thread.scrollHeight;
       if(status.dataset.state!=="GENERATING")show("GENERATING");}
     else if(ev.e==="done"){run=null;waiting.delete(d.id);conversation.push({role:"assistant",content:got});
       show("DONE",{tokens:ev.tokens,first_token_ms:ev.first_token_ms,total_ms:ev.total_ms});
       if(chosen&&catalog){const m=catalog.models.find(x=>x.key===chosen.key);if(m)m.e2e={at:ev.at};}
       if(speakToggle.getAttribute("aria-pressed")==="true")speak(got);}
     else if(ev.e==="error"||ev.e==="cancelled"){run=null;waiting.delete(d.id);
       if(!got)answer.parentNode.remove();else conversation.push({role:"assistant",content:got});
       if(conversation.length&&conversation[conversation.length-1].role==="user")conversation.pop();
       show(ev.e==="error"?"ERROR":"CANCELLED",ev.e==="error"?{cause:ev.cause}:{});}
   });
   show("SENT");
 },true);
 function speak(text){
   ask({op:"speak",texto:text.slice(0,3800)},d=>{
     const ev=d.ev||{};
     if(ev.e==="speak_start"){speaking=true;show("SPEAKING");}
     else if(ev.e==="speak_done"||ev.e==="speak_stopped"){speaking=false;waiting.delete(d.id);show("DONE");}
     else if(ev.e==="speak_error"){speaking=false;waiting.delete(d.id);show("ERROR",{cause:ev.cause});}
   });
 }
 stop.addEventListener("click",()=>{
   if(run)ask({op:"cancel"},()=>{});
   if(speaking)ask({op:"stop_speech"},()=>{});
 });
 show(chosen?"READY":"NO_MODEL");
 ask({op:"status"},d=>{if(d.configured)load();else show("NOT_CONNECTED");});
})(typeof window!=="undefined"?window:globalThis);
