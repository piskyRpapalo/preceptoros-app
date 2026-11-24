/* Android-only, owner-consented recurring heartbeat control. */
(function(root){
 "use strict";
 const native=root.PreceptorHeartbeatNative;
 const form=root.document&&root.document.getElementById("node-registration-form");
 if(!native||typeof native.postMessage!=="function"||!form||
    root.document.getElementById("native-heartbeat-service"))return;
 const section=root.document.createElement("section");
 section.id="native-heartbeat-service";
 section.setAttribute("aria-label","Android recurring node presence");
 const title=root.document.createElement("h3");title.textContent="Android · node presence";
 const explanation=root.document.createElement("p");
 explanation.textContent="Optional owner-controlled foreground service. It needs a second native consent, keeps a visible notification and sends the existing heartbeat contract every two minutes. Receipts do not establish public LIVE.";
 const start=root.document.createElement("button");start.type="button";start.textContent="Set up recurring heartbeat";
 const statusButton=root.document.createElement("button");statusButton.type="button";statusButton.textContent="Refresh status";
 const revoke=root.document.createElement("button");revoke.type="button";revoke.textContent="Revoke and stop";
 for(const button of [start,statusButton,revoke])button.style.minHeight="44px";
 const status=root.document.createElement("p");status.setAttribute("role","status");status.setAttribute("aria-live","polite");
 function paint(state,cause,message){status.dataset.state=state;status.dataset.cause=cause;status.dataset.acho=state;status.textContent=message;}
 paint("STOPPED","owner_consent_not_granted","STOPPED(owner_consent_not_granted). No recurring heartbeat is running.");
 section.append(title,explanation,start,statusButton,revoke,status);form.insertAdjacentElement("afterend",section);
 let waiting=null;
 const hex=bytes=>Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");
 const previousOnMessage=native.onmessage;
 native.onmessage=function(event){
   if(typeof previousOnMessage==="function")previousOnMessage(event);
   let data;try{data=JSON.parse(event.data);}catch{return;}
   if(!waiting||data.id!==waiting.id)return;
   clearTimeout(waiting.timer);const action=waiting.action;waiting=null;
   for(const button of [start,statusButton,revoke])button.disabled=false;
   if(!data.ok){const cause=typeof data.cause==="string"&&/^[a-z0-9_]+$/.test(data.cause)?data.cause:"native_reply_invalid";paint("NO_DATA",cause,"NO_DATA("+cause+"). Status is not confirmed.");return;}
   const result=data.result||{};
   if(action==="heartbeat_service_status"){
     if(result.state==="ACTIVE")paint("ACTIVE","public_live_not_independently_verified","ACTIVE: visible service consent is stored"+(result.autoResume?"; resume after restart enabled":"; restart resume disabled")+". Public LIVE unverified.");
     else if(result.state==="STOPPED")paint("STOPPED","owner_consent_not_active","STOPPED. No active recurring consent.");
     else paint("NO_DATA","native_status_invalid","NO_DATA(native_status_invalid).");
   }else if(action==="heartbeat_service_start"){
     if(result.state==="STARTING"&&result.publicProof==="NO_DATA(public_live_not_independently_verified)")paint("STARTING","public_live_not_independently_verified","STARTING visible service for "+result.node+" at "+result.intervalSeconds+"s. Public LIVE unverified.");
     else paint("NO_DATA","native_start_result_invalid","NO_DATA(native_start_result_invalid).");
   }else if(action==="heartbeat_service_revoke"){
     if(result.state==="REVOKED")paint("REVOKED","owner_revoked_consent","REVOKED. Recurring sends stopped; last public heartbeat may persist until expiry.");
     else paint("NO_DATA","native_revoke_result_invalid","NO_DATA(native_revoke_result_invalid).");
   }
 };
 function send(action,button){
   if(waiting)return;
   if(!root.crypto||typeof root.crypto.getRandomValues!=="function"){paint("NO_DATA","secure_nonce_unavailable","NO_DATA(secure_nonce_unavailable). Nothing sent.");return;}
   const id=hex(root.crypto.getRandomValues(new Uint8Array(16)));
   for(const b of [start,statusButton,revoke])b.disabled=true;
   paint("NO_DATA","awaiting_native_confirmation","NO_DATA(awaiting_native_confirmation). Waiting for Android.");
   const timer=root.setTimeout(()=>{waiting=null;for(const b of [start,statusButton,revoke])b.disabled=false;paint("NO_DATA","native_reply_timeout","NO_DATA(native_reply_timeout). Outcome not confirmed.");},180000);
   waiting={id,timer,action};
   try{native.postMessage(JSON.stringify({id,action}));}
   catch(_){clearTimeout(timer);waiting=null;for(const b of [start,statusButton,revoke])b.disabled=false;paint("NO_DATA","native_message_unavailable","NO_DATA(native_message_unavailable). Nothing confirmed.");}
 }
 start.addEventListener("click",()=>send("heartbeat_service_start",start));
 statusButton.addEventListener("click",()=>send("heartbeat_service_status",statusButton));
 revoke.addEventListener("click",()=>send("heartbeat_service_revoke",revoke));
 send("heartbeat_service_status",statusButton);
})(typeof window==="object"?window:globalThis);
