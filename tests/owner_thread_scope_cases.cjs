"use strict";
const {test}=require("node:test"),a=require("node:assert/strict"),vm=require("node:vm"),fs=require("node:fs");
const src=fs.readFileSync("interface/conversacion.js","utf8");
class E {
 constructor(tag="div"){this.tagName=tag.toUpperCase();this.dataset={};this.children=[];this.className="";this.textContent="";this.hidden=false}
 appendChild(x){x.parentNode=this;this.children.push(x);return x}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(x=>x!==this)}
 setAttribute(){} removeAttribute(){} scrollIntoView(){}
 querySelectorAll(q){return this.children.filter(x=>q.includes("owner-thread")?x.dataset.ownerThread==="true":x.className==="local")}
 querySelector(q){const m=q.match(/data-n="(\d+)"/);return m?this.children.find(x=>x.dataset.n===m[1]):null}
 get lastElementChild(){return this.children.at(-1)}
}
function client(fetch,profile="private_rack"){
 const els=new Map(),doc={readyState:"loading",hidden:false,addEventListener(){},
  getElementById(id){if(!els.has(id))els.set(id,new E());return els.get(id)},
  createElement(t){return new E(t)},createTextNode(t){const x=new E("#text");x.textContent=t;return x}};
 const root={document:doc,PreceptorProfile:profile};
 vm.runInNewContext(src,{window:root,globalThis:root,fetch});
 return {root,api:root.PreceptorConversacion,el:id=>doc.getElementById(id)}
}
const m=n=>({n,name:"Hexelion",kind:"private",text:"synthetic"+n,t:"2026-11-21T00:00:00Z",seal:"NO_DATA"});
const reply=messages=>({ok:true,json:async()=>({schema:"preceptoros.multipreceptor/1",state:"MEASURED",messages,last:messages.at(-1)?.n||0,hidden:0,destinations:[]})});
const rows=c=>c.el("hilo").querySelectorAll('li[data-owner-thread="true"]').map(x=>x.dataset.n);
test("three simulated clients read same upstream thread, not three backends",async()=>{
 const upstream=[m(1)],calls=[];
 const cs=["Beelink","S110","Tank3"].map(id=>client(async path=>{calls.push([id,path]);return reply(upstream)}));
 for(const c of cs)await c.api.sync();
 for(const c of cs)a.deepEqual(rows(c),["1"]);
 upstream.push(m(2));
 for(const c of cs)await c.api.sync();
 for(const c of cs)a.deepEqual(rows(c),["1","2"]);
 a.equal(calls.length,6);a(calls.every(x=>x[1].startsWith("/api/conversacion?desde=")));
});
test("personal denies owner GET+POST without erasing local MINI",async()=>{
 let n=0;const c=client(async()=>{n++}, "personal_mvp"),local=new E("li");
 local.className="local";c.el("hilo").appendChild(local);
 a.equal((await c.api.sync()).cause,"personal_profile_shared_thread_denied");
 a.equal((await c.api.send("hexelion","synthetic")).cause,"personal_profile_shared_thread_denied");
 a.equal(c.el("conv-destinos").dataset.acho,"silent");
 a.deepEqual(c.el("hilo").children,[local]);a.equal(n,0);
});
test("downgrade erases OWNER rows but retains local MINI",async()=>{
 const c=client(async()=>reply([m(1)]));await c.api.sync();
 const local=new E("li");local.className="local";c.el("hilo").appendChild(local);
 c.root.PreceptorProfile="personal_mvp";
 a.equal((await c.api.sync()).cause,"personal_profile_shared_thread_denied");
 a.deepEqual(c.el("hilo").children,[local]);a.deepEqual(Object.keys(c.api.routes()),[]);
});
test("late OWNER response is invalidated by profile downgrade",async()=>{
 let release;const c=client(()=>new Promise(ok=>release=ok));const pending=c.api.sync();
 c.root.PreceptorProfile="personal_mvp";await c.api.sync();
 release(reply([m(1)]));a.equal((await pending).cause,"owner_thread_view_invalidated");
 a.equal(c.el("hilo").children.length,0);
});

test("optimistic addressed OWNER drafts are tagged for deletion, unlike MINI replies",()=>{
 const app=fs.readFileSync("interface/app.js","utf8");
 assertOwnerDraft(app);
});
function assertOwnerDraft(app){
 a.match(app,/const ownerDraft = burbuja\(escrito, "mio"\);\s*ownerDraft\.dataset\.ownerThread = "true"/);
 a.match(app,/const localDraft = burbuja\(escrito, "mio"\);/);
}

test("replacing addressed owner drafts preserves a local MINI row",async()=>{
 const c=client(async()=>reply([m(1)]));
 const local=new E("li");local.className="local";local.textContent="device MINI";
 c.el("hilo").appendChild(local);
 await c.api.sync({replaceLocal:true});
 a(c.el("hilo").children.includes(local),"local MINI must survive OWNER sync");
 a.deepEqual(rows(c),["1"]);
});
