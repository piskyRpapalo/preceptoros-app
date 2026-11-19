'use strict';
/* APP-MVP-A0 · browser acceptance for review-only My node and panel controls.
 * No real API writes or public admission; a request draft is NOT a deployed node.
 */
const assert=require('node:assert/strict');
const {chromium}=require('playwright-core');
const URL=process.env.PREVIEW_URL||'http://127.0.0.1:18895/app.html';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',
   args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try{
  for(const width of [360,420,900]){
   const ctx=await browser.newContext({viewport:{width,height:720},serviceWorkers:'block',reducedMotion:'reduce'});
   const page=await ctx.newPage(),posts=[],errors=[];
   page.on('pageerror',e=>errors.push(e.message));
   page.on('request',r=>{if(!['GET','HEAD','OPTIONS'].includes(r.method()))posts.push(r.url());});
   await page.route('https://preceptoros.org/**',r=>r.abort('blockedbyclient'));
   await page.goto(URL,{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>!!window.PreceptorPanelFlow);
   const tabs=['conversacion','cuaderno','lab','ajustes','modelos','settings'];
   const details=[];
   for(const tab of tabs){
    await page.locator('#tab-'+tab).click();
    assert.equal(await page.locator('#tab-'+tab).getAttribute('aria-selected'),'true');
    const part=await page.evaluate(tab=>{
     const panel=document.getElementById('panel-'+tab);
     if(!panel)return {absent:tab};
     const rows=[];
     for(const el of panel.querySelectorAll('details')){
      if(el.hidden || el.closest('[hidden]')) continue;
      const summary=el.querySelector(':scope > summary');
      if(!summary) {rows.push({id:el.id,missingSummary:true});continue;}
      const before=el.open;
      let parent=el.parentElement; while(parent && parent!==panel){ if(parent.tagName==='DETAILS')parent.open=true;parent=parent.parentElement;}
      summary.click();
      rows.push({id:el.id||'(unnamed)',label:summary.textContent.trim().slice(0,80),
         toggled:el.open!==before,
         content:el.textContent.trim().length-summary.textContent.trim().length,
         actionable:el.querySelectorAll('button,input,textarea,select,a[href],form').length});
      el.open=false;
     }
     return {rows};
    },tab);
    assert.ok(!part.absent,'panel '+tab+' exists');
    assert.ok(part.rows.every(r=>r.toggled),'details must toggle for tab '+tab);
    details.push({tab,count:part.rows.length,rows:part.rows});
   }
   await page.locator('#tab-ajustes').click();
   await page.evaluate(()=>document.querySelectorAll('#panel-ajustes details').forEach(x=>x.open=false));
   await page.locator('#mynode-identity-toggle').click();
   const request=page.locator('#node-admission-open');
   assert.equal(await request.isVisible(),true);
   assert.equal(await request.getAttribute('aria-expanded'),'false');
   await request.click();
   assert.equal(await page.locator('#node-identity-advanced').evaluate(x=>x.open),true);
   assert.equal(await request.getAttribute('aria-expanded'),'true');
   assert.equal(await page.evaluate(()=>document.activeElement?.id),'node-registration-name');
   assert.equal(await page.locator('#node-registration-submit').isDisabled(),true);
   assert.equal(posts.length,0,'simply opening node tools cannot submit');
   assert.match(await page.locator('#node-admission-state').textContent(),/Nothing has been sent/);
   assert.equal(await page.locator('#node-admission-state').getAttribute('data-state'),'DRAFT_ONLY');
   assert.ok((await page.locator('#mvp-three-steps li').count())===3);
   assert.equal(await page.locator('#panel-ajustes').evaluate(x=>getComputedStyle(x).display!=='none'),true);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth),false);
   assert.deepEqual(errors,[]);
   const withActions=details.filter(x=>x.tab==='ajustes')[0].rows.filter(x=>x.actionable>0).length;
   results.push({width,panels:tabs.length,accordions:details.reduce((n,v)=>n+v.count,0),
     byPanel:Object.fromEntries(details.map(x=>[x.tab,{accordions:x.count,withActions:x.rows.filter(y=>y.actionable>0).length}])),
     reviewOnlyRows:details.flatMap(x=>x.rows.filter(y=>y.actionable===0&&y.content<160).map(y=>({panel:x.tab,summary:y.label,chars:y.content}))),
     myNodeAccordions:details.find(x=>x.tab==='ajustes').count,withActions,
     guide:'PASS',admissionNoWrite:'PASS',focus:'PASS',errors:0});
   await ctx.close();
  }
  console.log(JSON.stringify({schema:'preceptoros.app-mvp-panel-audit/1',status:'PASS',results},null,2));
 } finally {await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;});
