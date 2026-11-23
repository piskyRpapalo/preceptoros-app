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
  const docListeners={};
  const win={document:{getElementById:i=>nodes[i]||null,createElement:t=>mk(t),addEventListener(t,f){docListeners[t]=f;}},
    PreceptorModelsNative:{postMessage:m=>sent.push(JSON.parse(m))},
    localStorage:{getItem:k=>store[k]||null,setItem:(k,v)=>{store[k]=v;}},
    crypto:{getRandomValues:a=>{for(let i=0;i<a.length;i++)a[i]=Math.floor(Math.random()*256);return a;}}};
  vm.runInNewContext(src,Object.assign(win,{JSON,Array,Uint8Array,Object,Map,String,Math}));
  const reply=(id,o)=>win.PreceptorModelsNative.onmessage({data:JSON.stringify(Object.assign({id},o))});
  for(const k of Object.keys(docListeners))nodes["form-chat"].listeners[k]=(ev)=>docListeners[k](Object.assign({target:nodes["form-chat"]},ev));
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
test("a phone model: rag flag sent, sources shown under the answer, thinking keeps the crab working",()=>{
  const p=page();
  p.reply(p.sent[0].id,{harness:{files:2,passages:9}});
  const local={key:"this-phone/SenseNova.gguf",name:"SenseNova",device:"this-phone",where:"LOCAL_ANDROID",state:"AVAILABLE",chat:true,
    capabilities:"NO_DATA",memory:{fits_now:true,available_mb:11000,needs_mb:8300},runner:"PACKAGED",e2e:null,size_gb:5.8};
  p.reply(p.sent[1].id,{ok:true,catalog:{devices:[{id:"this-phone",state:"ONLINE"}],models:[local],harness:{files:2,passages:9}},rack_cause:"serve_not_configured"});
  assert.match(p.nodes["rack-model-rag-status"].textContent,/2 files, 9 passages/);
  radios(p).find(x=>x.value===local.key).listeners.change();
  p.nodes["rack-model-rag"].listeners.click();
  p.nodes.dicho.value="¿qué dice mi nota?";p.nodes["form-chat"].listeners.submit({preventDefault(){},stopImmediatePropagation(){}});
  const chat=p.sent.at(-1);assert.equal(chat.rag,true);assert.equal(chat.modelo,local.key);
  const crab=p.nodes["talk-processing"];
  p.reply(chat.id,{ev:{e:"sources",sources:[{n:1,file:"nota.md",excerpt:"hola"}]}});
  p.reply(chat.id,{ev:{e:"loading",available_mb:11000,needs_mb:8300}});assert.equal(crab.dataset.state,"LOADING");
  assert.match(p.nodes["rack-model-status"].textContent,/this phone's memory/);
  p.reply(chat.id,{ev:{e:"thinking"}});assert.equal(crab.dataset.state,"GENERATING");
  p.reply(chat.id,{ev:{e:"token",t:"Sí [1]"}});
  p.reply(chat.id,{ev:{e:"done",where:"LOCAL_ANDROID",tokens:3}});
  assert.equal(crab.dataset.state,"IDLE");
  const li=p.nodes.hilo.children.at(-1);
  assert.equal(li.children.at(-1).tagName,"ol");
  assert.equal(JSON.parse(p.nodes["rack-model-json"].textContent).where,"LOCAL_ANDROID");
});
test("not enough memory is said with numbers and the crab stops",()=>{
  const p=page();p.reply(p.sent[0].id,{});
  p.reply(p.sent[1].id,{ok:true,catalog:{devices:[],models:[{key:"this-phone/x.gguf",name:"x",device:"this-phone",where:"LOCAL_ANDROID",state:"AVAILABLE",chat:true}]}});
  radios(p).find(x=>x.value==="this-phone/x.gguf").listeners.change();
  p.nodes.dicho.value="hola";p.nodes["form-chat"].listeners.submit({preventDefault(){},stopImmediatePropagation(){}});
  const chat=p.sent.at(-1);
  p.reply(chat.id,{ev:{e:"error",cause:"memory_budget_insufficient",available_mb:4000,needs_mb:8300}});
  assert.equal(p.nodes["talk-processing"].dataset.state,"IDLE");
  const j=JSON.parse(p.nodes["rack-model-json"].textContent);
  assert.equal(j.cause,"memory_budget_insufficient");assert.equal(j.needs_mb,8300);
});
