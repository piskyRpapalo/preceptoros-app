'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const flow = require('../interface/node_registration.js');
const S = flow.deploymentStates;
const draft = () => flow.deploymentDraft('nodo.42.contributor', 'Public benchmark participation');
test('offline draft has no credential, signing grant or network', () => {
 const d=draft();
 assert.equal(d.state,S.draft);
 for(const x of ['firma_ssh','plan_sha256','grant','rack_url'])assert.equal(Object.hasOwn(d,x),false);
});
test('bad canonical node and empty/oversized purpose fail closed',()=>{
 for(const n of ['../../rack','nodo.X.bad','nodo.42.BAD'])assert.throws(()=>flow.deploymentDraft(n,'a'),/invalid_node_name/);
 assert.throws(()=>flow.deploymentDraft('nodo.42.good',''),/invalid_deployment_purpose/);
 assert.throws(()=>flow.deploymentDraft('nodo.42.good','x'.repeat(513)),/invalid_deployment_purpose/);
});
test('denied consent has zero native traffic',async()=>{
 let calls=0;const native={requestPreliminary:async()=>{calls++;return {};}};
 await assert.rejects(flow.requestDeploymentReview(draft(),false,native),/explicit_consent_required/);
 assert.equal(calls,0);
});
test('missing native bridge never falls back to browser fetch',async()=>{
 await assert.rejects(flow.requestDeploymentReview(draft(),true,null),/native_preliminary_request_not_available/);
});
test('synthetic confirmed REQUESTED gives tracking, never approval or LIVE',async()=>{
 const d=draft();let calls=0;
 const native={requestPreliminary:async p=>{
   calls++;assert.deepEqual(p,{node:d.node,purpose:d.purpose,consent:true});
   return {contractVerified:true,preliminaryReceiptValidated:true,state:'REQUESTED',
     trackingId:'request.synthetic-0001',node:d.node};
 }};
 const o=await flow.requestDeploymentReview(d,true,native);
 assert.equal(calls,1);assert.equal(o.state,S.requested);
 assert.equal(o.trackingId,'request.synthetic-0001');
 assert.equal(o.approved,false);assert.equal(o.live,false);
});
test('idempotent synthetic replay is PENDING, not LIVE',async()=>{
 const d=draft();const native={requestPreliminary:async()=>({contractVerified:true,preliminaryReceiptValidated:true,
   state:'PENDING',trackingId:'request.synthetic-0001',node:d.node})};
 const a=await flow.requestDeploymentReview(d,true,native),b=await flow.requestDeploymentReview(d,true,native);
 assert.equal(a.trackingId,b.trackingId);assert.equal(b.state,S.pending);assert.equal(b.live,false);
});
test('HTTP 200 alone, fabricated approval, wrong node or bad tracking fail closed',async()=>{
 const d=draft();
 const cases=[
  {status:200,state:'REQUESTED',trackingId:'request.synthetic-0001',node:d.node},
  {contractVerified:true,state:'REQUESTED',trackingId:'request.synthetic-0001',node:d.node},
  {contractVerified:false,preliminaryReceiptValidated:true,state:'REQUESTED',trackingId:'request.synthetic-0001',node:d.node},
  {contractVerified:true,preliminaryReceiptValidated:true,state:'APPROVED',trackingId:'request.synthetic-0001',node:d.node},
  {contractVerified:true,preliminaryReceiptValidated:true,state:'LIVE',trackingId:'request.synthetic-0001',node:d.node},
  {contractVerified:true,preliminaryReceiptValidated:true,state:'PENDING',trackingId:'request.synthetic-0001',node:'nodo.99.other'},
  {contractVerified:true,preliminaryReceiptValidated:true,state:'REQUESTED',trackingId:'bad',node:d.node}
 ];
 for(const out of cases)await assert.rejects(flow.requestDeploymentReview(d,true,{requestPreliminary:async()=>out}));
});
test('approval is a separate signed/adjudicated proof, rejection requires operator proof',()=>{
 assert.equal(flow.deploymentEvidence(S.approved,{preliminaryReceiptValidated:true}),S.unknown);
 assert.equal(flow.deploymentEvidence(S.approved,{operatorDecisionVerified:true,signedAdmissionVerified:true}),S.approved);
 assert.equal(flow.deploymentEvidence(S.rejected,{operatorDecisionVerified:true}),S.unknown);
 assert.equal(flow.deploymentEvidence(S.rejected,{operatorDecisionVerified:true,preliminaryReceiptValidated:true}),S.rejected);
});
test('LIVE requires four independent proof gates',()=>{
 const e={operatorDecisionVerified:true,signedAdmissionVerified:true,heartbeatFreshVerified:true,publicWorldVisible:true};
 for(const k of Object.keys(e))assert.equal(flow.deploymentEvidence(S.live,{...e,[k]:false}),S.unknown,k);
 assert.equal(flow.deploymentEvidence(S.live,e),S.live);
});
test('native refusal or offline never produces fake acknowledgement',async()=>{
 for(const cause of ['offline','owner_denied'])await assert.rejects(
   flow.requestDeploymentReview(draft(),true,{requestPreliminary:async()=>{throw Error(cause);}}),
   new RegExp(cause));
});
function fakeDom(){
 const ids=['node-registration-form','node-registration-name','node-registration-purpose',
  'node-registration-status','node-registration-preview','node-registration-signer',
  'node-registration-consent','node-registration-submit'];
 function element(id){return {id,textContent:'',value:'',checked:false,disabled:false,attrs:{},listeners:{},
  addEventListener(t,fn){this.listeners[t]=fn;},
  fire(t){assert.ok(this.listeners[t],id+':'+t);return this.listeners[t]({preventDefault(){}});},
  setAttribute(n,v){this.attrs[n]=String(v);},removeAttribute(n){delete this.attrs[n];}};}
 const nodes=Object.fromEntries(ids.map(id=>[id,element(id)]));const translated={};
 const doc={getElementById:id=>nodes[id],querySelector:sel=>{
   const match=sel.match(/^\[data-i18n="([^"]+)"\]$/);
   return match ? (translated[match[1]] ||= element(match[1])) : null;
 }};
 return {nodes,doc};
}
test('UI stays in existing My node and announces same state eye/ear/machine',async()=>{
 const {nodes,doc}=fakeDom();flow.mount(doc);
 const s=nodes['node-registration-status'];
 assert.equal(s.attrs['data-state'],S.draft);assert.equal(s.attrs['data-acho'],S.draft);
 nodes['node-registration-name'].value='nodo.42.contributor';
 nodes['node-registration-purpose'].value='Public benchmark participation';
 await nodes['node-registration-form'].fire('submit');
 assert.equal(s.attrs['data-state'],S.draft);
 assert.equal(nodes['node-registration-submit'].disabled,true);
 nodes['node-registration-consent'].checked=true;
 await nodes['node-registration-consent'].fire('change');
 assert.equal(nodes['node-registration-submit'].disabled,false);
 await nodes['node-registration-submit'].fire('click');
 assert.equal(s.attrs['data-state'],S.unknown);assert.equal(s.attrs['data-acho'],S.unknown);
 assert.match(s.textContent,/native_preliminary_request_not_available/);
});
test('changing draft revokes consent and requires preview again',async()=>{
 const {nodes,doc}=fakeDom();flow.mount(doc);
 nodes['node-registration-name'].value='nodo.42.contributor';nodes['node-registration-purpose'].value='Study';
 await nodes['node-registration-form'].fire('submit');
 nodes['node-registration-consent'].checked=true;await nodes['node-registration-consent'].fire('change');
 assert.equal(nodes['node-registration-submit'].disabled,false);
 await nodes['node-registration-purpose'].fire('input');
 assert.equal(nodes['node-registration-consent'].checked,false);
 assert.equal(nodes['node-registration-submit'].disabled,true);
});
