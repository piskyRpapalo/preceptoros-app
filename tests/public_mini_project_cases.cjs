'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const guide=require('../interface/mini_project_guide.js');
const companion=require('../interface/companion_onboarding.js');
const slots=require('../interface/owner_model_slots.js');
function store(){const map=new Map();return {getItem:key=>map.get(key)||null,
 setItem:(key,value)=>map.set(key,value),removeItem:key=>map.delete(key)};}
const project={title:'My Climate Lab',purpose:'Study measurements that I provide',
 description:'This is a reproducible, locally stored analysis of climate observations.',template:'custom'};
const docs={loadDocuments:()=>[{id:'x',title:'Observations',content:'Station A: 10.2',
 state:'saved',modified:'2026-11-18T00:00:00Z'}]};
test('owner creates valid local project without model or network',()=>{
 const storage=store();const result=guide.save(storage,project,companion);
 assert.equal(result.ok,true);
 const read=guide.load(storage,companion);
 assert.equal(read.ok,true);
 assert.equal(read.value.title,project.title);
 assert.equal(read.value.state,'DRAFT_ONLY');
 assert.equal(read.value.deployment,'NOT_SUBMITTED');
 assert.ok(!Object.hasOwn(read.value,'signature'));
});
test('missing title/purpose/description and long fields rejected',()=>{
 for(const patch of [{title:''},{purpose:''},{description:''},
  {title:'A'.repeat(81)},{purpose:'x'.repeat(601)},{description:'x'.repeat(3001)}]){
   const c=guide.validate({...project,...patch},companion);
   assert.equal(c.ok,false,JSON.stringify(patch).slice(0,80));
 }
});
test('Companion validation rejects secrets and non-portable slugs',()=>{
 for(const patch of [
  {title:'🔑'}, {title:'My API_KEY=secret'}, {purpose:'password for my account'},
  {description:'token: extremely-sensitive-claim'}
 ])assert.equal(guide.validate({...project,...patch},companion).ok,false);
});
test('two editable examples have versioned official primary source links',()=>{
 for(const key of ['law','fairness']){
  const t=guide.templates[key];
  assert.ok(t.title && t.purpose && t.description);
  assert.ok(t.sources.length>0);
  for(const src of t.sources){
   assert.match(src.url,/^https:\/\/eur-lex\.europa\.eu\//);
   assert.match(src.version,/^\d{4}-\d\d-\d\d$/);
  }
  assert.equal(guide.validate({...t,template:key},companion).ok,true);
 }
});
test('documents count excludes invalid or unsaved rows',()=>{
 const d=guide.documents({loadDocuments:()=>[
  ...docs.loadDocuments(),
  {id:'bad',title:'File',content:'bad',state:'draft'},
  {id:'xss',title:'x'.repeat(81),content:'test',state:'saved'}]});
 assert.equal(d.count,1);
 assert.equal(d.cause,'invalid_documents_excluded');
});
test('no selected model means DETERMINISTIC_ONLY; saved label means configured only',()=>{
 const s=store();
 assert.equal(guide.modelState(slots,s).state,'DETERMINISTIC_ONLY');
 const value={private_chat_model:{runtime:'owner_managed',label:'My Server'},
  public_visitor_model:{runtime:'none',label:''}};
 assert.equal(slots.save(s,value).ok,true);
 const m=guide.modelState(slots,s);
 assert.equal(m.state,'MODEL_CONFIGURED');
 assert.equal(m.cause,'no_verified_model_turn');
 const invalidTurn={source:'owner_runtime_turn',answer:'NO_DATA(cannot_connect)',
  runtimeObserved:true,ownerConsent:true};
 assert.equal(guide.modelState(slots,s,invalidTurn).state,'MODEL_CONFIGURED');
});
test('only actual consented owner runtime reply can count as MODEL_VERIFIED in this pure projector',()=>{
 const s=store();
 slots.save(s,{private_chat_model:{runtime:'on_device',label:'My local runtime'},
  public_visitor_model:{runtime:'none',label:''}});
 assert.equal(guide.modelState(slots,s,{answer:'Test',ownerConsent:false,runtimeObserved:true,
  source:'owner_runtime_turn'}).state,'MODEL_CONFIGURED');
 assert.equal(guide.modelState(slots,s,{answer:'A real response',ownerConsent:true,
  runtimeObserved:true,source:'owner_runtime_turn'}).state,'MODEL_VERIFIED');
 // The public browser currently has no runtime producing this proof.
});
test('FAQ uses local source identifiers and refuses unsupported generation',()=>{
 const questions=[['where are my documents','interface/documents.js'],
 ['do I have a model','interface/owner_model_slots.js'],
 ['where is My node','interface/node_registration.js'],
 ['what can you do','preceptoros.mini-project/1']];
 for(const [q,source] of questions){
  const a=guide.answer(q,project,{count:1}, {state:'DETERMINISTIC_ONLY',cause:'none'});
  assert.ok(a.source.includes(source),q);
 }
 const unknown=guide.answer('quantum entanglement from first principles',null,{count:0},{state:'DETERMINISTIC_ONLY'});
 assert.equal(unknown.state,'NO_DATA');
});
test('export is explicit, local, includes owner documents and never a model weight or grant',()=>{
 const s=store();guide.save(s,project,companion);
 const result=guide.exportBundle(guide.load(s,companion).value,docs);
 assert.equal(result.ok,true);
 const bundle=JSON.parse(result.content);
 assert.equal(bundle.documents.length,1);
 assert.equal(bundle.sent,false);
 assert.equal(bundle.model_weights_included,false);
 assert.ok(!Object.hasOwn(bundle,'credential'));
});
test('unavailable browser storage cannot produce false saved state',()=>{
 const denied={getItem(){throw Error('denied')},setItem(){throw Error('denied')}};
 assert.equal(guide.load(denied,companion).ok,false);
 assert.equal(guide.save(denied,project,companion).cause,'owner_storage_unavailable');
});
test('six-step tutorial requires project, validated docs, explicit review and node visit',()=>{
 const m={state:'DETERMINISTIC_ONLY'};
 const empty=guide.progress(null,{count:0},m,false,false);
 assert.equal(empty.length,6);assert.equal(empty[0].complete,false);
 const full=guide.progress(project,{count:1},m,true,true);
 assert.ok(full.every(s=>s.complete));
 assert.deepEqual(full.map(x=>x.step),guide.steps);
});
test('real Documents module persists saved state and rejects oversized import content',()=>{
 const previous=global.localStorage;
 const s=store();
 global.localStorage=s;
 try{
  const mod=require('../interface/documents.js');
  const created=mod.createDocument('A public source','Verified by owner');
  assert.equal(created.state,'saved');
  assert.equal(mod.getDocument(created.id).state,'saved');
  const updated=mod.updateDocument(created.id,'A public source','Updated locally');
  assert.equal(updated.state,'saved');
  assert.equal(mod.getDocument(created.id).content,'Updated locally');
  const invalid=mod.createDocument('Too large','x'.repeat(100001));
  assert.equal(invalid._validationError,'invalid_document_size_or_title');
  assert.equal(mod.loadDocuments().length,1);
 }finally{global.localStorage=previous;}
});
