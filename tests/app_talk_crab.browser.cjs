"use strict";
const {chromium}=require("playwright-core");
const assert=require("node:assert/strict");
const url=process.env.PREVIEW_URL||"http://127.0.0.1:18894/app.html";
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',
  args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  for(const width of [360,420,900]){
   const ctx=await browser.newContext({viewport:{width,height:680},serviceWorkers:'block'});
   const page=await ctx.newPage();
   let release;
   const deferred=new Promise(r=>{release=r;});
   const errors=[];page.on('pageerror',e=>errors.push(e.message));
   await page.route('**/api/cerebro',r=>r.fulfill({status:200,contentType:'application/json',
    body:JSON.stringify({estado:'ok',talk_mode:'local_gguf'})}));
   await page.route('**/api/charla',async r=>{
    await deferred;
    await r.fulfill({status:503,contentType:'application/json',body:JSON.stringify({
      estado:'NO_DATA',causa:'synthetic_local_model_unavailable'})});
   });
   await page.goto(url,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!!window.PreceptorPanelFlow);
   await page.evaluate(()=>{
    const task=document.querySelector('#talk-tasks');
    task.textContent='NO_DATA: this task could not be read.';
    task.hidden=false;
   });
   assert.equal(await page.locator('#talk-processing').isHidden(),false);
   assert.equal(await page.locator('#talk-processing').getAttribute('data-state'),'IDLE');
   assert.equal(await page.locator('#talk-processing-label').isHidden(),true);
   await page.locator('#talk-crab-check').click();
   assert.match(await page.locator('#talk-crab-detail').textContent(),/no request in progress/i);
   const dockRect=await page.locator('#talk-processing').boundingBox();
   const composerRect=await page.locator('#form-chat').boundingBox();
   assert.ok(dockRect && composerRect && dockRect.y+dockRect.height<=composerRect.y+1,
     'crab dock must be above Write your answer');
   await page.locator('#dicho').fill('Synthetic question. No real model request.');
   await page.locator('#enviar').click();
   await page.waitForFunction(()=>document.querySelector('#talk-processing')?.dataset.state==='PROCESSING',{timeout:5000});
   const pending=await page.evaluate(()=>{
    const activity=document.querySelector('#talk-processing');
    const track=activity.querySelector('.talk-processing-track');
    const crab=track.querySelector('canvas');
    const pixels=crab.getContext('2d').getImageData(0,0,crab.width,crab.height).data;
    let painted=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i])painted++;
    return {state:activity.dataset.state,acho:activity.dataset.acho,
      hidden:activity.hidden,description:activity.textContent.trim(),
      role:activity.getAttribute('role'),live:activity.querySelector('#talk-processing-label').getAttribute('aria-live'),
      animation:getComputedStyle(track.querySelector('.talk-processing-crab')).animationName,
      width:activity.getBoundingClientRect().width,visibleCrab:!!crab.getClientRects().length,
      crabRenderer:activity.dataset.crabRender,paintedPixels:painted,
      taskText:document.querySelector('#talk-tasks').textContent,
      taskHiddenCss:getComputedStyle(document.querySelector('#talk-tasks')).display};
   });
   assert.equal(pending.hidden,false);
   assert.equal(pending.state,'PROCESSING');assert.equal(pending.acho,'working');
   assert.equal(pending.live,'polite');
   assert.match(pending.description,/Processing your message/);
   assert.equal(pending.animation,'talk-crab-sidestep');
   assert.equal(pending.visibleCrab,true);
   assert.equal(pending.crabRenderer,'atlas');
   assert.ok(pending.paintedPixels>200,'canonical crab must paint actual pixels');
   assert.equal(pending.taskHiddenCss,'none');
   assert.equal(pending.role,'group');
   assert.equal(await page.locator('#talk-processing-label').textContent(),'Processing your message…');
   assert.equal(await page.locator('#talk-processing-label').isHidden(),false);
   await page.locator('#talk-crab-check').click();
   assert.match(await page.locator('#talk-crab-detail').textContent(),/No reply has been verified yet/i);
   assert.match(pending.taskText,/could not be read/);
   release();
   await page.waitForFunction(()=>document.querySelector('#talk-processing')?.dataset.state==='IDLE',undefined,{timeout:10000});
   assert.equal(await page.locator('#talk-processing').isHidden(),false);
   assert.equal(await page.locator('#talk-processing-label').isHidden(),true);
   assert.equal(await page.locator('#talk-processing').getAttribute('data-state'),'IDLE');
   assert.equal(await page.locator('#panel-conversacion').getAttribute('data-thinking'),'false');
   assert.notEqual(await page.locator('#talk-tasks').evaluate(el=>getComputedStyle(el).display),'none');
   assert.deepEqual(errors,[]);
   results.push({width,alwaysVisibleDock:'PASS',canonicalWorldBody:'PASS',animatedWhilePending:'PASS',realErrorPreserved:'PASS',stoppedOnFailure:'PASS',runtimeErrors:0});
   await ctx.close();
  }
  const ctx=await browser.newContext({viewport:{width:420,height:680},reducedMotion:'reduce',serviceWorkers:'block'});
  const page=await ctx.newPage();
  await page.goto(url,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PreceptorPanelFlow);
  await page.waitForFunction(()=>document.querySelector('#talk-processing')?.dataset.crabRender==='atlas');
  assert.equal(await page.locator('#talk-processing').isHidden(),false);
  assert.equal(await page.locator('.talk-processing-crab').evaluate(el=>getComputedStyle(el).animationName),'none');
  await ctx.close();
  results.push({accessibility:'reduced_motion_still_crab_PASS'});
  console.log(JSON.stringify({schema:'preceptoros.talk-crab-processing/1',status:'PASS',results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;});
