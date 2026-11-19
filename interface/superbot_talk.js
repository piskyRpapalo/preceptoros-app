/* PreceptorOS Superbot Talk rail · plan agent references, NOT verified agent roster.
 * Uses the existing Plan.project flow; no new authority, no dispatch, no endpoints.
 * A swarm becomes agent tabs only when its source contains distinct agent refs. */
(function (root) {
  "use strict";
  const doc=root.document;
  const $=id=>doc?.getElementById(id);
  const clean=(v,n=100)=>typeof v==="string"?v.replace(/[\u0000-\u001f\u007f<>]/g," ").trim().slice(0,n):"";
  const safeId=id=>typeof id==="string"&&id.length>0&&id.length<=40&&/^[a-z0-9_.-]+$/i.test(id);
  let agents=[], selected=null, lastSignature="";
  const number=n=>String(n).padStart(2,"0");
  function state(kind,cause){
    const line=$("superbot-agent-count"),box=$("superbot-agent-disclosure");
    if(!line||!box)return;
    box.dataset.state=kind;box.dataset.cause=cause;box.dataset.acho=kind==="NO_DATA"?"silent":kind==="SYNTHETIC"?"synthetic":"proposed";
  }
  function select(id,focus=false){
    const agent=agents.find(a=>a.id===id);
    if(!agent)return;
    selected=id;
    const tabs=$("superbot-agent-tabs"),detail=$("superbot-agent-detail");
    if(!tabs||!detail)return;
    for(const b of tabs.querySelectorAll('[role="tab"]')){
      const is=b.dataset.agentId===id;b.setAttribute("aria-selected",String(is));b.tabIndex=is?0:-1;
      if(focus&&is)b.focus();
    }
    detail.replaceChildren();
    const title=doc.createElement("h4");title.textContent=agent.id;
    const role=doc.createElement("p");role.textContent="Functions: "+(agent.roles.join(", ")||"NO_DATA(no_capability_declared)")+".";
    const tasks=doc.createElement("ul");
    for(const item of agent.tasks){
      const li=doc.createElement("li");
      li.textContent=clean(item.title,140)+" · "+clean(item.stage,24)+" · "+clean(item.cause,120);
      tasks.append(li);
    }
    const note=doc.createElement("p");note.textContent="Plan references are not proof of an installed, authorized or running agent. No action can be started here.";
    detail.append(title,role,tasks,note);detail.dataset.agentId=id;detail.dataset.state=agent.synthetic?"SYNTHETIC":"PLAN_REFERENCE";
  }
  function render(p){
    const heading=$("superbot-orchestrator"),label=$("superbot-agent-count"),list=$("superbot-agent-tabs"),
      names=$("superbot-agent-names"),detail=$("superbot-agent-detail"),hint=$("superbot-agent-hint");
    if(!heading||!label||!list||!detail||!names)return {state:"NO_DATA",cause:"missing_mount"};
    if(!p||p.state!=="shown"||!Array.isArray(p.tasks)){
      heading.textContent="Mini Orchestrator · local mode";
      label.textContent="Agents · not connected";
      names.textContent="Not connected";
      hint.textContent="Connect your orchestrator or create a plan to see referenced agents here.";
      list.replaceChildren();detail.replaceChildren();detail.hidden=true;agents=[];selected=null;lastSignature="";
      state("NO_DATA",clean(p?.cause,80)||"agent_roster_not_connected");
      return {state:"NO_DATA",cause:"agent_roster_not_connected",count:null};
    }
    const map=new Map();
    for(const t of p.tasks.slice(0,24)){
      const id=clean(t.agent,40);
      if(!safeId(id))continue;
      if(!map.has(id))map.set(id,{id,roles:[],tasks:[],synthetic:p.synthetic===true});
      const a=map.get(id),cap=clean(t.capability,48);
      if(cap&&!a.roles.includes(cap))a.roles.push(cap);
      a.tasks.push({title:t.title,stage:t.stage,cause:t.cause});
    }
    const sorted=[...map.values()].sort((a,b)=>a.id.localeCompare(b.id));
    const signature=JSON.stringify({plan:p.plan?.sha,synthetic:p.synthetic,agents:sorted});
    heading.textContent=(p.synthetic?"SYNTHETIC · ":"")+"Plan coordinator: "+(clean(p.orchestrator,60)||"not verified");
    label.textContent=number(sorted.length)+" agents referenced in plan"+(p.synthetic?" · SYNTHETIC":"");
    names.textContent=sorted.map(a=>a.id).join(" · ");
    hint.textContent=sorted.length?"These are task references, not an authenticated agent registry. Select an agent to inspect its declared functions.":"No agents are referenced in this plan.";
    state(p.synthetic?"SYNTHETIC":"PLAN_REFERENCE",p.synthetic?"synthetic_fixture":"agent_cards_not_verified");
    if(signature===lastSignature)return {state:p.synthetic?"SYNTHETIC":"PLAN_REFERENCE",count:sorted.length};
    lastSignature=signature;agents=sorted;
    list.replaceChildren();
    for(let i=0;i<agents.length;i++){
      const a=agents[i],button=doc.createElement("button");
      button.type="button";button.className="superbot-agent-tab";button.setAttribute("role","tab");
      button.dataset.agentId=a.id;button.setAttribute("aria-controls","superbot-agent-detail");
      button.setAttribute("aria-selected","false");button.tabIndex=-1;
      button.textContent=a.id;
      button.addEventListener("click",()=>select(a.id));
      button.addEventListener("keydown",e=>{
        if(!["ArrowRight","ArrowLeft","Home","End"].includes(e.key))return;
        e.preventDefault();
        const index=agents.findIndex(x=>x.id===a.id);
        const next=e.key==="Home"?0:e.key==="End"?agents.length-1:
          (index+(e.key==="ArrowRight"?1:-1)+agents.length)%agents.length;
        select(agents[next].id,true);
      });
      list.append(button);
    }
    detail.hidden=!agents.length;
    if(agents.length)select(agents.some(a=>a.id===selected)?selected:agents[0].id);
    return {state:p.synthetic?"SYNTHETIC":"PLAN_REFERENCE",count:agents.length};
  }
  root.PreceptorSuperbotTalk=Object.freeze({fromPlan:render});
  if(typeof module==="object"&&module.exports)module.exports=root.PreceptorSuperbotTalk;
})(typeof window==="object"?window:globalThis);
