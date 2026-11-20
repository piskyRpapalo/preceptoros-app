/* Android-only native one-shot heartbeat: the credential NEVER reaches JavaScript.
 * This is not the existing node admission bridge, not a signer and not a LIVE monitor.
 */
(function(root){
 "use strict";
 const native=root.PreceptorHeartbeatNative;
 const form=root.document&&root.document.getElementById("node-registration-form");
 if(!native || typeof native.postMessage!=="function" || !form ||
    root.document.getElementById("native-heartbeat-once"))return;
 const section=root.document.createElement("section");
 section.id="native-heartbeat-once";
 section.setAttribute("aria-label","Owner heartbeat, Android only");
 const instruction=root.document.createElement("p");
 instruction.textContent="After human approval and operator provisioning, select your own local key file. Android sends one heartbeat only after a second native confirmation. A receipt does not prove LIVE.";
 const button=root.document.createElement("button");
 button.type="button"; button.id="native-heartbeat-send";
 button.textContent="Choose credential · send one heartbeat";
 button.style.minHeight="44px";
 const status=root.document.createElement("p");
 status.id="native-heartbeat-status";
 status.setAttribute("role","status");
 status.setAttribute("aria-live","polite");
 function paint(state,cause,words){
   status.dataset.state=state;
   status.dataset.cause=cause;
   status.dataset.acho=words;
   status.textContent=words;
 }
 paint("NO_DATA","owner_credential_not_selected",
       "NO_DATA(owner_credential_not_selected). No heartbeat sent. Approval and key provisioning are separate.");
 section.append(instruction,button,status);
 form.insertAdjacentElement("afterend",section);
 let waiting=null;
 const hex=bytes=>Array.from(bytes,b=>b.toString(16).padStart(2,"0")).join("");
 native.onmessage=function(evt){
   let data;try{data=JSON.parse(evt.data);}catch{return;}
   if(!waiting || data.id!==waiting.id)return;
   clearTimeout(waiting.timer);waiting=null;button.disabled=false;
   if(!data.ok){
     const cause=typeof data.cause==="string"&&/^[a-z0-9_]+$/.test(data.cause)?data.cause:"native_reply_invalid";
     paint("NO_DATA",cause,"NO_DATA("+cause+"). No confirmed heartbeat receipt.");
     return;
   }
   const r=data.result;
   if(!r || r.state!=="RECEIVED" || r.authority!=="NONE" ||
      r.live!==false || r.publicProof!=="NO_DATA(public_live_not_independently_verified)" ||
      typeof r.node!=="string" || !/^nodo\.[0-9]{1,6}\.[a-z0-9][a-z0-9-]{0,30}$/.test(r.node) ||
      !Number.isSafeInteger(r.sequence) || r.sequence<0 ||
      !/^[a-f0-9]{64}$/.test(r.receiptSha256||"")){
     paint("NO_DATA","native_receipt_unverified","NO_DATA(native_receipt_unverified). No LIVE claim.");
     return;
   }
   paint("RECEIVED","public_live_not_independently_verified",
     "RECEIVED by Aduana: "+r.node+", sequence "+r.sequence+
     ". Receipt SHA-256 "+r.receiptSha256.slice(0,16)+
     "…; NO_DATA(public_live_not_independently_verified). Authority not granted.");
 };
 button.addEventListener("click",()=>{
   if(waiting)return;
   if(!root.crypto || typeof root.crypto.getRandomValues!=="function"){
     paint("NO_DATA","secure_nonce_unavailable","NO_DATA(secure_nonce_unavailable). Nothing sent.");return;
   }
   const id=hex(root.crypto.getRandomValues(new Uint8Array(16)));
   button.disabled=true;
   paint("NO_DATA","awaiting_owner_native_confirmation",
     "NO_DATA(awaiting_owner_native_confirmation). Select an owner key; Android asks again before sending.");
   const timer=root.setTimeout(()=>{
     waiting=null;button.disabled=false;
     paint("NO_DATA","native_receipt_timeout","NO_DATA(native_receipt_timeout). Delivery not verified.");
   },180000);
   waiting={id,timer};
   try{native.postMessage(JSON.stringify({id,action:"heartbeat_once"}));}
   catch(_){clearTimeout(timer);waiting=null;button.disabled=false;
     paint("NO_DATA","native_message_unavailable","NO_DATA(native_message_unavailable). Nothing confirmed.");}
 });
})(typeof window==="object"?window:globalThis);
