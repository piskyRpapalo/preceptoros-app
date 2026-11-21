"use strict";
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const read=p=>fs.readFileSync('interface/'+p,'utf8');
test('Settings visible Kill switch is contained in its static accessible name',()=>{
  const tag=read('app.html').match(/<button[^>]*id="connection-kill"[\s\S]*?<\/button>/);
  assert(tag,'Kill switch button exists');
  const name=tag[0].match(/aria-label="([^"]+)"/)?.[1];
  const visible=tag[0].match(/>([^<>]+)<\/button>/)?.[1]?.trim();
  assert.equal(visible,'Kill switch');
  assert(name.includes(visible),'WCAG 2.5.3 label-in-name');
});
test('Dynamic accessible names retain both visible control labels',()=>{
 const source=read('connection_guard.js');
 assert.match(source,/"Kill switch · Pause My node and Open World"/);
 assert.match(source,/"Reconnect My node and Open World"/);
});
function setup(){
 const spoken=[],nodes={};
 for(const id of ['settings-speech-enable','settings-speech-read','settings-audio-status'])
   nodes[id]={dataset:{},textContent:'',disabled:false};
 const document={readyState:'loading',addEventListener(){},getElementById:id=>nodes[id]||null};
 const win={document,localStorage:{getItem(){return null},setItem(){}},speechSynthesis:{cancel(){},speak:u=>spoken.push(u)},SpeechSynthesisUtterance:function(t){this.text=t}};
 vm.runInNewContext(read('audio_accessibility.js'),{window:win});
 return {api:win.PreceptorAudioAccessibility,spoken,line:nodes['settings-audio-status']};
}
test('Requesting speech does not imply playback success',()=>{
 const x=setup();x.api.setEnabled(true);const r=x.api.speak('Read English');
 assert.equal(r.state,'REQUESTED');assert.equal(x.line.dataset.state,'REQUESTED');
 assert.equal(x.line.dataset.acho,'uncertain');assert.equal(x.line.dataset.cause,'native_speech_requested');
 assert.equal(x.spoken.length,1);
});
test('Disabled speech is BLOCKED with silent Acho and precise cause',()=>{
 const x=setup();const r=x.api.speak('read');
 assert.equal(r.state,'BLOCKED');assert.equal(x.line.dataset.state,'BLOCKED');
 assert.equal(x.line.dataset.acho,'silent');assert.equal(x.line.dataset.cause,'user_disabled');
 assert.equal(x.spoken.length,0);
});
function localVoice(voices){
 const spoken=[],notes=[];
 const root={TextEncoder,addEventListener(){},speechSynthesis:{cancel(){},getVoices(){return voices},speak:u=>spoken.push(u)},SpeechSynthesisUtterance:function(t){this.text=t}};
 vm.runInNewContext(read('native_voice.js'),{...root,globalThis:root});
 root.HexelionNativeVoice.read('English only','en',v=>notes.push(v),'browser');
 return {spoken,notes};
}
test('Existing native voice reader rejects Spanish-only voices',()=>{
 const x=localVoice([{lang:'es-ES',localService:true}]);
 assert.equal(x.spoken.length,0);assert.match(x.notes.join(' '),/NO_DATA.*no local voice for en/);
});
test('Existing native voice reader selects an installed local English voice',()=>{
 const x=localVoice([{lang:'es-ES',localService:true},{lang:'en_US',localService:true}]);
 assert.equal(x.spoken.length,1);assert.equal(x.spoken[0].voice.lang,'en_US');
});
