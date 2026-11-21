const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
function setup(secure=true,standalone=false){
  const handlers={},button={disabled:false,addEventListener:(n,f)=>handlers.click=f},status={};
  const root={navigator:{standalone},isSecureContext:secure,matchMedia:()=>({matches:false}),addEventListener:(n,f)=>handlers[n]=f};
  vm.runInNewContext(fs.readFileSync('interface/install.js','utf8'),root);root.HexelionInstall.mount(button,status);
  return{handlers,button,status};
}
test('no prompt is invented for insecure or unavailable contexts',()=>{
  const a=setup(false);assert(a.button.disabled);assert.match(a.status.textContent,/HTTPS/);
  a.handlers.beforeinstallprompt({preventDefault(){throw Error('insecure event accepted');}});
  assert(a.button.disabled);assert(setup().button.disabled);
});
test('accepted choice is not installation and duplicate clicks do not prompt twice',async()=>{
  const a=setup();let count=0,resolve;
  const event={preventDefault(){},prompt:()=>{count++;return Promise.resolve();},userChoice:new Promise(r=>resolve=r)};
  a.handlers.beforeinstallprompt(event);assert(!a.button.disabled);
  const first=a.handlers.click({isTrusted:true});await a.handlers.click({isTrusted:true});assert.equal(count,1);
  resolve({outcome:'accepted'});await first;assert.match(a.status.textContent,/Waiting/);
  a.handlers.appinstalled();assert.match(a.status.textContent,/reported app installed/);assert(a.button.disabled);
});
test('untrusted click never opens the browser prompt',async()=>{
  const a=setup();let count=0;
  a.handlers.beforeinstallprompt({preventDefault(){},prompt(){count++;}});
  await a.handlers.click({isTrusted:false});assert.equal(count,0);
});
test('dismissal remains uninstalled and a later native event may retry',async()=>{
  const a=setup();const event={preventDefault(){},prompt:async()=>{},userChoice:Promise.resolve({outcome:'dismissed'})};
  a.handlers.beforeinstallprompt(event);await a.handlers.click({isTrusted:true});assert.match(a.status.textContent,/dismissed/);
  a.handlers.beforeinstallprompt(event);assert(!a.button.disabled);
});
test('installed app ignores later eligibility events',()=>{
  const a=setup(true,true);a.handlers.beforeinstallprompt({preventDefault(){throw Error('installed event accepted');}});assert(a.button.disabled);
});

// UPDATE-STATE-01 · every state comes from a browser or rack signal; nothing is offered before the new worker installed.
function el(){const h={};return{textContent:'',disabled:false,attrs:{},h,addEventListener(n,f){h[n]=f;},setAttribute(k,v){this.attrs[k]=v;},removeAttribute(k){delete this.attrs[k];}};}
function updSetup(opts={}){
  const swH={},regH={};let reloads=0;
  const reg=Object.assign({installing:null,waiting:null,addEventListener:(n,f)=>regH[n]=f,update:opts.update||(async()=>{})},opts.reg||{});
  const controller=opts.noController?null:{postMessage(msg,ports){if(opts.silentWorker)return;ports[0].onmessage&&0;setImmediate(()=>ports[0]._peer.onmessage({data:opts.reply||{type:'shell-version',cache:'preceptoros-armazon-v197',files:32}}));}};
  class MessageChannel{constructor(){this.port1={onmessage:null};this.port2={_peer:this.port1};}}
  const sw=opts.noSw?undefined:{controller,addEventListener:(n,f)=>swH[n]=f,getRegistration:async()=>opts.noReg?undefined:reg};
  const fetch=opts.fetch||(async()=>({ok:true,json:async()=>({version:{huella:'abcdef123456',fecha:'2026-11-16',ficheros:33}})}));
  const root={navigator:{serviceWorker:sw},MessageChannel,setTimeout:(f,ms)=>setTimeout(f,opts.fastTimeout?1:ms),clearTimeout,fetch,location:{reload(){reloads++;}},matchMedia:()=>({matches:false}),addEventListener(){}};
  vm.runInNewContext(fs.readFileSync('interface/install.js','utf8'),root);
  const u={installed:el(),served:el(),state:el(),check:el(),reload:el()};
  const ready=root.HexelionInstall.mountUpdate(u);
  return{u,ready,swH,regH,reg,reloads:()=>reloads};
}
test('installed and served lines come from the worker and the rack',async()=>{
  const a=updSetup();await a.ready;
  assert.match(a.u.installed.textContent,/App v197 · 32 files/);assert.match(a.u.served.textContent,/Shell abcdef12 · 2026-11-16 · 33 files/);
  assert(a.u.reload.disabled,'nothing is offered before a check');
});
test('an older worker that does not answer is named, not guessed',async()=>{
  const a=updSetup({silentWorker:true,fastTimeout:true});await a.ready;assert.match(a.u.installed.textContent,/before v197/);
});
test('an invalid worker reply is NO_DATA',async()=>{
  const a=updSetup({reply:{cache:'evil-v1'}});await a.ready;assert.match(a.u.installed.textContent,/^NO_DATA/);
});
test('offline: served is NO_DATA and the installed app is said to keep working',async()=>{
  const a=updSetup({fetch:async()=>{throw Error('offline');}});await a.ready;
  assert.match(a.u.served.textContent,/^NO_DATA · the rack is not reachable/);assert.match(a.u.installed.textContent,/v197/);
});
test('no service worker or no registration: NO_DATA, never up to date',async()=>{
  const a=updSetup({noSw:true});await a.ready;await a.u.check.h.click({isTrusted:true});
  assert.match(a.u.state.textContent,/^NO_DATA/);assert.match(a.u.installed.textContent,/^NO_DATA/);
  const b=updSetup({noReg:true});await b.ready;await b.u.check.h.click({isTrusted:true});assert.match(b.u.state.textContent,/^NO_DATA · this app is not registered/);
});
test('check with nothing new says up to date; a failed check is NO_DATA, not up to date',async()=>{
  const a=updSetup();await a.ready;await a.u.check.h.click({isTrusted:true});assert.match(a.u.state.textContent,/^Up to date/);assert(a.u.reload.disabled);
  const b=updSetup({update:async()=>{throw Error('net');}});await b.ready;await b.u.check.h.click({isTrusted:true});
  assert.match(b.u.state.textContent,/^NO_DATA · could not reach the rack/);assert(b.u.reload.disabled);
});
test('a new worker downloading is not offered; a failed install is refused and offers nothing',async()=>{
  const wh={};const worker={state:'installing',addEventListener:(n,f)=>wh[n]=f};
  const a=updSetup({reg:{installing:worker}});await a.ready;await a.u.check.h.click({isTrusted:true});
  assert.match(a.u.state.textContent,/^Downloading/);assert(a.u.reload.disabled);
  worker.state='redundant';wh.statechange();assert.match(a.u.state.textContent,/^Update refused/);assert(a.u.reload.disabled);
});
test('only controllerchange (new worker installed and active) offers reload; reload needs a trusted click; no auto reload',async()=>{
  const a=updSetup();await a.ready;
  a.u.reload.h.click({isTrusted:true});assert.equal(a.reloads(),0,'nothing offered yet');
  a.swH.controllerchange();assert(!a.u.reload.disabled);assert.match(a.u.state.textContent,/^Update ready/);assert.equal(a.reloads(),0);
  await new Promise(r=>setTimeout(r,20));assert.match(a.u.installed.textContent,/still shows the previous version until you reload/);
  a.u.reload.h.click({isTrusted:false});assert.equal(a.reloads(),0);
  a.u.reload.h.click({isTrusted:true});assert.equal(a.reloads(),1);
});
test('untrusted or repeated check clicks do not double-check',async()=>{
  let n=0;const a=updSetup({update:()=>new Promise(r=>{n++;setTimeout(r,5);})});await a.ready;
  await a.u.check.h.click({isTrusted:false});assert.equal(n,0);
  const first=a.u.check.h.click({isTrusted:true});await a.u.check.h.click({isTrusted:true});await first;assert.equal(n,1);
});
test('the worker answers its own number and still deletes only caches',()=>{
  const src=fs.readFileSync('interface/sw.js','utf8');
  assert.match(src,/const Cache = "preceptoros-armazon-v240";/);assert.match(src,/"\/install\.js\?v=2"/);
  assert.match(src,/type: "shell-version", cache: Cache/);
  assert(!/indexedDB|localStorage|clients\.matchAll\(\)\.then\([^)]*navigate/.test(src),'worker must not touch browser storage or force navigation');
});
test('first visit: the first worker claiming the page is not an update',async()=>{
  const a=updSetup({noController:true});await a.ready;
  a.swH.controllerchange();assert(a.u.reload.disabled);assert.match(a.u.state.textContent,/kept on this device for offline use/);
});
