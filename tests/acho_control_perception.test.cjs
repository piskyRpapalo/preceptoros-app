// Directed fixture test: no browser/device/network claims.
const fs=require("node:fs");
const path=require("node:path");
const root=path.resolve(__dirname,"..");
const read=p=>fs.readFileSync(path.join(root,p),"utf8");
function runFixtures(source,html,owner,sw,Encoder,gate){
  const catalog=JSON.parse(source.match(/const controlCatalog = ([\s\S]*?\n  \]);/)[1]);
  const byId=new Map(),listeners={},spoken=[];
  let max=0, checks=0;
  function check(ok,msg){if(!ok)throw Error(msg);checks++;}
  const mk=(row,extra={})=>({tagName:row[2]==="disclosure"?"SUMMARY":row[2]==="select"?"SELECT":"BUTTON",
    id:row[4]?row[0]:"",textContent:row[1],parentElement:null,hidden:false,inert:false,open:false,
    attrs:row[4]?{}:{"data-acho-control":row[0]},
    getAttribute(k){return this.attrs[k]??null;},hasAttribute(k){return k in this.attrs;},
    setAttribute(k,v){this.attrs[k]=v;},matches(){return false;},
    closest(q){return q==="button,summary,select"?this:null;},addEventListener(){},...extra});
  for(const row of catalog)byId.set(row[0],mk(row));
  const doc={readyState:"loading",getElementById:id=>byId.get(id)||null,
    querySelector:s=>byId.get(s.match(/"([^"]+)"/)?.[1])||null,
    activeElement:null,addEventListener:(k,v)=>{listeners[k]=v;}};
  const root={document:doc,TextEncoder:Encoder,
    localStorage:{getItem:()=>null,setItem(){}},
    speechSynthesis:{speak:u=>spoken.push(u.text),cancel(){}},
    SpeechSynthesisUtterance:function(s){this.text=s;}};
  const m={exports:{}};
  new Function("window","module",source)(root,m);
  const api=m.exports,reader=api.controls;
  check(catalog.length===148,"catalog size");
  check(new Set(reader.ids()).size===148,"unique stable ids");
  check(catalog.every(row=>(row[0].startsWith("owner-")?owner:html).includes((row[4]?'id="':'data-acho-control="')+row[0]+'"')),"all mounts sourced");
  check(html.includes('/audio_accessibility.js?v=2')&&sw.includes('/audio_accessibility.js?v=2'),"asset alignment");
  for(const row of catalog){
    const p=reader.read(row[0]);
    const items=p.frame?.atoms?.[0]?.i||[],cv=p.frame?.cv||[];
    const visual=items.map(item=>item.tx).join(" ");
    const geometry=items.length>0&&items.length<=4&&items.every(item=>{
      const width=0.6*item.sz*item.tx.length;
      return item.o==="text"&&item.x-width/2>=0&&item.x+width/2<=cv[0]&&
        item.y-item.sz*0.7>=0&&item.y+item.sz*0.7<=cv[1];
    });
    check(!!p.frame&&p.frame.v==="preceptoros.acho/1"&&cv[0]===390&&cv[1]===96&&
      p.frame.atoms[0].r===p.text&&visual===p.text&&geometry&&
      p.frame_bytes===new Encoder().encode(JSON.stringify(p.frame)).length&&p.frame_bytes<1024&&
      p.freshness==="LOCAL_DOM_SNAPSHOT"&&Number.isFinite(Date.parse(p.observed_at))&&
      p.authorization==="NOT_GRANTED_BY_READ"&&p.frame.sound==="NO_DATA"&&p.frame.seal!=="LIVE","frame "+row[0]);
    if(gate)check(gate(p.frame).ok,"WEB gate "+row[0]);
    max=Math.max(max,p.frame_bytes);
  }
  const get=id=>byId.get(id);
  get("hitl-si").matches=q=>q===":disabled";
  check(reader.read("hitl-si").availability==="DISABLED","disabled");
  check(reader.read("hitl-si").requirement.includes("owner approval"),"signature gate");
  get("hitl-si").hidden=true;
  check(reader.read("hitl-si").availability==="HIDDEN"&&reader.read("hitl-si").disabled,"hidden and disabled");
  get("modelos-toggle").attrs["aria-expanded"]="true";
  check(reader.read("modelos-toggle").state.includes("expanded=true"),"expanded state");
  get("tab-lab").attrs["aria-selected"]="true";
  check(reader.read("tab-lab").state.includes("selected=true"),"selected state");
  const summary=mk(["summary-fixture","Agents","disclosure","local UI",true]);
  const detail=mk(["details-fixture","Details","disclosure","local UI",true],{tagName:"DETAILS",children:[summary]});
  summary.contains=e=>e===summary;
  get("mini-local-toggle").parentElement=detail;
  check(reader.read("mini-local-toggle").availability==="HIDDEN","closed details");
  detail.open=true;
  check(reader.read("mini-local-toggle").availability==="VISIBLE","open details");
  get("modelos-toggle").textContent="PRIVATE_VALUE_SENTINEL";
  check(!JSON.stringify(reader.read("modelos-toggle")).includes("PRIVATE_VALUE_SENTINEL"),"no dynamic label leakage");
  const dynamic=reader.read("modelos-toggle");
  check(dynamic.accessible_name===null&&dynamic.frame.seal==="NO_DATA","dynamic name NO_DATA");
  check(reader.read("__proto__").state==="NO_DATA","unknown id");
  byId.delete("owner-public-runtime");
  check(reader.read("owner-public-runtime").cause==="control_mount_missing","unmounted dynamic selector");
  const desc=mk(["acho-control-description","","activate","",true]);byId.set(desc.id,desc);
  doc.activeElement=get("tab-lab");
  const p=reader.focused();
  check(p.id==="tab-lab","focus lookup");
  api.readFocused();
  check(desc.textContent===p.text&&spoken.length===0,"visual same; sound off");
  api.setEnabled(true);
  api.readFocused();
  check(spoken.length===1&&spoken[0]===desc.textContent&&spoken[0]===p.text,"explicit speech text parity");
  check(desc.attrs["aria-live"]==="off","avoid duplicate live announcement when speech requested");
  check(reader.read("settings-speech-rate").function==="select","speech selector");
  check(reader.read("owner-private-runtime").function==="select","private model selector");
  return {controls:catalog.length,checks,maxFrame:max,webGate:!!gate};
}
console.log(JSON.stringify(runFixtures(read("interface/audio_accessibility.js"),read("interface/app.html"),read("interface/owner_model_slots.js"),read("interface/sw.js"),TextEncoder,null)));
