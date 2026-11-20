'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {webcrypto}=require('node:crypto');
const recovery=require('../interface/mini_recovery.js');
const guide=require('../interface/mini_project_guide.js');
const companion=require('../interface/companion_onboarding.js');
function store(){
 const map=new Map();
 return {getItem:k=>map.has(k)?map.get(k):null,setItem:(k,v)=>map.set(k,v),
 removeItem:k=>map.delete(k), map};
}
const deps={guide,companion,crypto:webcrypto};
const sourceProject={
 title:'My previous Mini',purpose:'Explore owner-approved offline measurements',
 description:'My previous Mini created from local project sources.',template:'custom'
};
function exportPrevious(patch, docs=[{title:'Measurements',content:'Owner provided lab note',modified:null}]){
 const source=store();
 const result=guide.save(source,{...sourceProject,...patch},companion);
 assert.equal(result.ok,true);
 const bundle=guide.exportBundle(guide.load(source,companion).value,
    {loadDocuments:()=>docs.map(d=>({...d,state:'saved'}))});
 assert.equal(bundle.ok,true);
 return JSON.parse(bundle.content);
}
const raw=(patch,docs)=>JSON.stringify(exportPrevious(patch,docs));
test('existing Mini export preview uses exact source schema, does not save or authorize',async()=>{
 const state=store();const packet=raw();
 const p=await recovery.prepare(packet,deps);
 assert.equal(p.ok,true);assert.equal(p.state,'DRAFT_ONLY');
 assert.match(p.fingerprint,/^[a-f0-9]{64}$/);
 assert.equal(p.ownership,'NO_DATA(no_signed_owner_proof)');
 assert.equal(p.authority,'NONE');
 assert.equal(state.map.size,0);
});
test('stable fingerprint independent of JSON formatting and key order',async()=>{
 const pack=exportPrevious();
 const first=await recovery.prepare(JSON.stringify(pack),deps);
 const reversed=Object.fromEntries(Object.entries(pack).reverse());
 const second=await recovery.prepare(JSON.stringify(reversed,null,2),deps);
 assert.equal(first.fingerprint,second.fingerprint);
});
test('full explicit consent is needed; false and missing do not write',async()=>{
 const state=store();
 for(const consent of [false,null,undefined,'true',1]){
  const r=await recovery.apply(raw(),consent,state,deps);
  assert.equal(r.ok,false);assert.equal(r.cause,'explicit_owner_consent_required');
 }
 assert.equal(state.map.size,0);
});
test('import restores same local project, documents, and fingerprint after restart',async()=>{
 const state=store();const packet=raw();
 const result=await recovery.apply(packet,true,state,deps);
 assert.equal(result.ok,true);assert.equal(result.state,'UNVERIFIED_LOCAL');
 assert.equal(result.changed,true);assert.equal(result.authority,'NONE');
 const importedProject=guide.load(state,companion);
 assert.equal(importedProject.ok,true);
 assert.equal(importedProject.value.title,'My previous Mini');
 const docs=JSON.parse(state.getItem('preceptoros.documents.v1'));
 assert.equal(docs.length,1);assert.equal(docs[0].state,'saved');
 const second=recovery.read(state);
 assert.equal(second.ok,true);
 assert.equal(second.fingerprint,result.fingerprint);
 assert.equal(second.ownerProof,'NO_DATA(no_signed_owner_proof)');
 assert.equal(second.authority,'NONE');
});
test('repeated import has stable fingerprint and never duplicates documents',async()=>{
 const state=store();const packet=raw();
 const first=await recovery.apply(packet,true,state,deps);
 const before=JSON.stringify([...state.map.entries()]);
 const again=await recovery.apply(packet,true,state,deps);
 assert.equal(again.alreadyRecovered,true);
 assert.equal(again.fingerprint,first.fingerprint);
 assert.equal(JSON.stringify([...state.map.entries()]),before);
 assert.equal(JSON.parse(state.getItem('preceptoros.documents.v1')).length,1);
});
test('wrong source, fake owner credential, signed or LIVE claim all fail closed',async()=>{
 const fake=[
  {schema:'other'},
  {declared_by:'node_issuer'},
  {sent:true},
  {model_weights_included:true},
  {authority:'SIGNED'},
  {private_key:'secret'},
  {project:{...exportPrevious().project,owner:'sovereign'}},
  {project:{...exportPrevious().project,deployment:'LIVE'}}
 ];
 for(const patch of fake){
  const p=exportPrevious();
  Object.assign(p,patch);
  const state=store();
  const res=await recovery.apply(JSON.stringify(p),true,state,deps);
  assert.equal(res.ok,false,JSON.stringify(patch));
  assert.equal(state.map.size,0);
 }
});
test('tampered slug or authoritative source links cannot substitute a Mini identity',async()=>{
 for(const modify of [
   packet=>packet.project.slug='matching-name-wrong-slug',
   packet=>packet.source_links=[{title:'Foreign',url:'https://example.invalid',version:'0'}],
   packet=>packet.project.id='owner-claimed-id'
 ]){
   const packet=exportPrevious();modify(packet);
   const state=store();
   const outcome=await recovery.apply(JSON.stringify(packet),true,state,deps);
   assert.equal(outcome.ok,false);
   assert.equal(state.map.size,0);
 }
});
test('mutated payload and title collision cannot silently take over previous Mini',async()=>{
 const state=store();const original=raw();
 const first=await recovery.apply(original,true,state,deps);
 const changed=raw({description:'This is a different project with same title.'});
 const second=await recovery.apply(changed,true,state,deps);
 assert.equal(second.ok,false);assert.equal(second.cause,'different_existing_recovery_refused');
 assert.equal(recovery.read(state).fingerprint,first.fingerprint);
});
test('already existing different owner project cannot be overwritten',async()=>{
 const state=store();
 guide.save(state,{...sourceProject,title:'Existing different project'},companion);
 const before=state.getItem('preceptoros.public-mini.project.v1');
 const out=await recovery.apply(raw(),true,state,deps);
 assert.equal(out.ok,false);assert.equal(out.cause,'existing_project_conflict');
 assert.equal(state.getItem('preceptoros.public-mini.project.v1'),before);
 assert.equal(state.getItem(recovery.recordSchema),null);
});
test('same filename but different document text conflicts rather than replacing',async()=>{
 const state=store();
 state.setItem('preceptoros.documents.v1',
 JSON.stringify([{id:'existing',title:'Measurements',content:'different original',state:'saved',created:'x',modified:'x'}]));
 const snapshot=state.getItem('preceptoros.documents.v1');
 const out=await recovery.apply(raw(),true,state,deps);
 assert.equal(out.ok,false);assert.equal(out.cause,'document_title_conflict');
 assert.equal(state.getItem('preceptoros.documents.v1'),snapshot);
});
test('quota failure rolls back previous project and document data',async()=>{
 const state=store();const original=state.setItem.bind(state);
 let failed=false;
 state.setItem=(k,v)=>{
  if(k==='preceptoros.documents.v1'&&!failed){failed=true;throw Error('quota');}
  original(k,v);
 };
 const out=await recovery.apply(raw(),true,state,deps);
 assert.equal(out.ok,false);assert.equal(out.cause,'owner_storage_write_failed');
 assert.equal(state.map.size,0);
});
test('corrupt or fabricated local receipt not accepted as signed identity',async()=>{
 const state=store();
 state.setItem(recovery.recordSchema,JSON.stringify({
  schema:recovery.recordSchema,state:'LIVE',fingerprint:'a'.repeat(64),
  title:'forged',documents:0,authority:'SIGNED',ownerProof:'APPROVED'
 }));
 assert.equal(recovery.read(state).ok,false);
 assert.equal((await recovery.apply(raw(),true,state,deps)).cause,'existing_recovery_unreadable');
});
test('input bound measured in UTF-8 bytes and parse errors have no effect',async()=>{
 const state=store();
 for(const text of ['','{oops','🦀'.repeat(70000)]){
  const r=await recovery.apply(text,true,state,deps);
  assert.equal(r.ok,false);
 }
 assert.equal(state.map.size,0);
});
test('oversized document data and unsupported documents rejected, no side effects',async()=>{
 const state=store();
 for(const doc of [{title:'T',content:'x'.repeat(100001)},{title:'A'.repeat(82),content:'x'}]){
  const packet=exportPrevious();
  packet.documents=[doc];
  const out=await recovery.apply(JSON.stringify(packet),true,state,deps);
  assert.equal(out.ok,false);
 }
 assert.equal(state.map.size,0);
});
test('no network or remote permissions are granted in this importer',async()=>{
 const old=global.fetch;let contacted=false;
 global.fetch=()=>{contacted=true;throw Error('forbidden');};
 try{
  const result=await recovery.apply(raw(),true,store(),deps);
  assert.equal(result.ok,true);
  assert.equal(contacted,false);assert.equal(result.authority,'NONE');
 }finally{global.fetch=old;}
});
test('sabotage: editing one byte changes the fingerprint; name alone is not identity',async()=>{
 const a=await recovery.prepare(raw(),deps);
 const b=await recovery.prepare(raw({description:'Different content, identical name'}),deps);
 assert.notEqual(a.fingerprint,b.fingerprint);
 assert.equal(a.project.title,b.project.title);
});

// Faro/C regression: a stale receipt must not certify changed local project bytes.
test('Faro sabotage: a mutated recovered project is not already recovered',async()=>{
 const state=store(), packet=raw();
 const initial=await recovery.apply(packet,true,state,deps);
 assert.equal(initial.ok,true);
 for(const field of ['title','purpose','description','slug']){
  const original=JSON.parse(state.getItem('preceptoros.public-mini.project.v1'));
  const tampered={...original,[field]:original[field]+'-locally-edited'};
  state.setItem('preceptoros.public-mini.project.v1',JSON.stringify(tampered));
  const recordBefore=state.getItem(recovery.recordSchema);
  const documentsBefore=state.getItem('preceptoros.documents.v1');
  const result=recovery.read(state);
  assert.equal(result.ok,false,field);
  assert.equal(result.cause,'recovered_project_changed',field);
  const repeated=await recovery.apply(packet,true,state,deps);
  assert.equal(repeated.ok,false,field);
  assert.equal(repeated.cause,'recovered_project_changed',field);
  assert.equal(state.getItem('preceptoros.public-mini.project.v1'),JSON.stringify(tampered));
  assert.equal(state.getItem('preceptoros.documents.v1'),documentsBefore);
  assert.equal(state.getItem(recovery.recordSchema),recordBefore);
  state.setItem('preceptoros.public-mini.project.v1',JSON.stringify(original));
 }
 assert.equal(recovery.read(state).ok,true);
 assert.equal((await recovery.apply(packet,true,state,deps)).alreadyRecovered,true);
});
test('old receipt is migrated only after consent and an identical current project',async()=>{
 const state=store(), packet=raw();
 const created=await recovery.apply(packet,true,state,deps);
 assert.equal(created.ok,true);
 const stored=JSON.parse(state.getItem(recovery.recordSchema));
 delete stored.projectSnapshot;
 state.setItem(recovery.recordSchema,JSON.stringify(stored));
 assert.equal(recovery.read(state).cause,'recovery_snapshot_missing');
 const noConsent=await recovery.apply(packet,false,state,deps);
 assert.equal(noConsent.cause,'explicit_owner_consent_required');
 assert.equal(state.getItem(recovery.recordSchema),JSON.stringify(stored));
 const result=await recovery.apply(packet,true,state,deps);
 assert.equal(result.ok,true);
 assert.equal(result.migrated,true);
 assert.equal(result.alreadyRecovered,true);
 assert.equal(result.authority,'NONE');
 assert.equal(JSON.parse(state.getItem('preceptoros.documents.v1')).length,1);
 assert.equal(recovery.read(state).ok,true);
});
test('old receipt cannot be migrated after legitimate local project edits',async()=>{
 const state=store(), packet=raw();
 await recovery.apply(packet,true,state,deps);
 const old=JSON.parse(state.getItem(recovery.recordSchema));
 delete old.projectSnapshot;
 state.setItem(recovery.recordSchema,JSON.stringify(old));
 const changed=JSON.parse(state.getItem('preceptoros.public-mini.project.v1'));
 changed.description+=' owner edit';
 state.setItem('preceptoros.public-mini.project.v1',JSON.stringify(changed));
 const before=Array.from(state.map.entries());
 const res=await recovery.apply(packet,true,state,deps);
 assert.equal(res.ok,false);
 assert.equal(res.cause,'recovered_project_changed');
 assert.deepEqual(Array.from(state.map.entries()),before);
});

test('legitimate edited documents remain intact and are not certified by re-import',async()=>{
 const state=store(),packet=raw();
 await recovery.apply(packet,true,state,deps);
 const docs=JSON.parse(state.getItem('preceptoros.documents.v1'));
 docs[0].content+=' edited by owner';
 state.setItem('preceptoros.documents.v1',JSON.stringify(docs));
 const before=Array.from(state.map.entries());
 const repeated=await recovery.apply(packet,true,state,deps);
 assert.equal(repeated.ok,false);
 assert.equal(repeated.cause,'recovered_documents_changed');
 assert.deepEqual(Array.from(state.map.entries()),before);
 assert.equal(recovery.read(state).authority,'NONE');
});
