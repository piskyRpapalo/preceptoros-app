/* Android-only owner review bridge. Native WebView message listener is restricted
 * to the signed app's own HTTPS asset origin and the main frame.
 * This code cannot send network requests, sign credentials or grant node status.
 */
(function(root){
 "use strict";
 if(!root.PreceptorJoinNative||typeof root.PreceptorJoinNative.postMessage!=="function")return;
 const pending=new Map();
 const hex=bytes=>[...bytes].map(n=>n.toString(16).padStart(2,"0")).join("");
 const secureId=()=>{
   const c=root.crypto;
   if(!c||typeof c.getRandomValues!=="function")throw Error("secure_nonce_unavailable");
   return hex(c.getRandomValues(new Uint8Array(16)));
 };
 root.PreceptorJoinNative.onmessage=function(event){
   let response;
   try{response=JSON.parse(event.data);}catch{return;}
   if(!response||typeof response.id!=="string"||!pending.has(response.id))return;
   const slot=pending.get(response.id);clearTimeout(slot.timer);pending.delete(response.id);
   if(response.ok!==true||!response.result||typeof response.result!=="object"){
     slot.reject(Error(response.cause||"native_intake_not_confirmed"));return;
   }
   const r=response.result;
   if(r.contractVerified!==true||r.preliminaryReceiptValidated!==true||
      !/^[a-f0-9]{64}$/.test(r.trackingId||"")||
      !["REQUESTED","PENDING"].includes(r.state)||r.approved!==false||r.live!==false||
      r.node!==slot.node){
     slot.reject(Error("unverified_native_intake_receipt"));return;
   }
   slot.resolve(Object.freeze({contractVerified:true,preliminaryReceiptValidated:true,
     trackingId:r.trackingId,node:r.node,state:r.state,approved:false,live:false}));
 };
 root.PreceptorAndroidJoin=Object.freeze({
  requestPreliminary(draft){
   if(!draft||draft.consent!==true||
      typeof draft.node!=="string"||!/^nodo\.[0-9]{1,6}\.[a-z0-9][a-z0-9-]{0,30}$/.test(draft.node)||
      typeof draft.purpose!=="string"||!draft.purpose.trim()||draft.purpose.length>512){
     return Promise.reject(Error("invalid_or_unconsented_request"));
   }
   if(pending.size)return Promise.reject(Error("review_already_in_flight"));
   let id;try{id=secureId()}catch(e){return Promise.reject(e);}
   return new Promise((resolve,reject)=>{
     const timer=setTimeout(()=>{
       pending.delete(id);reject(Error("native_intake_timeout_no_verified_receipt"));
     },18000);
     pending.set(id,{resolve,reject,timer,node:draft.node});
     try{
       root.PreceptorJoinNative.postMessage(JSON.stringify({id,node:draft.node,
         purpose:draft.purpose.trim(),consent:true}));
     }catch(e){clearTimeout(timer);pending.delete(id);reject(Error("native_message_unavailable"));}
   });
  }
 });
})(typeof window==="object"?window:globalThis);
