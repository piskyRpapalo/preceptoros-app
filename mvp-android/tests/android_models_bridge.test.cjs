"use strict";
const test=require("node:test"),assert=require("node:assert"),fs=require("fs"),path=require("path"),vm=require("vm");
const src=fs.readFileSync(path.join(__dirname,"../android_models_bridge.js"),"utf8");
function page(){
  const nodes={};
  const mk=tag=>{const e={tagName:tag,dataset:{},attrs:{},children:[],style:{},listeners:{},hidden:false,value:"",textContent:"",
    parentNode:null,setAttribute(k,v){this.attrs[k]=v;},getAttribute(k){return this.attrs[k];},
    append(...c){for(const x of c){if(typeof x==="object"){x.parentNode=this;this.children.push(x);if(x.id)nodes[x.id]=x;}}},
    remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(x=>x!==this);},
    addEventListener(t,f){this.listeners[t]=f;},querySelector(){return nodes.dicho;}};return e;};
  for(const id of ["modelos-menu","modelos-toggle","form-chat","hilo","talk-processing","talk-processing-label","dicho"]){nodes[id]=mk("x");nodes[id].id=id;}
  const sent=[],store={};
  const win={document:{getElementById:i=>nodes[i]||null,createElement:t=>mk(t)},
    PreceptorModelsNative:{postMessage:m=>sent.push(JSON.parse(m))},
    localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v;}},
    crypto:{getRandomValues:a=>{for(let i=0;i<a.length;i++)a[i]=Math.floor(Math.random()*256);return a;}}};
  vm.runInNewContext(src,Object.assign(win,{JSON,Array,Uint8Array,Object,Map,String,Math}));
  const reply=(id,o)=>win.PreceptorModelsNative.onmessage({data:JSON.stringify(Object.assign({id},o))});
  return {nodes,sent,reply,store};
}
const catalog={devices:[{id:"rack-a",state:"ONLINE"},{id:"rack-b",state:"OFFLINE",cause:"host_unreachable"}],
  models:[{key:"rack-a/qwen3:4b",name:"qwen3:4b",device:"rack-a",where:"RACK",state:"AVAILABLE",chat:true,capabilities:["completion"],e2e:null},
          {key:"rack-a/embed",name:"embed",device:"rack-a",where:"RACK",state:"AVAILABLE",chat:false,capabilities:["embedding"],e2e:null}]};
function connected(){
  const p=page();
  p.reply(p.sent[0].id,{configured:true});
  p.reply(p.sent[1].id,{ok:true,catalog});
  return p;
}
const radios=p=>p.nodes["rack-models-list"].children.filter(c=>c.children).flatMap(c=>c.children).filter(c=>c.type==="radio");
test("the existing picker lists every model; non-chat models cannot be chosen",()=>{
  const p=connected();
  const r=radios(p);
  assert.equal(r.length,3);                 // Mini + 2 rack models
  assert.equal(r.find(x=>x.value==="rack-a/embed").disabled,true);
  assert.equal(p.nodes["rack-model-status"].dataset.state,"NO_MODEL");
});
test("a turn: crab, Acho and JSON follow the engine events and stop at done",()=>{
  const p=connected(),s=p.nodes["rack-model-status"],crab=p.nodes["talk-processing"];
  radios(p).find(x=>x.value==="rack-a/qwen3:4b").listeners.change();
  assert.equal(crab.dataset.state,"IDLE");
  p.nodes.dicho.value="hola";
  let stopped=false;p.nodes["form-chat"].listeners.submit({preventDefault(){},stopImmediatePropagation(){stopped=true;}});
  assert.ok(stopped);
  const chat=p.sent.at(-1);assert.equal(chat.op,"chat");assert.equal(chat.modelo,"rack-a/qwen3:4b");
  assert.deepEqual(chat.mensajes,[{role:"user",content:"hola"}]);
  p.reply(chat.id,{ev:{e:"loading"}});assert.equal(crab.dataset.state,"LOADING");
  p.reply(chat.id,{ev:{e:"token",t:"Ho"}});assert.equal(crab.dataset.state,"GENERATING");
  p.reply(chat.id,{ev:{e:"token",t:"la"}});
  p.reply(chat.id,{ev:{e:"done",tokens:2}});
  assert.equal(crab.dataset.state,"IDLE");assert.equal(s.dataset.state,"DONE");
  const j=JSON.parse(p.nodes["rack-model-json"].textContent);
  assert.equal(j.state,s.dataset.state);assert.equal(j.model,"rack-a/qwen3:4b");assert.equal(s.dataset.acho,"ok");
});
test("errors and cancel stop the crab immediately and never invent an answer",()=>{
  const p=connected(),crab=p.nodes["talk-processing"];
  radios(p).find(x=>x.value==="rack-a/qwen3:4b").listeners.change();
  p.nodes.dicho.value="hola";p.nodes["form-chat"].listeners.submit({preventDefault(){},stopImmediatePropagation(){}});
  const chat=p.sent.at(-1);
  p.reply(chat.id,{ev:{e:"loading"}});
  p.reply(chat.id,{ev:{e:"error",cause:"engine_unreachable"}});
  assert.equal(crab.dataset.state,"IDLE");
  assert.equal(p.nodes["rack-model-status"].dataset.cause,"engine_unreachable");
  assert.equal(p.nodes.hilo.children.length,1);   // only the person's line; no empty answer left behind
});
test("Mini stays the default and keeps its own route",()=>{
  const p=connected();
  p.nodes.dicho.value="help";let stopped=false;
  p.nodes["form-chat"].listeners.submit({preventDefault(){},stopImmediatePropagation(){stopped=true;}});
  assert.equal(stopped,false);
});
