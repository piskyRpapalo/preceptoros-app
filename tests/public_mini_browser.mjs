/* Real Chrome, loopback-only MINI smoke. Mobile 360/420, offline and local persistence. */
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {createServer} from 'node:http';
import {readFile,mkdtemp,rm} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join,resolve,extname,sep} from 'node:path';

const root=resolve('dist/public-mini-app');
const width=Number(process.argv[2] || 360);
if (![360,420].includes(width)) throw Error('width_requires_360_or_420');
const mime={'.html':'text/html','.js':'application/javascript','.css':'text/css',
 '.json':'application/json','.webmanifest':'application/manifest+json','.png':'image/png'};
const requests=[],writes=[];
const server=createServer(async(req,res)=>{
 const path=new URL(req.url,'http://localhost').pathname;
 if(req.method!=='GET'&&req.method!=='HEAD'){writes.push({method:req.method,path});res.writeHead(405);res.end();return;}
 if(path==='/app'){res.writeHead(308,{location:'/app/'});res.end();return;}
 const relative=path==='/app/'?'/app/index.html':path;
 if(!relative.startsWith('/app/')){res.writeHead(404);res.end();return;}
 const file=resolve(root,'.'+relative);
 if(!file.startsWith(root+sep)){res.writeHead(403);res.end();return;}
 try{
  const data=await readFile(file);
  requests.push(path);
  res.writeHead(200,{'content-type':mime[extname(file)]||'application/octet-stream',
    'cache-control':'no-store'});res.end(data);
 }catch{res.writeHead(404);res.end();}
});
await new Promise(r=>server.listen(0,'127.0.0.1',r));
const url='http://127.0.0.1:'+server.address().port+'/app/';
const profile=await mkdtemp(join(tmpdir(),'preceptor-mini-cdp-'));
const chrome=spawn('/usr/bin/google-chrome',['--headless=new','--no-sandbox','--disable-gpu',
 '--disable-extensions','--disable-background-networking','--no-first-run',
 '--remote-debugging-port=0','--user-data-dir='+profile,url],
 {stdio:['ignore','ignore','pipe']});
let errors='', ws;
chrome.stderr.on('data',b=>errors+=String(b).slice(0,1000));
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try {
 let port=0;
 for(let i=0;i<70;i++){
  try{port=Number((await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0]);break;}catch{await sleep(100);}
 }
 assert.ok(port,'Chrome CDP unavailable: '+errors.slice(0,240));
 let page=null;
 for(let i=0;i<50;i++){
  try{page=(await (await fetch('http://127.0.0.1:'+port+'/json/list')).json())
    .find(p=>p.type==='page'&&p.url.includes('/app/'));if(page)break;}catch{}
  await sleep(100);
 }
 assert.ok(page,'MINI browser page missing');
 ws=new WebSocket(page.webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.addEventListener('open',r,{once:true});ws.addEventListener('error',j,{once:true});});
 const pending=new Map();let id=0;
 ws.addEventListener('message',e=>{const msg=JSON.parse(e.data);if(msg.id&&pending.has(msg.id)){
  pending.get(msg.id)(msg);pending.delete(msg.id);
 }});
 const command=(method,params={})=>new Promise((r,j)=>{
  const n=++id;pending.set(n,r);ws.send(JSON.stringify({id:n,method,params}));
  setTimeout(()=>{if(pending.has(n)){pending.delete(n);j(Error('CDP_TIMEOUT_'+method));}},12000).unref();
 });
 const evaluate=async expression=>{
  const msg=await command('Runtime.evaluate',{expression,awaitPromise:true,returnByValue:true});
  if(msg.result?.exceptionDetails)throw Error('BROWSER_EXCEPTION_'+JSON.stringify(msg.result.exceptionDetails).slice(0,500));
  return msg.result?.result?.value;
 };
 await command('Runtime.enable');
 await command('Page.enable');
 await command('Network.enable');
 await command('Emulation.setDeviceMetricsOverride',{width,height:740,deviceScaleFactor:1,mobile:true});
 await command('Page.reload',{ignoreCache:true});
 let booted=false;
 for(let i=0;i<75;i++){
  try{booted=await evaluate("!!(window.PreceptorMiniProjectGuide&&document.getElementById('mini-project-status')&&document.getElementById('form-chat').dataset.miniMounted)");}catch{}
  if(booted)break;
  await sleep(100);
 }
 assert.equal(booted,true,'no public MINI boot: '+errors.slice(0,200));
 const initial=await evaluate("({tabs:document.querySelectorAll('[role=tab]').length,scroll:document.documentElement.scrollWidth,client:document.documentElement.clientWidth,model:document.getElementById('mini-model-status').dataset.state})");
 assert.equal(initial.tabs,6);assert.equal(initial.model,'DETERMINISTIC_ONLY');
 const six=await evaluate("Array.from(document.querySelectorAll('[role=tab]'),x=>x.id)");
 assert.deepEqual(six,['tab-conversacion','tab-cuaderno','tab-lab','tab-ajustes','tab-modelos','tab-settings']);
 const first=await evaluate("({open:!document.getElementById('mvp-first-run').hidden,steps:document.querySelectorAll('#mvp-first-run ol > li').length,draft:localStorage.getItem('preceptoros.node-public-template/1')})");
 assert.deepEqual(first,{open:true,steps:3,draft:null});
 assert.ok(initial.scroll<=initial.client+4,'horizontal overflow '+JSON.stringify(initial));
 const firstOpen=await evaluate("(()=>{document.getElementById('mvp-first-run-mini').click();return {shown:!document.getElementById('modelos-menu').hidden,focus:document.activeElement.id,mini:document.getElementById('mini-local-toggle').getAttribute('aria-pressed')};})()");
 assert.deepEqual(firstOpen,{shown:true,focus:'mini-local-toggle',mini:'true'});
 const firstNode=await evaluate("(()=>{document.getElementById('mvp-first-run-node').click();return {node:!document.getElementById('panel-ajustes').hidden,expanded:document.getElementById('ajustes-nodo').open,focus:document.activeElement.id,posts:0};})()");
 assert.deepEqual(firstNode,{node:true,expanded:true,focus:'node-default-name',posts:0});
 assert.equal(writes.length,0,'opening My node must not write to any server');
 await evaluate("(()=>{document.getElementById('tab-settings').click();document.getElementById('mini-text-large').click();document.getElementById('mini-reduced-motion').click();return true;})()");
 const prefs=await evaluate("({large:document.documentElement.dataset.miniLargeText,motion:document.documentElement.dataset.reduceMotion,stored:JSON.parse(localStorage.getItem('preceptoros.public-mini.settings/1')).schema})");
 assert.deepEqual(prefs,{large:'true',motion:'true',stored:'preceptoros.public-mini.settings/1'});
 await evaluate("(()=>{document.getElementById('tab-conversacion').click();return true;})()");
 const routed=await evaluate("(()=>{const field=document.getElementById('dicho');field.value='open Documents';document.getElementById('form-chat').requestSubmit();return !document.getElementById('panel-cuaderno').hidden;})()");
 assert.equal(routed,true,'shared deterministic MINI did not route to Documents');
 const help=await evaluate("(()=>{document.getElementById('tab-conversacion').click();document.getElementById('mini-guide-ask').value='where are my documents?';document.getElementById('mini-guide-form').requestSubmit();return document.getElementById('mini-guide-answer').textContent;})()");
 assert.match(help,/interface\/documents.js/);
 const unknown=await evaluate("(()=>{document.getElementById('dicho').value='write me a full novel';document.getElementById('form-chat').requestSubmit();return document.getElementById('hilo').lastElementChild.textContent;})()");
 assert.match(unknown,/NO_DATA\(on_device_model_unavailable\)/);

 await evaluate("(()=>{document.getElementById('mini-start-project').click();const x=document.getElementById('mini-project-template');x.value='law';x.dispatchEvent(new Event('change'));document.getElementById('mini-project-title').value='Owner Law Study';document.getElementById('mini-project-form').requestSubmit();return true;})()");
 const title=await evaluate("JSON.parse(localStorage.getItem('preceptoros.public-mini.project.v1')).title");
 assert.equal(title,'Owner Law Study');
 await evaluate("(()=>{document.getElementById('mini-to-documents').click();document.getElementById('documentos-nuevo-btn').click();document.getElementById('documentos-titulo').value='My source note';document.getElementById('documentos-titulo').dispatchEvent(new Event('input'));document.getElementById('documentos-contenido').value='Owner reviewed the original AI Act link.';document.getElementById('documentos-guardar').click();return true;})()");
 const docs=await evaluate("window.PreceptorDocuments.loadDocuments().filter(x=>x.state==='saved').length");
 if(docs!==1)console.error('DOC_DEBUG',await evaluate("({status:document.getElementById('documentos-editor-estado').textContent,button:document.getElementById('documentos-guardar').disabled,value:document.getElementById('documentos-titulo').value,items:window.PreceptorDocuments.loadDocuments(),general:document.getElementById('documentos-estado').textContent})"));
 assert.equal(docs,1);
 await evaluate("(()=>{document.getElementById('tab-lab').click();document.getElementById('mini-project-refresh').click();document.getElementById('mini-project-review').click();return true;})()");
 const review=await evaluate("({list:document.getElementById('mini-project-steps').textContent,docCount:JSON.parse(document.getElementById('mini-project-review-text').textContent).documents})");
 assert.equal(review.docCount,1);assert.match(review.list,/Complete: Add documents/);
 await evaluate("(()=>{document.getElementById('mini-to-node').click();const r=document.getElementById('owner-private-runtime');r.value='owner_managed';r.dispatchEvent(new Event('input'));document.getElementById('owner-private-label').value='Own optional model';document.getElementById('owner-models-form').requestSubmit();document.getElementById('node-registration-name').value='nodo.42.collaborator';document.getElementById('node-registration-purpose').value='Owner library';document.getElementById('node-registration-form').requestSubmit();return true;})()");
 const node=await evaluate("({model:window.PreceptorMiniProjectGuide.modelState(window.PreceptorOwnerModelSlots,localStorage).state,state:document.getElementById('node-registration-status').dataset.state})");
 assert.equal(node.model,'MODEL_CONFIGURED');assert.equal(node.state,'DRAFT_ONLY');
 const ownerDraft=await evaluate("(()=>{const name=document.getElementById('node-default-name');const description=document.getElementById('node-default-description');name.value='My own Companion';description.value='Private local research';document.getElementById('node-default-save').click();return JSON.parse(localStorage.getItem('preceptoros.node-public-template/1'));})()");
 assert.equal(ownerDraft.name,'My own Companion');
 assert.equal(ownerDraft.description,'Private local research');
 assert.ok(ownerDraft.prompt.startsWith('You are an experimental PreceptorOS companion.'));
 await evaluate("(()=>{const c=document.getElementById('node-registration-consent');c.checked=true;c.dispatchEvent(new Event('change'));document.getElementById('node-registration-submit').click();return true;})()");
 await sleep(150);
 const blocked=await evaluate("({state:document.getElementById('node-registration-status').dataset.state,text:document.getElementById('node-registration-status').textContent})");
 assert.equal(blocked.state,'NO_DATA');assert.match(blocked.text,/native_preliminary_request_not_available/);
 await command('Page.reload');
 await sleep(450);
 const persisted=await evaluate("({project:document.getElementById('mini-project-title').value,docs:window.PreceptorDocuments.loadDocuments().length,model:window.PreceptorMiniProjectGuide.modelState(window.PreceptorOwnerModelSlots,localStorage).state,companion:document.getElementById('node-default-name').value})");
 assert.equal(persisted.project,'Owner Law Study');assert.equal(persisted.docs,1);
 assert.equal(persisted.model,'MODEL_CONFIGURED');
 assert.equal(persisted.companion,'My own Companion');
 const restoredPrefs=await evaluate("({large:document.documentElement.dataset.miniLargeText,motion:document.documentElement.dataset.reduceMotion})");
 assert.deepEqual(restoredPrefs,{large:'true',motion:'true'});
 assert.equal(writes.length,0,'all local saves and node previews must remain local');
 const sw=await evaluate("navigator.serviceWorker.ready.then(()=>true).catch(()=>false)");
 assert.equal(sw,true);
 await command('Network.emulateNetworkConditions',{offline:true,latency:0,downloadThroughput:0,uploadThroughput:0});
 await command('Page.reload',{ignoreCache:false});
 await sleep(550);
 const offline=await evaluate("({loaded:!!window.PreceptorOfflineMini,project:window.PreceptorMiniProjectGuide.load(localStorage,window.PreceptorCompanionOnboarding).ok})");
 assert.equal(offline.loaded,true);assert.equal(offline.project,true);
 assert.equal(requests.filter(x=>x.includes('/api/')).length,0);
 assert.equal(writes.length,0);
 console.log(JSON.stringify({status:'PASS',width,tabs:6,docCount:docs,model:node.model,
  offline:true,consentBlocked:blocked.state,localRequests:requests.length,
  apiRequests:0,writes:0,onboarding:'PASS',ownerDraft:'PASS',settings:'PASS',
  scroll:initial.scroll,client:initial.client}));
}catch(e){
 console.error(JSON.stringify({status:'FAIL',width,error:String(e.stack||e).slice(0,1500)}));
 process.exitCode=1;
}finally{
 try{ws?.close();}catch{}
 chrome.kill('SIGTERM');await sleep(120);try{chrome.kill('SIGKILL');}catch{}
 await new Promise(r=>server.close(r));
 await rm(profile,{recursive:true,force:true});
}
