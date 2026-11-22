const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup(voices) {
  const spoken=[];
  const scope={TextEncoder,AbortController,Blob,crypto:require('node:crypto').webcrypto,URL,
    speechSynthesis:{getVoices:()=>voices,cancel(){},speak:u=>spoken.push(u)},
    SpeechSynthesisUtterance:function(text){this.text=text;},addEventListener(){}};
  vm.runInNewContext(fs.readFileSync('interface/native_voice.js','utf8'),scope);
  return {scope,spoken,reader:scope.HexelionNativeVoice};
}
test('remote-only voices never cause speech or an implicit default',()=>{
  const {reader,spoken}=setup([{localService:false,lang:'en-US'}]);let status;
  reader.read('Synthetic test text','en',s=>status=s,'browser');
  assert.match(status,/NO_DATA/);assert.equal(spoken.length,0);
});
test('chunks preserve every Unicode character and obey the byte budget',()=>{
  const {reader}=setup([]);const text='Synthetic 🌊 text. '.repeat(400);
  const parts=reader.chunks(text);assert.equal(parts.join(''),text);
  assert(parts.every(p=>Buffer.byteLength(p)<=700));
});
test('STOP invalidates late native callbacks and remaining chunks',()=>{
  const {reader,spoken}=setup([{localService:true,lang:'en-US'}]);
  reader.read('Synthetic '.repeat(200),'en',()=>{},'browser');
  assert.equal(spoken.length,1);reader.stop();spoken[0].onend();assert.equal(spoken.length,1);
});
test('STOP ignores a late host response without creating audio',async()=>{
  const {reader,scope}=setup([]);let finish,created=0;
  scope.fetch=()=>new Promise(r=>finish=r);scope.Audio=function(){created++;};
  reader.read('Synthetic test text','en',()=>{},'host-espeak-ng');
  reader.stop();finish({ok:true});await new Promise(r=>setImmediate(r));assert.equal(created,0);
});
// Bugfix 3 (2026-11-03): the Doogee read «no local browser voice» with 0 voices and no cause. Chrome hands an empty
// list until `voiceschanged`; a device may have no TTS engine at all. Each case now says WHICH NO_DATA it is.
function setupLate(initial, later, opts={}) {
  const spoken=[],timers=[];let listener=null,voices=initial;
  const synth=opts.noSynth?undefined:{getVoices:()=>voices,cancel(){},speak:u=>spoken.push(u),
    addEventListener:(t,h)=>{if(t==='voiceschanged')listener=h;},removeEventListener:()=>{listener=null;}};
  const scope={TextEncoder,AbortController,Blob,crypto:require('node:crypto').webcrypto,URL,speechSynthesis:synth,
    SpeechSynthesisUtterance:function(text){this.text=text;},addEventListener(){},
    setTimeout:(f,ms)=>{timers.push(f);return timers.length;},clearTimeout:()=>{}};
  vm.runInNewContext(fs.readFileSync('interface/native_voice.js','utf8'),scope);
  return {reader:scope.HexelionNativeVoice,spoken,arrive:()=>{voices=later;listener&&listener();},expire:()=>timers.splice(0).forEach(f=>f())};
}
test('voices that arrive late (voiceschanged) are waited for and used',()=>{
  const t=setupLate([],[{localService:true,lang:'en-US'}]);let status;
  t.reader.read('Synthetic test text','en',s=>status=s,'browser');
  assert.equal(t.spoken.length,0);t.arrive();assert.equal(t.spoken.length,1);assert.match(status,/part 1\/1/);
});
test('a device with zero voices says so, with the count and what to do',()=>{
  const t=setupLate([],[]);let status;
  t.reader.read('Synthetic test text','en',s=>status=s,'browser');t.expire();
  assert.match(status,/^NO_DATA · this device has no installed voices \(0\)/);assert.equal(t.spoken.length,0);
});
test('no speech synthesis at all is its own cause',()=>{
  const t=setupLate([],[],{noSynth:true});let status;
  t.reader.read('Synthetic test text','en',s=>status=s,'browser');
  assert.match(status,/^NO_DATA · this browser has no speech synthesis/);
});
test('only network voices: said as such, text never leaves',()=>{
  const t=setupLate([{localService:false,lang:'en-US'}],[]);let status;
  t.reader.read('Synthetic test text','en',s=>status=s,'browser');
  assert.match(status,/only network voices/);assert.equal(t.spoken.length,0);
});
test('local voices in other languages: the count is given',()=>{
  const t=setupLate([{localService:true,lang:'es-ES'},{localService:true,lang:'fr-FR'}],[]);let status;
  t.reader.read('Synthetic test text','en',s=>status=s,'browser');
  assert.match(status,/no local voice for en \(2 local voices in other languages\)/);
});
test('STOP while waiting for voices: nothing is spoken when they arrive',()=>{
  const t=setupLate([],[{localService:true,lang:'en-US'}]);
  t.reader.read('Synthetic test text','en',()=>{},'browser');t.reader.stop();t.arrive();t.expire();
  assert.equal(t.spoken.length,0);
});
// Measured on the Doogee (2026-11-03): Chrome for Android tags voices «en_US», with an underscore. 87 local voices,
// 5 of them English, and the reader saw none: split('-') kept «en_US» whole. BCP 47 says '-'; Android says '_'.
test('an Android voice tag with an underscore (en_US) is the same language as en',()=>{
  const t=setupLate([{localService:true,lang:'es_ES'},{localService:true,lang:'en_US'}],[]);let status;
  t.reader.read('Synthetic test text','en',s=>status=s,'browser');
  assert.equal(t.spoken.length,1);assert.equal(t.spoken[0].lang,'en_US');assert.match(status,/part 1\/1/);
});


test('loopback Spanish without browser voices uses only the existing host reader',async()=>{
  const {reader,scope,spoken}=setup([]);
  let requests=[],plays=0,notices=[];
  scope.location={protocol:'http:',hostname:'127.0.0.1'};
  const bytes=Uint8Array.from([82,73,70,70,0,0,0,0,87,65,86,69]);
  const crypto0=require('node:crypto');
  scope.Audio=function(){this.play=async()=>{plays++};this.pause=()=>{};this.removeAttribute=()=>{};this.load=()=>{};};
  scope.fetch=async(url,options)=>{
    const body=JSON.parse(options.body);requests.push({url,body,options});
    const receipt={state:'ok',engine:'host-espeak-ng',language:'es',
      text_sha256:crypto0.createHash('sha256').update(body.text).digest('hex'),
      audio_sha256:crypto0.createHash('sha256').update(bytes).digest('hex'),
      bytes:bytes.byteLength};
    return {ok:true,headers:{get:()=>JSON.stringify(receipt)},arrayBuffer:async()=>bytes.buffer};
  };
  reader.read('Hola, estado local.','es-ES',s=>notices.push(s),'browser');
  await new Promise(resolve=>setTimeout(resolve,20));
  assert.equal(spoken.length,0,'no hidden browser voice is used');
  assert.equal(requests.length,1,'only one host read');
  assert.equal(requests[0].url,'/api/voz/lectura');
  assert.equal(requests[0].options.method,'POST');
  assert.equal(requests[0].options.redirect,'error');
  assert.deepEqual(requests[0].body,{text:'Hola, estado local.',engine:'host-espeak-ng',language:'es'});
  assert.equal(plays,1,'software playback requested; physical speaker not proved');
  assert.match(notices.join(' '),/physical audibility NO_DATA/);
});

test('non-loopback Spanish without local voices never asks host to read',()=>{
  const {reader,scope,spoken}=setup([]);
  let calls=0,note='';
  scope.location={protocol:'https:',hostname:'example.test'};
  scope.fetch=()=>{calls++;throw Error('must not call');};
  scope.Audio=function(){};
  reader.read('Hola','es-ES',s=>note=s,'browser');
  assert.equal(calls,0);assert.equal(spoken.length,0);assert.match(note,/NO_DATA/);
});

test('Spanish local browser voice wins over host fallback',()=>{
  const {reader,scope,spoken}=setup([{localService:true,lang:'es_ES'}]);
  let calls=0;
  scope.location={protocol:'http:',hostname:'127.0.0.1'};
  scope.fetch=()=>{calls++;throw Error('host forbidden when local voice exists');};
  scope.Audio=function(){};
  reader.read('Hola','es-ES',()=>{},'browser');
  assert.equal(spoken.length,1);assert.equal(calls,0);
});
