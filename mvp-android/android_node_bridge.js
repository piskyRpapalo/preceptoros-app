/* Android-only «Create my node»: identity, request, approval, cédula, heartbeat and ONE building.
 * The owner key and the heartbeat key stay in the native app; this page only sees the public state.
 * One state, three readings: the sentence on screen, data-state/data-cause/data-acho for Acho and readers,
 * and the same JSON in <pre>. Approval is never produced here: it is the Sovereign's own signature.
 */
(function(root){
 "use strict";
 const doc=root.document;
 const native=root.PreceptorNodeNative;
 const form=doc&&doc.getElementById("node-registration-form");
 if(!native||typeof native.postMessage!=="function"||!form||doc.getElementById("native-node-owner"))return;
 const el=(tag,props)=>Object.assign(doc.createElement(tag),props||{});
 const card=el("section",{id:"native-node-owner",className:"tarjeta"});
 card.setAttribute("aria-labelledby","native-node-owner-title");
 const title=el("h3",{id:"native-node-owner-title",textContent:"My node in OpenWorld"});
 const help=el("p",{id:"native-node-owner-help",className:"pie",
   textContent:"This phone creates its own identity. After the Sovereign approves it, your node gets exactly one building in OpenWorld."});
 const aliasLabel=el("label",{id:"native-node-alias-label",htmlFor:"native-node-alias",textContent:"Public map name"});
 const alias=el("input",{id:"native-node-alias",maxLength:30,autocomplete:"off",pattern:"[a-z0-9][a-z0-9-]{0,29}"});
 const nodeLabel=el("label",{id:"native-node-id-label",htmlFor:"native-node-id",textContent:"Node identity"});
 const node=el("input",{id:"native-node-id",maxLength:48,autocomplete:"off",pattern:"nodo\\.[0-9]{1,6}\\.[a-z0-9][a-z0-9-]{0,30}"});
 const create=el("button",{type:"button",id:"native-node-create",textContent:"Create my node"});
 const build=el("button",{type:"button",id:"native-node-build",textContent:"Raise my building",disabled:true});
 for(const b of [create,build])b.style.minHeight="44px";
 const status=el("p",{id:"native-node-status"});
 status.setAttribute("role","status");status.setAttribute("aria-live","polite");
 const json=el("pre",{id:"native-node-json"});
 json.setAttribute("aria-label","Node state as JSON");
 card.append(title,help,aliasLabel,alias,nodeLabel,node,create,build,status,json);
 const host=form.closest("section")||form;
 host.insertAdjacentElement("beforebegin",card);

 const SENTENCE={
   no_identity:"This phone has no node yet. Press Create my node.",
   awaiting_approval:"Request sent. Waiting for the Sovereign to approve it with a signature. This screen continues on its own.",
   awaiting_map_link:"Approved: cédula verified. Waiting for the map to place your node.",
   ready_to_build:"Your node is approved and alive. You can raise its building.",
   building_raised:"Your building stands in OpenWorld. One node, one building."
 };
 const ACHO={MEASURED:"ok",PENDING:"needs_you",NO_DATA:"uncertain"};
 let pending=null,edited=false;
 alias.addEventListener("input",()=>{edited=true;if(alias.validity.valid&&alias.value)node.value="nodo.3."+alias.value;});
 node.addEventListener("input",()=>{edited=true;});
 function paint(s){
   const state=["MEASURED","PENDING","NO_DATA"].includes(s.state)?s.state:"NO_DATA";
   const cause=typeof s.cause==="string"&&/^[a-zA-Z0-9_()]{1,64}$/.test(s.cause)?s.cause:"native_reply_invalid";
   const step=typeof s.step==="string"&&SENTENCE[s.step]?s.step:"no_identity";
   let words=state==="NO_DATA"&&cause!=="node_not_created"?"Not done yet: "+cause.replace(/_/g," ")+". "+SENTENCE[step]:SENTENCE[step];
   if(step==="building_raised"&&typeof s.building==="string")words="Your building "+s.building+" stands in OpenWorld. One node, one building.";
   status.dataset.state=state;status.dataset.cause=cause;status.dataset.step=step;
   status.dataset.acho=ACHO[state];status.textContent=words;
   const pub={state,step,cause};
   for(const k of ["node","alias","request_id","building","key_until","last_beat"])if(s[k]!=null)pub[k]=s[k];
   json.textContent=JSON.stringify(pub,null,1);
   const has=step!=="no_identity";
   create.disabled=has;alias.disabled=has;node.disabled=has;
   build.disabled=step!=="ready_to_build";
   if(has){alias.value=s.alias||"";node.value=s.node||"";}
   else if(!edited&&typeof s.suggested_alias==="string"){alias.value=s.suggested_alias;node.value="nodo.3."+s.suggested_alias;}
   if(root.AchoMotion&&typeof root.AchoMotion.express==="function"){
     try{root.AchoMotion.express(status,{MEASURED:"ok",PENDING:"needs_you",NO_DATA:"uncertain"}[state],state);}catch(e){}
   }
 }
 native.onmessage=function(evt){
   let data;try{data=JSON.parse(evt.data);}catch(e){return;}
   if(pending&&data.id===pending.id){clearTimeout(pending.timer);pending=null;}
   if(!data.id&&data.cause)return paint(data);
   paint(data);
 };
 function ask(msg){
   if(pending)return;
   const id=Array.from(root.crypto.getRandomValues(new Uint8Array(16)),b=>b.toString(16).padStart(2,"0")).join("");
   pending={id,timer:setTimeout(()=>{pending=null;paint({state:"NO_DATA",cause:"native_timeout",step:status.dataset.step});},60000)};
   native.postMessage(JSON.stringify(Object.assign({id},msg)));
 }
 create.addEventListener("click",()=>{
   if(!alias.validity.valid||!node.validity.valid||!alias.value||!node.value){
     paint({state:"NO_DATA",cause:"invalid_node_or_alias",step:"no_identity"});return;}
   ask({action:"create",node:node.value,alias:alias.value,consent:true});
 });
 build.addEventListener("click",()=>ask({action:"build"}));
 paint({state:"NO_DATA",cause:"node_not_created",step:"no_identity"});
 ask({action:"status"});
 setInterval(()=>{if(!pending)ask({action:"status"});},30000);
})(typeof window!=="undefined"?window:globalThis);
