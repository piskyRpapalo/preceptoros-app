"use strict";
const assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
const url=process.env.PREVIEW_URL||'http://127.0.0.1:18894/app.html';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',
  args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  for(const width of [390,420,1280]){
   const context=await browser.newContext({viewport:{width,height:820},serviceWorkers:'block'});
   const page=await context.newPage(),errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(url,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>document.querySelector('#talk-processing')?.dataset.crabRender==='atlas',{timeout:7500});
   const state=await page.evaluate(()=>{
     const composer=document.querySelector('#form-chat').getBoundingClientRect();
     const track=document.querySelector('.talk-processing-track').getBoundingClientRect();
     const crab=document.querySelector('.talk-processing-crab').getBoundingClientRect();
     const label=document.querySelector('#app-installed-version');
     const link=document.querySelector('#node0-public-chat');
     const style=getComputedStyle(document.querySelector('.talk-processing-crab'));
     return {composer:{x:composer.x,w:composer.width},track:{x:track.x,w:track.width},
      crab:{x:crab.x,w:crab.width},animation:style.animationName,animationDirection:style.animationDirection,
      labelText:label.textContent.trim(),labelState:label.dataset.state,labelAcho:label.dataset.acho,
      href:link.getAttribute('href'),target:link.target,rel:link.rel,linkCount:document.querySelectorAll('#node0-public-chat').length,
      panelCount:document.querySelectorAll('.panel[role=tabpanel]').length,
      scrollWidth:document.documentElement.scrollWidth};
   });
   assert.equal(state.linkCount,1);
   assert.equal(state.panelCount,6);
   assert.equal(state.href,'https://preceptoros.org/openworld/?go=hexelion');
   assert.equal(state.target,'_blank');
   assert.match(state.rel,/noopener/);
   assert.match(state.rel,/noreferrer/);
   assert.ok(state.track.w<=state.composer.w+1, 'crab track does not exceed composer');
   assert.ok(state.track.x>=state.composer.x-1,'crab track starts within composer');
   assert.equal(state.animation,'talk-crab-sidestep');
   assert.equal(state.animationDirection,'alternate');
   assert.match(state.labelText,/APK NO_DATA\(not_native_android\)/);
   assert.equal(state.labelState,state.labelAcho);
   assert.ok(state.scrollWidth<=width+1, 'no horizontal overflow width='+width);
   await page.locator('#tab-modelos').click();
   await page.locator('#node0-public-chat').waitFor({state:'visible'});
   const link=await page.locator('#node0-public-chat').boundingBox();
   assert.ok(link.width>=44 && link.height>=44);
   assert.deepEqual(errors,[]);
   results.push({width,status:'PASS',noHorizontalOverflow:true,crabFullComposer:true,node0PublicOnly:true});
   await context.close();
  }
  const context=await browser.newContext({viewport:{width:420,height:820},reducedMotion:'reduce',serviceWorkers:'block'});
  const page=await context.newPage();
  await page.goto(url,{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>document.querySelector('#talk-processing')?.dataset.crabRender==='atlas',{timeout:7500});
  const animation=await page.locator('.talk-processing-crab').evaluate(el=>getComputedStyle(el).animationName);
  assert.equal(animation,'none','motion reduced');
  await context.close();
  console.log(JSON.stringify({schema:'preceptoros.app11-ui-p0-browser/1',results,reducedMotion:'PASS'}));
 }finally{await browser.close()}
})().catch(err=>{console.error(err.stack||String(err));process.exitCode=1;});
