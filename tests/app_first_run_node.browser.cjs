'use strict';
/* New Android owner's browser journey: no network writes until independent
 * owner authorization; no model/agent execution by navigating the guide. */
const puppeteer=require('/home/pisky/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer');
const assert=require('node:assert/strict');
const url=process.env.PREVIEW_URL||'http://127.0.0.1:18897/app.html';
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:'/usr/bin/google-chrome',
  args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const width of [360,420,900]){
   const ctx=await browser.createBrowserContext();
   const page=await ctx.newPage();await page.setViewport({width,height:720});
   const writes=[],errors=[];
   page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))writes.push(r.url());});
   page.on('pageerror',e=>errors.push(e.message));
   await page.goto(url,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!!window.PreceptorFirstRun);
   assert.equal(await page.$eval('#mvp-first-run',e=>e.hidden),false);
   assert.equal(await page.$$eval('#mvp-first-run ol > li',els=>els.length),3);
   assert.equal(await page.$eval('#mvp-first-run',e=>e.dataset.acho),'GUIDE_ONLY');
   assert.equal(await page.evaluate(()=>localStorage.getItem('preceptoros.node-public-template/1')),null);
   assert.equal(await page.evaluate(()=>localStorage.getItem('preceptoros.app-first-run/1')),null);
   await page.click('#mvp-first-run-mini');
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'mini-local-toggle');
   assert.equal(await page.$eval('#mini-local-toggle',el=>el.getAttribute('aria-pressed')),'false');
   await page.keyboard.press('Escape'); // dismiss existing model selection dialog
   await page.click('#mvp-first-run-node');
   assert.equal(await page.$eval('#tab-ajustes',el=>el.getAttribute('aria-selected')),'true');
   assert.equal(await page.$eval('#ajustes-nodo',el=>el.open),true);
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'node-default-name');
   assert.equal(await page.$eval('#node-default-name',el=>el.value),'My companion');
   const neutral=await page.$eval('#node-default-prompt',el=>el.value);
   assert.ok(neutral.startsWith('You are an experimental PreceptorOS companion.'));
   assert.ok(neutral.includes('Never disclose private information.'));
   assert.equal(writes.length,0);
   assert.equal(await page.evaluate(()=>localStorage.getItem('preceptoros.node-public-template/1')),null);
   await page.$eval('#node-default-name',el=>{el.value='My research companion';el.dispatchEvent(new Event('input',{bubbles:true}));});
   await page.$eval('#node-default-description',el=>{el.value='Helps me research local history with citations.';});
   await page.click('#node-default-id');
   const proposal=await page.$eval('#node-identity-id',el=>el.value);
   assert.match(proposal,/^nodo\.[0-9]{6}\.my-research-companion$/);
   assert.equal(await page.$eval('#node-registration-name',el=>el.value),proposal);
   assert.equal(await page.$eval('#node-default-status',el=>el.dataset.state),'DRAFT_ONLY');
   await page.click('#node-default-id'); // Existing owner ID must be preserved.
   assert.equal(await page.$eval('#node-identity-id',el=>el.value),proposal);
   assert.equal(writes.length,0);
   await page.click('#node-default-save');
   const saved=await page.evaluate(()=>JSON.parse(localStorage.getItem('preceptoros.node-public-template/1')));
   assert.deepEqual(saved,{schema:'preceptoros.node-public-template/1',name:'My research companion',description:'Helps me research local history with citations.',prompt:neutral});
   assert.equal(await page.$eval('#node-default-status',el=>el.dataset.state),'SAVED_LOCAL');
   assert.equal(writes.length,0);
   await page.reload({waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!!window.PreceptorFirstRun);
   assert.equal(await page.$eval('#mvp-first-run',el=>el.hidden),false);
   assert.equal(await page.$eval('#node-default-name',el=>el.value),'My research companion');
   assert.equal(await page.$eval('#node-default-description',el=>el.value),'Helps me research local history with citations.');
   await page.click('#tab-lab');
   await page.click('#lab-first-experiment');
   assert.equal(await page.$eval('#tab-cuaderno',el=>el.getAttribute('aria-selected')),'true');
   assert.equal(await page.$eval('#plan-escribir',el=>el.open),true);
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'plan-titulo');
   assert.equal(writes.length,0);
   await page.click('#tab-conversacion');
   await page.click('#mvp-first-run-finish');
   assert.equal(await page.$eval('#mvp-first-run',el=>el.hidden),true);
   assert.equal(await page.evaluate(()=>localStorage.getItem('preceptoros.app-first-run/1')),'done');
   await page.reload({waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!!window.PreceptorFirstRun);
   assert.equal(await page.$eval('#mvp-first-run',el=>el.hidden),true);
   await page.click('#tab-ajustes');
   await page.click('#mvp-journey-guide > summary');
   await page.click('#mvp-first-run-reopen');
   assert.equal(await page.$eval('#tab-conversacion',el=>el.getAttribute('aria-selected')),'true');
   assert.equal(await page.$eval('#mvp-first-run',el=>el.hidden),false);
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'mvp-first-run-title');
   assert.equal(writes.length,0);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);
   console.log(JSON.stringify({width,guide:'PASS',localMiniOptIn:'PASS',nodeTemplateOwnerOnly:'PASS',suggestedId:'PASS',labOnramp:'PASS',
     persistence:'PASS',reopen:'PASS',networkWrites:0,jsErrors:0}));
   await ctx.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;});
