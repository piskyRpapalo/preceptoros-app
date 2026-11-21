'use strict';
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const app = require('../interface/companion_onboarding.js');

const good = () => ({name:'Solar Workshop',purpose:'Build open-source parts in my home'});
test('room creates precisely one local building draft, not admission',()=>{
  const r=app.renderBuildingDraft(good());
  assert.equal(r.ok,true);
  assert.equal(r.slug,'solar-workshop');
  assert.match(r.text,/Schema: preceptoros\.room-building-draft\/1/);
  assert.match(r.text,/Building count: 1/);
  assert.match(r.text,/State: DRAFT_ONLY/);
  assert.match(r.text,/NO_DATA\(building_admission_not_requested\)/);
  assert.match(r.text,/NO_DATA\(world_publication_not_verified\)/);
  assert.match(r.text,/Nothing was submitted, registered, signed or published/);
  assert.doesNotMatch(r.text,/Status: (?:LIVE|AUTHORIZED)/);
});
test('home install and Companion are later, own model and feedback hardware',()=>{
  const r=app.renderBuildingDraft(good());
  assert.match(r.text,/at home/i);
  assert.match(r.text,/Companion HITL PR if you have GitHub/i);
  assert.match(r.text,/does not connect any model, private service or owner account/);
  assert.doesNotMatch(r.text,/Hexelion|founder.s rack|founder.s private|private rack/i);
  assert.match(r.text,/owner's own hardware/);
  assert.match(r.text,/NO_DATA\(owner_model_not_connected\)/);
});
test('reuses strict existing validation for empty name/purpose and length',()=>{
  for(const x of [{name:'',purpose:'Hello'},{name:'A',purpose:''},
    {name:'a'.repeat(81),purpose:'Good'},
    {name:'Good',purpose:'a'.repeat(601)}]) {
    assert.equal(app.renderBuildingDraft(x).ok,false,JSON.stringify(x).slice(0,100));
  }
});
test('slug is provisional and Unicode accents are normalized',()=>{
  assert.equal(app.renderBuildingDraft({name:'Café do Sol',purpose:'Solar repair'}).slug,'cafe-do-sol');
  assert.equal(app.renderBuildingDraft({name:'!!!',purpose:'Solar repair'}).ok,false);
  assert.equal(app.renderBuildingDraft({name:'A'.repeat(24),purpose:'Solar repair'}).slug.length,24);
});
test('shared secret policy rejects account tokens in either input',()=>{
  for (const value of ['my api_key is abc', 'secret password=xx',
    'Bearer abcdefghijklmno', 'sk-abcdefghijklmnopqrst', 'github_pat_abcdefghijklmn',
    'https://name:pass@example.com/private']) {
    for(const field of ['name','purpose']) {
      const form=good();form[field]=value;
      assert.equal(app.renderBuildingDraft(form).ok,false,field+' '+value);
    }
  }
});
test('treat text supplied by participants as data, not HTML',()=>{
  const r=app.renderBuildingDraft({
    name:'<script>alert(1)</script>',
    purpose:'Please execute <img src=x onerror=alert(1)>'
  });
  assert.equal(r.ok,true);
  assert.ok(r.text.includes('Building name (owner data): "' + String.fromCharCode(92) + 'u003c'));
  assert.ok(r.text.includes('Purpose (owner data): "Please execute ' + String.fromCharCode(92) + 'u003c'));
  assert.doesNotMatch(r.text,/<script|<img/);
  assert.doesNotMatch(r.text,/node_publication_verified/);
});
test('no new authority, network, or local storage in room path',()=>{
  const source=fs.readFileSync(path.join(__dirname,'../interface/companion_onboarding.js'),'utf8');
  const room=source.slice(source.indexOf('function buildingSlug'),source.indexOf('/*  Browser UI mount'));
  assert.ok(room.includes('renderDraft({ slug: slug'), 'reuse existing validator');
  assert.ok(!room.includes('fetch('));
  assert.ok(!room.includes('XMLHttpRequest'));
  assert.ok(!room.includes('localStorage.'));
  assert.ok(!room.includes('sessionStorage.'));
  assert.ok(!room.includes('navigator.sendBeacon'));
});
test('no model/provider is required for the room',()=>{
  const r=app.renderBuildingDraft({name:'My garden',purpose:'Grow vegetables'});
  assert.equal(r.ok,true);
  assert.match(r.text,/NO_DATA\(owner_model_not_connected\)/);
  assert.doesNotMatch(r.text,/github\.com.*pull/);
});
