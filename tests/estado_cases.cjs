// PreceptorEstado (evidence_chip.js): one participant-state grammar. Deterministic: fixed `now`, no network.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const E=require('../interface/evidence_chip.js').estado;
const NOW=Date.parse('2026-11-16T12:00:00Z'), SHA='a'.repeat(64);
const st=(rows)=>E.fromEvidence(rows,NOW).state;

test('the table: twelve states, each with a word, a glyph, a tone, a line and an Acho reading; triples are unique',()=>{
  const names=Object.keys(E.states);
  assert.deepEqual(names.sort(),['authorized','available','blocked','done','hitl','loading','no_data','proposed','refused','stale','waiting','working']);
  const seen=new Set();
  for(const n of names){const s=E.states[n];for(const k of ['word','glyph','tone','line','acho','says'])assert.ok(s[k],n+'.'+k);
    const key=s.glyph+'|'+s.word;assert(!seen.has(key),'duplicate '+key);seen.add(key);}
  assert.equal(E.states.done.glyph,'■');assert.equal(E.states.refused.glyph,'✕');assert.equal(E.states.stale.glyph,'▲');assert.equal(E.states.no_data.glyph,'□');
});
test('false or untyped evidence is refused: thread talk, timers, UI, unknown words, bare strings',()=>{
  for(const fake of [{source:'thread',last_spoke:'2026-11-16T11:59:00Z'},{source:'timer',state:'working'},{source:'ui',state:'available'},
    {source:'conversation_open'},{state:'working'},'working',null,{source:'task',state:'RUNNING'},{source:'turn',state:'WORKING'},
    {source:'heartbeat',status:'WORKING',receipt:SHA}])
    assert.equal(E.fromEvidence([fake],NOW).state,'no_data',JSON.stringify(fake));
});
test('WORKING needs a declared run with a receipt and a fresh time; nothing else can make it',()=>{
  assert.equal(st([{source:'run',state:'RUNNING',receipt:SHA,at:'2026-11-16T11:59:30Z'}]),'working');
  assert.equal(st([{source:'run',state:'RUNNING',receipt:SHA,at:'2026-11-16T11:50:00Z'}]),'stale','an old run declaration is stale, not working');
  assert.equal(st([{source:'run',state:'RUNNING',at:'2026-11-16T11:59:30Z'}]),'no_data','no receipt');
  assert.equal(st([{source:'run',state:'RUNNING',receipt:SHA}]),'no_data','no time');
  assert.equal(st([{source:'run',state:'RUNNING',receipt:SHA,at:'2026-11-16T12:30:00Z'}]),'no_data','future time');
  assert.equal(st([{source:'heartbeat',status:'OBSERVADO',receipt:SHA}]),'available','a heartbeat is presence, never work');
});
test('AVAILABLE needs a heartbeat with its receipt sha; STALE heartbeat is stale',()=>{
  assert.equal(st([{source:'heartbeat',status:'OBSERVADO',receipt:'short'}]),'no_data');
  assert.equal(st([{source:'heartbeat',status:'STALE',receipt:SHA}]),'stale');
  assert.equal(E.fromEvidence([{source:'heartbeat',status:'NO_DATA',receipt:SHA,cause:'file_missing'}],NOW).cause,'file_missing');
});
test('tasks and turns map only their contract words',()=>{
  assert.equal(st([{source:'task',state:'NEEDS_YOUR_AUTHORIZATION'}]),'hitl');
  assert.equal(st([{source:'task',state:'DONE_CHECKED'}]),'done');
  assert.equal(E.fromEvidence([{source:'task',state:'DONE_UNCHECKED'}],NOW).evidence,'DECLARED');
  assert.equal(st([{source:'task',state:'FAILED'}]),'blocked');
  assert.equal(st([{source:'task',state:'NO_RESULT_RECORDED'}]),'waiting');
  for(const s of ['OUTCOME_UNKNOWN','CANCELLED','NO_DATA']) assert.equal(st([{source:'task',state:s}]),'no_data',s);
  assert.equal(st([{source:'turn',state:'ACTION_REFUSED'}]),'refused');
  for(const s of ['ACTION_UNVERIFIED','ANSWERED_UNVERIFIED','NO_ANSWER']) assert.equal(st([{source:'turn',state:s}]),'no_data',s);
});
test('receipts: ok is done, refused is refused, failed is blocked; no sha or no status is no data',()=>{
  assert.equal(st([{source:'receipt',result:'ok',status:'DECLARED',receipt:SHA}]),'done');
  assert.equal(st([{source:'receipt',result:'refused',status:'DECLARED',receipt:SHA}]),'refused');
  assert.equal(st([{source:'receipt',result:'failed',status:'DECLARED',receipt:SHA}]),'blocked');
  assert.equal(st([{source:'receipt',result:'ok',status:'STALE',receipt:SHA}]),'stale');
  assert.equal(st([{source:'receipt',result:'ok',status:'DECLARED'}]),'no_data');
  assert.equal(st([{source:'receipt',result:'ok',status:'VERIFIED',receipt:SHA}]),'no_data','a status the contract does not emit');
});
test('loops, bench and pending decisions: measured only',()=>{
  assert.equal(st([{source:'loop',fresh:true,result:'success'}]),'done');
  assert.equal(st([{source:'loop',fresh:true,result:'exit-code'}]),'blocked');
  assert.equal(st([{source:'loop',result:'success'}]),'no_data','stale sensor');
  assert.equal(st([{source:'loop',fresh:true,result:'probably fine'}]),'no_data');
  assert.equal(st([{source:'bench',attempted:2,failed:0}]),'done');
  assert.equal(st([{source:'bench',attempted:2,failed:1}]),'blocked');
  for(const b of [{attempted:0,failed:0},{attempted:2,failed:3},{attempted:'2',failed:0},{attempted:2}]) assert.equal(st([{source:'bench',...b}]),'no_data',JSON.stringify(b));
  assert.equal(st([{source:'hitl',pending:3,measured:true}]),'hitl');
  assert.equal(st([{source:'hitl',pending:0,measured:true}]),'done');
  assert.equal(st([{source:'hitl',pending:0}]),'no_data','an uncounted zero is not "nothing awaits you"');
  assert.equal(st([{source:'hitl',pending:-1,measured:true}]),'no_data');
});
test('combination: live overlays win, then the newest result, then presence; a bad row cannot hide a real one',()=>{
  const hb={source:'heartbeat',status:'OBSERVADO',receipt:SHA};
  assert.equal(st([hb,{source:'hitl',pending:1,measured:true}]),'hitl');
  assert.equal(st([hb,{source:'receipt',result:'ok',status:'DECLARED',receipt:SHA}]),'done');
  assert.equal(st([{source:'turn',state:'ACTION_REFUSED',at:'2026-11-16T10:00:00Z'},{source:'turn',state:'ACTED',at:'2026-11-16T11:00:00Z'}]),'done','newest result');
  assert.equal(st([{source:'turn',state:'ACTED',at:'2026-11-16T10:00:00Z'},{source:'turn',state:'ACTION_REFUSED',at:'2026-11-16T11:00:00Z'}]),'refused');
  assert.equal(st([{source:'timer',state:'working'},hb]),'available');
  assert.equal(E.fromEvidence([],NOW).state,'no_data');
  assert.equal(E.fromEvidence([{source:'absent',cause:'p2_mirror_not_built'}],NOW).cause,'p2_mirror_not_built');
});
test('one badge, three readers: eye (word on screen), screen reader (same sentence), machine and Acho (data-*)',()=>{
  const made=[];const doc={createElement:(tag)=>{const el={tag,children:[],dataset:{},attrs:{},className:'',textContent:'',
    setAttribute(k,v){this.attrs[k]=v;},append(...c){this.children.push(...c);},appendChild(c){this.children.push(c);}};made.push(el);return el;}};
  const x=E.fromEvidence([{source:'task',state:'NEEDS_YOUR_AUTHORIZATION'}],NOW);
  const b=E.make(doc,x,'Task r1');
  assert.equal(b.dataset.estado,'hitl');assert.equal(b.dataset.acho,'needs_you');assert.equal(b.dataset.tone,'warn');assert.equal(b.dataset.line,'solid');
  assert.equal(b.dataset.evidence,'DECLARED');assert.equal(b.dataset.source,'task');
  const word=b.children.find((c)=>c.className==='estado-word'), glyph=b.children.find((c)=>c.className==='estado-glyph'), sr=b.children.find((c)=>c.className==='sr');
  assert.equal(word.textContent,'NEEDS YOU');assert.equal(glyph.attrs['aria-hidden'],'true');assert.match(sr.textContent,/needs your authorization · evidence DECLARED/);
  assert.equal(E.sentence('Task r1',x),'Task r1: NEEDS YOU · needs your authorization · evidence DECLARED');
  const bad=E.make(doc,{state:'working_hard'},'x');assert.equal(bad.dataset.estado,'no_data','an unknown state never paints');
});
test('Talk evidence: a heartbeat with the same id and the newest receipt in its voice; speaking is never evidence',()=>{
  const {evidenceFor}=require('../interface/notebook.js');
  const nb={schema:'preceptoros.notebook-readonly/0',agents:[{id:'codex',status:'OBSERVADO',receipt_sha256:SHA}],
    receipts:[{voice:'hexelion',result:'refused',status:'DECLARED',receipt_sha256:SHA},{voice:'hexelion',result:'ok',status:'DECLARED',receipt_sha256:SHA}]};
  assert.equal(st(evidenceFor('codex',nb)),'available');
  assert.equal(st(evidenceFor('hexelion',nb)),'done','newest receipt in that voice');
  assert.equal(st(evidenceFor('claude',nb)),'no_data','spoke in the thread but no heartbeat or receipt');
  assert.equal(E.fromEvidence(evidenceFor('claude',{schema:'other'}),NOW).cause,'notebook_unreadable');
});
