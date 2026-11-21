"use strict";
const test=require("node:test"),assert=require("node:assert/strict");
const vm=require("node:vm"),fs=require("node:fs"),path=require("node:path");
const src=fs.readFileSync(path.join(__dirname,"../android_heartbeat_bridge.js"),"utf8");
const bridgeJava=fs.readFileSync(path.join(__dirname,
 "../app/src/main/java/org/preceptoros/mvp/HeartbeatOnceBridge.java"),"utf8");
const activity=fs.readFileSync(path.join(__dirname,
 "../app/src/main/java/org/preceptoros/mvp/MainActivity.java"),"utf8");
function fixture(hasNative=true){
 const events=[], sent=[], nodes=new Map();
 const form={insertAdjacentElement(pos,el){assert.equal(pos,"afterend");nodes.set(el.id,el);}};
 nodes.set("node-registration-form",form);
 function element(){
   return {id:"",style:{},dataset:{},listeners:{},children:[],disabled:false,textContent:"",
     setAttribute(k,v){this[k]=v;}, append(...child){this.children.push(...child);},
     addEventListener(k,fn){this.listeners[k]=fn;},click(){this.listeners.click?.();}};
 }
 const document={createElement:element,getElementById:id=>nodes.get(id)||null};
 const crypto=require("node:crypto").webcrypto;
 const native={onmessage:null,postMessage:data=>sent.push(JSON.parse(data))};
 const win={document,crypto,Uint8Array,setTimeout(fn){events.push(fn);return events.length;},
    clearTimeout(){},PreceptorHeartbeatNative:hasNative?native:undefined};win.window=win;
 vm.runInNewContext(src,{window:win,globalThis:win,setTimeout:win.setTimeout,clearTimeout:win.clearTimeout});
 const section=nodes.get("native-heartbeat-once");
 const button=section?.children.find(x=>x.id==="native-heartbeat-send");
 const status=section?.children.find(x=>x.id==="native-heartbeat-status");
 return {win,native,section,button,status,sent,events};
}
test("no browser-only capability and no automatic POST on mount",()=>{
 assert.equal(fixture(false).section,undefined);
 const x=fixture(); assert.equal(x.sent.length,0);
 assert.equal(x.status.dataset.state,"NO_DATA");
 assert.equal(x.button.style.minHeight,"44px");
 assert.match(x.status["aria-live"],/polite/);
});
test("owner click passes NO key, no node identity and no credentials to native",()=>{
 const x=fixture(); x.button.click();
 assert.equal(x.sent.length,1);
 assert.deepEqual(Object.keys(x.sent[0]).sort(),["action","id"]);
 assert.equal(x.sent[0].action,"heartbeat_once");
 assert.match(x.sent[0].id,/^[a-f0-9]{32}$/);
 assert.equal(x.button.disabled,true);
 x.button.click(); assert.equal(x.sent.length,1);
 assert.equal(x.status.dataset.cause,"awaiting_owner_native_confirmation");
 assert.equal(x.status.dataset.acho,x.status.textContent);
});
test("forged callback id ignored; cancellation never marks received",()=>{
 const x=fixture();x.button.click();
 x.native.onmessage({data:JSON.stringify({id:"f".repeat(32),ok:true,result:{state:"RECEIVED"}})});
 assert.equal(x.status.dataset.state,"NO_DATA");
 x.native.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:false,cause:"owner_cancelled"})});
 assert.equal(x.status.dataset.state,"NO_DATA");
 assert.equal(x.status.dataset.cause,"owner_cancelled");
 assert.equal(x.button.disabled,false);
});
test("even native forged LIVE cannot make the UI LIVE",()=>{
 const x=fixture();x.button.click();
 x.native.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:true,result:{
  node:"nodo.42.owner",sequence:0,receiptSha256:"a".repeat(64),
  state:"LIVE",authority:"APPROVED",live:true,publicProof:"VERIFIED"
 }})});
 assert.equal(x.status.dataset.state,"NO_DATA");
 assert.equal(x.status.dataset.cause,"native_receipt_unverified");
});
test("validated native receipt claims only RECEIVED, not independent public LIVE",()=>{
 const x=fixture();x.button.click();
 x.native.onmessage({data:JSON.stringify({id:x.sent[0].id,ok:true,result:{
  node:"nodo.42.owner",sequence:0,receiptSha256:"b".repeat(64),
  state:"RECEIVED",authority:"NONE",live:false,
  publicProof:"NO_DATA(public_live_not_independently_verified)"
 }})});
 assert.equal(x.status.dataset.state,"RECEIVED");
 assert.equal(x.status.dataset.cause,"public_live_not_independently_verified");
 assert.match(x.status.textContent,/NO_DATA\(public_live_not_independently_verified\)/);
 assert.equal(x.status.dataset.acho,x.status.textContent);
 assert.equal(x.button.disabled,false);
});
test("bridge transport is origin+main frame restricted, owner-picked and one-shot",()=>{
 assert.match(bridgeJava,/OwnerFrameAccess\.accepts\([^;]+isMainFrame[^;]+view\.getUrl\(\)/);
 assert.match(bridgeJava,/Collections\.singleton\(ORIGIN\)/);
 assert.match(bridgeJava,/activity\.ownPageVerified\(\)/);
 assert.match(bridgeJava,/Intent\.ACTION_OPEN_DOCUMENT/);
 assert.match(bridgeJava,/ContentResolver/); // negative check supplied by owner file path, no browser key
 assert.match(bridgeJava,/\.setPositiveButton\("Send one heartbeat"/);
 assert.match(bridgeJava,/x-heartbeat-key/);
 assert.match(bridgeJava,/setInstanceFollowRedirects\(false\)/);
 assert.match(bridgeJava,/Receipt|receipt/);
 assert.doesNotMatch(src,/fetch\(|localStorage|x-heartbeat-key|secret|\.key/);
 assert.match(activity,/HeartbeatOnceBridge\.install/);
 assert.doesNotMatch(bridgeJava,/AlarmManager|WorkManager|JobScheduler|startForegroundService|setRepeating/);
});
