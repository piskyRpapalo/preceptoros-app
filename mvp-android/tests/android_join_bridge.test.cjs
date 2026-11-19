"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),vm=require("node:vm"),fs=require("node:fs");
const src=fs.readFileSync(require("node:path").join(__dirname,"../android_join_bridge.js"),"utf8");
function fixture(){
 const result=[];
 const crypto=require("node:crypto").webcrypto;
 const win={crypto,Uint8Array,Promise,setTimeout,clearTimeout,PreceptorJoinNative:{
  postMessage(x){result.push(JSON.parse(x));},onmessage:null
 }};
 win.window=win;
 vm.runInNewContext(src,{window:win,globalThis:win,Uint8Array,Promise,setTimeout,clearTimeout});
 return {win,result};
}
test("safe bridge available only if native listener installed",()=>{
 const win={crypto:require("node:crypto").webcrypto};win.window=win;
 vm.runInNewContext(src,{window:win,globalThis:win});
 assert.equal(win.PreceptorAndroidJoin,undefined);
});
test("unconsented request refused before native call",async()=>{
 const {win,result}=fixture();
 await assert.rejects(win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.alice",purpose:"Research",consent:false}));
 assert.equal(result.length,0);
});
test("native receives only bounded identity/purpose; never host/keys",async()=>{
 const {win,result}=fixture();
 const promise=win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.alice",purpose:"Research",consent:true});
 assert.equal(result.length,1);
 assert.deepEqual(Object.keys(result[0]).sort(),["consent","id","node","purpose"]);
 const m=result[0];assert.match(m.id,/^[a-f0-9]{32}$/);
 const requestId="a".repeat(64);
 win.PreceptorJoinNative.onmessage({data:JSON.stringify({id:m.id,ok:true,result:{contractVerified:true,preliminaryReceiptValidated:true,trackingId:requestId,node:m.node,state:"PENDING",approved:false,live:false}})});
 const out=await promise;assert.equal(out.trackingId,requestId);assert.equal(out.live,false);
});
test("cross callback ID does not resolve different intent",async()=>{
 const {win,result}=fixture();
 const promise=win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.alice",purpose:"Research",consent:true});
 win.PreceptorJoinNative.onmessage({data:JSON.stringify({id:"f".repeat(32),ok:true,result:{}})});
 assert.equal(result.length,1);
 win.PreceptorJoinNative.onmessage({data:JSON.stringify({id:result[0].id,ok:false,cause:"owner_cancelled"})});
 await assert.rejects(promise,/owner_cancelled/);
});
test("deny native fake LIVE",async()=>{
 const {win,result}=fixture();
 const promise=win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.alice",purpose:"Research",consent:true});
 win.PreceptorJoinNative.onmessage({data:JSON.stringify({id:result[0].id,ok:true,result:{contractVerified:true,preliminaryReceiptValidated:true,trackingId:"a".repeat(64),node:"nodo.1.alice",state:"LIVE",approved:true,live:true}})});
 await assert.rejects(promise,/unverified_native_intake_receipt/);
});
test("don't start second overlapping request",async()=>{
 const {win,result}=fixture();
 const promise=win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.alice",purpose:"Research",consent:true});
 await assert.rejects(win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.bob",purpose:"Other",consent:true}),/review_already_in_flight/);
 win.PreceptorJoinNative.onmessage({data:JSON.stringify({id:result[0].id,ok:false,cause:"owner_cancelled"})});
 await assert.rejects(promise,/owner_cancelled/);
});

test("cross-node native reply is rejected",async()=>{
 const {win,result}=fixture();
 const pending=win.PreceptorAndroidJoin.requestPreliminary({node:"nodo.1.alice",purpose:"Research",consent:true});
 win.PreceptorJoinNative.onmessage({data:JSON.stringify({id:result[0].id,ok:true,result:{contractVerified:true,preliminaryReceiptValidated:true,trackingId:"a".repeat(64),node:"nodo.1.bob",state:"PENDING",approved:false,live:false}})});
 await assert.rejects(pending,/unverified_native_intake_receipt/);
});
