'use strict';
// Agents dot: activity truth and visual compactness, including references-only plans.
const puppeteer=require('/home/pisky/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer');
const assert=require('node:assert/strict');
const base=process.env.PREVIEW_URL||'http://127.0.0.1:18896/app.html';
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:'/usr/bin/google-chrome',
  args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for(const width of [360,420,900]){
   const ctx=await browser.createBrowserContext();
   for(const synthetic of [false,true]){
    const page=await ctx.newPage();
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.setViewport({width,height:720});
    await page.goto(base+(synthetic?'?plan=synthetic':''),{waitUntil:'domcontentloaded'});
    await page.waitForFunction(()=>window.PreceptorSuperbotTalk && (
      !location.search.includes('synthetic') ||
      document.getElementById('superbot-agent-disclosure')?.dataset.state==='SYNTHETIC'
    ));
    const proof=await page.evaluate(()=>{
     const d=document.getElementById('superbot-agent-disclosure'),
       summary=d.querySelector('summary'),dot=document.getElementById('superbot-agent-status-dot'),
       names=document.getElementById('superbot-agent-names'),
       text=document.getElementById('superbot-agent-count'),
       header=document.querySelector('#panel-conversacion > .superbot-panel-header'),
       h=document.getElementById('superbot-title'),
       css=getComputedStyle(d),ds=getComputedStyle(dot),ss=getComputedStyle(summary),ts=getComputedStyle(text),
       borderWidth=css.borderTopWidth;
     const guide=document.createElement('span');guide.style.background='var(--stop)';document.body.appendChild(guide);
     const red=getComputedStyle(guide).backgroundColor;
     guide.style.background='var(--ok)';const green=getComputedStyle(guide).backgroundColor;guide.remove();
     const status={dot:ds.backgroundColor,red,green,names:names.textContent,
       summaryBackground:ss.backgroundColor,borderWidth,
       hiddenText:ts.position==='absolute'&&ts.width==='1px',
       label:text.textContent,accessible:summary.getAttribute('aria-labelledby')==='superbot-agent-count',
       headerHeight:Math.round(header.getBoundingClientRect().height),
       overflow:document.documentElement.scrollWidth>innerWidth,
       title:h.textContent.trim(),listed:[...document.querySelectorAll('.superbot-heading h3')].length};
     if(d.dataset.state!=='VERIFIED_ACTIVE')status.redByDefault=ds.backgroundColor===red;
     return status;
    });
    assert.equal(proof.title,'Agents');assert.equal(proof.listed,1);
    assert.equal(proof.redByDefault,true);assert.equal(proof.borderWidth,'0px');
    assert.equal(proof.hiddenText,true);assert.equal(proof.accessible,true);
    assert.equal(proof.overflow,false);assert.ok(proof.headerHeight<=48,'Agents should use one compact row');
    if(synthetic){
      assert.ok(proof.names.includes('claude') && proof.names.includes('codex'));
      assert.ok(proof.label.includes('agents referenced'));
      assert.equal(proof.dot,proof.red,'synthetic agent references cannot count as live activity');
      await page.click('#superbot-agent-disclosure > summary');
      assert.equal(await page.$$eval('#superbot-agent-tabs [role=tab]',arr=>arr.length),5);
      const green=await page.evaluate(()=>{
       const d=document.getElementById('superbot-agent-disclosure');
       const dot=document.getElementById('superbot-agent-status-dot');
       d.dataset.state='VERIFIED_ACTIVE';return getComputedStyle(dot).backgroundColor;
      });
      assert.equal(green,proof.green,'green presentation requires explicit verified activity state');
    }else{
      assert.equal(proof.names,'Not connected');
      assert.ok(proof.label.includes('not connected'));
    }
    assert.deepEqual(errors,[]);
    console.log(JSON.stringify({width,fixture:synthetic?'synthetic_refs':'no_verified_activity',
      dot:'red',visualLabelAbsent:true,names:proof.names,oneRow:true,accessible:true,errors:0}));
    await page.close();
   }
   await ctx.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1;});
