'use strict';
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(__dirname, '..');
const port = Number(process.env.PREVIEW_PORT || 18896);
const url = 'http://127.0.0.1:' + port + '/app.html';
const delay = ms => new Promise(r => setTimeout(r, ms));
(async () => {
 const server = spawn('python3', ['-m', 'http.server', String(port), '--bind',
  '127.0.0.1', '--directory', path.join(root,'interface')], {stdio:'ignore'});
 let browser;
 try {
  for (let i=0;i<50;i++) {try {if ((await fetch(url)).ok)break;}catch{} await delay(100);}
  browser = await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',
    args:['--no-sandbox','--disable-dev-shm-usage']});
  const results=[];
  for (const viewport of [{width:360,height:640},{width:420,height:680},{width:900,height:968}]) {
   const context = await browser.newContext({viewport,serviceWorkers:'block',reducedMotion:'reduce'});
   const page = await context.newPage();
   const errors=[]; page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/api/estado',route=>route.fulfill({status:404,contentType:'application/json',
     body:JSON.stringify({estado:'NO_DATA',causa:'not_implemented_in_preview'})}));
   await page.route('https://preceptoros.org/openworld/**',route=>route.abort('blockedbyclient'));
   await page.goto(url,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>window.PreceptorConnectionGuard && !!window.PreceptorPanelFlow);
   await page.waitForFunction(()=>document.querySelector('#connection-status').dataset.cause === 'local_service_http_404');
   const initial=await page.evaluate(()=>{
    const head=document.querySelector('.identidad'),h1=head.querySelector('h1'),os=head.querySelector('.brand-os');
    const rect=x=>{const r=x.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,
      bottom:r.bottom,width:r.width,height:r.height}};
    const panel=document.getElementById('panel-conversacion');
    const actions=document.getElementById('talk-actions');
    const form=document.getElementById('form-chat');
    const textarea=document.getElementById('dicho');
    const send=document.getElementById('enviar');
    const status=document.getElementById('connection-status');
    return {brand:h1.textContent,osColor:getComputedStyle(os).color,
      head:rect(head),title:rect(h1),controls:rect(document.querySelector('.connection-controls')),
      status:status.textContent,cause:status.dataset.cause,toolbar:rect(actions),panel:rect(panel),
      form:rect(form),composer:rect(textarea),send:rect(send),
      visibleDiagnostics:!!document.querySelector('#panel-conversacion #talk-diagnostics'),
      hiddenInterlocutor:document.getElementById('conv-interlocutor').hidden,
      hiddenTurn:!!document.getElementById('estado').classList.contains('sr'),
      duplicateIds:(()=>{const ids=[...document.querySelectorAll('[id]')].map(e=>e.id);return ids.filter((x,i)=>ids.indexOf(x)!==i)})(),
    };
   });
   assert.equal(initial.brand,'PreceptorOS');
   assert.equal(initial.status,'Not connected');
   assert.equal(initial.cause,'local_service_http_404');
   assert.equal(initial.visibleDiagnostics,false);
   assert.equal(initial.hiddenInterlocutor,true);
   assert.equal(initial.hiddenTurn,true);
   assert.deepEqual(initial.duplicateIds,[]);
   assert.ok(initial.title.bottom > initial.controls.top && initial.controls.bottom > initial.title.top,'same row');
   assert.ok(initial.controls.right <= viewport.width +1,'header controls inside screen');
   assert.ok(initial.form.left >= initial.panel.left-1 && initial.form.right <= initial.panel.right+1,'composer outer width matches panel');
   assert.ok(Math.abs(initial.form.left-initial.panel.left)<=2 && Math.abs(initial.form.right-initial.panel.right)<=2,'composer same panel edges');
   assert.ok(initial.composer.height>=44 && initial.send.height>=44);
   assert.ok(Math.abs(initial.composer.height-initial.send.height)<=2);
   assert.ok(initial.toolbar.bottom<=initial.form.top,'composer below controls');
   // The reversible pause control belongs to Settings, not the APP header.
   await page.locator('#tab-settings').click();
   await page.locator('#settings-connection > summary').click();
   const kill=page.locator('#connection-kill');
   await kill.click();
   assert.equal(await kill.getAttribute('aria-pressed'),'true');
   assert.equal(await page.locator('#connection-status').textContent(),'Paused');
   await page.locator('#tab-ajustes').click();
   assert.equal(await page.locator('#mynode-paused').isVisible(),true);
   assert.equal(await page.locator('#mynode-identity-toggle').evaluate(x=>x.inert),true);
   await page.locator('#tab-modelos').click();
   assert.equal(await page.locator('#openworld-paused').isVisible(),true);
   assert.equal(await page.locator('#openworld-frame').getAttribute('src'),null);
   assert.equal(await page.locator('.openworld-fallback').getAttribute('href'),null);
   await page.locator('#tab-settings').click();
   await kill.click();
   assert.equal(await kill.getAttribute('aria-pressed'),'false');
   assert.equal(await page.locator('#mynode-identity-toggle').evaluate(x=>x.inert),false);
   assert.equal(await page.locator('.openworld-fallback').getAttribute('href'),'https://preceptoros.org/openworld/');
   await page.route('**/api/estado',route=>route.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({estado:'ok',turnos:{turnos:0,consentidos:0}})}));
   await page.evaluate(()=>window.PreceptorConnectionGuard.probe());
   await page.waitForFunction(()=>document.getElementById('connection-status').dataset.state==='CONNECTED');
   assert.equal(await page.locator('#connection-status').textContent(),'Connected');
   assert.deepEqual(errors,[],'JS runtime errors');
   results.push({viewport:viewport.width,header:'PASS',connected_ground_truth:'PASS',
     talk_clean:'PASS',composer:'PASS',kill_pause_resume:'PASS',runtime_errors:0});
   await context.close();
  }
  console.log(JSON.stringify({schema:'preceptoros.app-header-kill/1',status:'PASS',results},null,2));
 } finally {if (browser)await browser.close();server.kill('SIGTERM');}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
