"use strict";
const test=require("node:test"),assert=require("node:assert"),fs=require("fs"),path=require("path"),vm=require("vm");
const src=fs.readFileSync(path.join(__dirname,"../android_node_bridge.js"),"utf8");
function page(){
  const nodes={};
  const mk=tag=>{const e={tagName:tag,dataset:{},attrs:{},children:[],style:{},listeners:{},validity:{valid:true},value:"",disabled:false,
    setAttribute(k,v){this.attrs[k]=v;},append(...c){this.children.push(...c);for(const x of c)if(x.id)nodes[x.id]=x;},
    addEventListener(t,f){this.listeners[t]=f;},insertAdjacentElement(p,e){nodes[e.id]=e;},closest(){return this;}};return e;};
  const form=mk("form");form.id="node-registration-form";nodes[form.id]=form;
  const sent=[];
  const win={document:{getElementById:id=>nodes[id]||null,createElement:t=>mk(t)},
    PreceptorNodeNative:{postMessage:m=>sent.push(JSON.parse(m))},
    crypto:{getRandomValues:a=>a.fill(7)},setTimeout:()=>0,clearTimeout:()=>0,setInterval:()=>0};
  win.window=win;vm.runInNewContext(src,Object.assign(win,{JSON,Array,Uint8Array,Object}));
  return {nodes,sent,win,reply:o=>win.PreceptorNodeNative.onmessage({data:JSON.stringify(o)})};
}
test("one state, three readings: sentence, data-* and JSON agree",()=>{
  const p=page();
  assert.equal(p.sent[0].action,"status");
  p.reply({id:p.sent[0].id,state:"MEASURED",step:"building_raised",cause:"one_node_one_building",node:"nodo.3.tank-3",alias:"tank-3",building:"casa-tank-3"});
  const s=p.nodes["native-node-status"],j=JSON.parse(p.nodes["native-node-json"].textContent);
  assert.equal(s.dataset.state,j.state);assert.equal(s.dataset.cause,j.cause);assert.equal(s.dataset.step,j.step);
  assert.match(s.textContent,/casa-tank-3/);assert.equal(j.building,"casa-tank-3");
  assert.equal(s.attrs.role,"status");assert.equal(s.attrs["aria-live"],"polite");
  assert.equal(p.nodes["native-node-create"].disabled,true);assert.equal(p.nodes["native-node-build"].disabled,true);
});
test("suggested alias fills the identity; create carries explicit consent",()=>{
  const p=page();
  p.reply({id:p.sent[0].id,state:"NO_DATA",step:"no_identity",cause:"node_not_created",suggested_alias:"tank-3"});
  assert.equal(p.nodes["native-node-id"].value,"nodo.3.tank-3");
  p.nodes["native-node-create"].listeners.click();
  const c=p.sent.at(-1);assert.equal(c.action,"create");assert.equal(c.consent,true);assert.equal(c.alias,"tank-3");
});
test("unknown states and causes fall to NO_DATA, never to a claim",()=>{
  const p=page();
  p.reply({id:p.sent[0].id,state:"LIVE",step:"hack",cause:"<b>x</b>"});
  const s=p.nodes["native-node-status"];
  assert.equal(s.dataset.state,"NO_DATA");assert.equal(s.dataset.cause,"native_reply_invalid");assert.equal(s.dataset.step,"no_identity");
});
