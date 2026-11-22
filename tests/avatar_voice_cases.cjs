'use strict';
const vm = require('node:vm');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const candidates = [path.join(__dirname, '../interface/avatar_voice.js'), path.join(__dirname, 'avatar_voice.js')];
const file = process.env.AVATAR_VOICE_SRC || candidates.find(fs.existsSync);
if (!file) throw new Error('NO_DATA(avatar_voice_source_not_found)');
const source = fs.readFileSync(file, 'utf8');
class El {
  constructor(tag) {this.tagName=tag;this.children=[];this.attributes={};this.style={};this.dataset={};this.listeners={};this.classList={contains:x=>(this._cls||[]).includes(x)};this.textContent='';this.value='';this.disabled=false;this.tabIndex=-1;}
  setAttribute(k,v){this.attributes[k]=String(v);if(k==='id')this.id=String(v);if(k==='data-state')this.dataset.state=String(v)}
  getAttribute(k){return this.attributes[k]??null}
  append(...kids){this.children.push(...kids)}
  appendChild(kid){this.children.push(kid)}
  addEventListener(t,cb){(this.listeners[t]??=[]).push(cb)}
  dispatchEvent(ev){for(let cb of this.listeners[ev.type]||[])cb(ev)}
  click(){this.dispatchEvent({type:'click'})}
  querySelectorAll(sel){return sel==='li'?this.children.filter(c=>c.tagName==='li'):[]}
}
const baseIds=['talk-actions','dicho','form-chat','hilo','talk-processing','estado'];
const observers=[];
class FakeObserver {constructor(callback){this.cb=callback;observers.push(this)}observe(node){this.node=node}}
const base=Object.fromEntries(baseIds.map(x=>[x,new El(x)]));
base['talk-processing'].dataset.state='IDLE';
let sends=0, readerStops=0, readerText=null;
base['form-chat'].requestSubmit=()=>sends++;
const doc={getElementById(id){if(base[id])return base[id];const all=[...Object.values(base)];while(all.length){let el=all.pop();if(el.id===id)return el;all.push(...el.children);}return null},createElement(tag){return new El(tag)},createElementNS(ns,tag){assert.equal(ns,'http://www.w3.org/2000/svg');return new El(tag)}};
let LocalRecognition=null;
class FakeSpeech {
  static async available(opts){assert.equal(opts.processLocally,true);assert.equal(opts.langs[0],'es-ES');return 'available'}
  constructor(){this.processLocally=false;LocalRecognition=this;}
  start(){this.onstart?.()}
  abort(){this.aborted=true;}
}
const root={document:doc,MutationObserver:FakeObserver,SpeechRecognition:undefined,webkitSpeechRecognition:undefined,SpeechSynthesisUtterance:undefined,Event:class {constructor(type){this.type=type}}, addEventListener:()=>{}, HexelionNativeVoice:{read:(text,lang,notify)=>{readerText={text,lang};notify('Reading visible text · local browser voice')},stop:()=>readerStops++}, setTimeout};
vm.runInNewContext(source,root,{filename:'avatar_voice.js'});
const el=id=>doc.getElementById(id);
const voice=root.HexelionAvatarVoice;
const wait=()=>new Promise(r=>setTimeout(r,5));
(async()=>{
 let n=0;function yes(ok,msg){n++;assert.ok(ok,msg)}
 yes(!!voice,'api mounted');
 yes(voice.state().schema==='hexelion.avatar-state/1','schema');
 yes(voice.state().authority==='none'&&voice.state().render_effects==='none','zero authority');
 yes(sends===0,'no auto-sends');
 yes(voice.state().state==='idle','idle initial');
 yes(el('hex-avatar-state').getAttribute('aria-live')==='off','no second live announcer');
 yes(el('hex-avatar-face').getAttribute('aria-label')===el('hex-avatar-state').textContent,'initial accessible parity');
 yes(el('hex-avatar-voice').dataset.cause===voice.state().cause,'initial cause parity');
 yes(el('hex-avatar-face').getAttribute('src')==='/assets/avatar-github.png','reuses existing served illustration');
 yes(el('hex-avatar-face').tagName==='img','no generated second renderer');
 yes(el('hex-avatar-voice').children.some(x=>x.tagName==='style'&&x.textContent.includes('prefers-reduced-motion')),'reduced motion contract');
 el('hex-avatar-listen').click();await wait();
 yes(voice.state().state==='no_data'&&voice.state().cause==='local_stt_unavailable','fail closed STT missing');
 yes(sends===0,'zero remote-only STT sends');
 root.SpeechRecognition=FakeSpeech;
 el('hex-avatar-listen').click();await wait();
 yes(LocalRecognition.processLocally===true,'enforce on-device flag');
 yes(voice.state().state==='listening','mic state');
 yes(sends===0,'not before result');
 LocalRecognition.onresult({results:[[{transcript:'hola prueba'}]]});
 yes(el('dicho').value==='hola prueba','transcript fills existing input');
 yes(sends===1,'existing Talk submit once');
 yes(voice.state().state==='thinking','thinking after send');
 yes(el('hex-avatar-face').getAttribute('aria-label')===el('hex-avatar-state').textContent,'ARIA parity thinking');
 yes(el('hex-avatar-voice').dataset.cause===voice.state().cause,'cause parity thinking');
 el('hex-avatar-stop').click();
 yes(voice.state().state==='interrupted','interrupt state');
 el('hex-avatar-mute').click();
 yes(voice.state().state==='muted','mute state');
 yes(el('hex-avatar-mute').getAttribute('aria-pressed')==='true','mute accessible');
 el('hex-avatar-listen').click();
 yes(sends===1,'muted no send');
 el('hex-avatar-mute').click();
 yes(voice.state().state==='idle','unmuted');
 base['estado'].dataset.cause='personal_profile_private_route_denied';
 for(const observer of observers.filter(x=>x.node===base['estado']))observer.cb();
 yes(voice.state().state==='awaiting_authorization','approval status derived from Talk');
 yes(voice.state().cause==='owner_profile_required','approval cause typed and retained');
 yes(el('hex-avatar-face').getAttribute('aria-label')===el('hex-avatar-state').textContent,'auth state accessible');
 const li=new El('li');li.textContent='respuesta visible';el('hilo').appendChild(li);
 el('hex-avatar-read').click();await wait();
 yes(readerText.text.includes('Último mensaje visible')&&readerText.text.includes('respuesta visible'),'last visible response with provenance caveat');
 yes(readerText.text.includes('Causa: local_speech_requested_audition_unverified'),'speech text shares state and cause');
 yes(readerText.lang==='es-ES','Spanish locale');
 yes(voice.state().state==='speaking','speech request state');
 yes(voice.state().cause==='local_speech_requested_audition_unverified','no faked sound proof');
 el('hex-avatar-stop').click();
 yes(readerStops>0&&voice.state().state==='interrupted','stop reading');
 yes(el('hex-avatar-face').getAttribute('aria-label')===el('hex-avatar-state').textContent,'final semantic parity');
 yes(el('hex-avatar-voice').dataset.state===voice.state().state,'final machine parity');
 yes(voice.state().authority==='none','still no auth');
 yes(root.HexelionAvatarVoice.state().render_effects==='none','zero effect claims after auth notice');
 console.log('PASS',n,'of',n,'tests (synthetic browser DOM, no actual mic/audio)');
})().catch(e=>{console.error('FAIL',e.stack);process.exitCode=1});