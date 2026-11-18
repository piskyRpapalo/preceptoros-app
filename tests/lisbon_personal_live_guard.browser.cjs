/* Lisbon Table · observational browser guard against the running APP.
 * No writes are permitted: every attempted POST is intercepted and denied.
 * No private thread reads, no external network, no prompt/body logging.
 * Tests client behavior against actual :8742-served JS + declared brain mode.
 * Not a packet capture and NOT proof of server authorization.
 */
'use strict';
const assert = require('node:assert/strict');
const {chromium}=require('playwright-core');
const base='http://127.0.0.1:8742';
const result={schema:'preceptoros.lisbon.personal-live-guard/1',
  source:'running_rack_app_browser_intercept', external_requests:0,
  attempted_posts:0, private_chat_attempts:0, private_thread_attempts:0,
  reply:'NO_DATA', host_talk_mode:'NO_DATA', user_profile:'NO_DATA'};
(async()=>{
 const controller=new AbortController();
 const brain=await fetch(base+'/api/cerebro',{signal:controller.signal});
 assert.equal(brain.status,200);
 const payload=await brain.json();
 result.host_talk_mode=payload.talk_mode;
 assert.equal(payload.talk_mode,'private_hexelion',
   'this gate must exercise actual private-capable rack mode');
 const browser=await chromium.launch({headless:true,
   executablePath:process.env.CHROME_PATH||'/usr/bin/google-chrome',
   args:['--no-sandbox','--disable-dev-shm-usage']});
 try{
  for (const width of [900,420,360]){
   const ctx=await browser.newContext({viewport:{width,height:740},
    serviceWorkers:'block'});
   const page=await ctx.newPage();
   const attempts=[];
   await page.route('**/*',async(route)=>{
    const r=route.request();
    const u=new URL(r.url());
    if (u.origin!==base){
      result.external_requests++;
      attempts.push('foreign:'+u.origin);
      return route.abort();
    }
    if(r.method()!=='GET'&&r.method()!=='HEAD'){
      result.attempted_posts++;
      if(u.pathname==='/api/hexelion/chat')result.private_chat_attempts++;
      if(u.pathname==='/api/conversacion')result.private_thread_attempts++;
      attempts.push('attempted-write:'+u.pathname);
      return route.fulfill({status:403,contentType:'application/json',
         body:'{"estado":"NO_DATA","causa":"test_intercepted_write"}'});
    }
    if(u.pathname==='/api/conversacion'){
      result.private_thread_attempts++;
      attempts.push('attempted-read:/api/conversacion');
      return route.fulfill({status:403,contentType:'application/json',
         body:'{"estado":"NO_DATA","causa":"test_intercepted_private_read"}'});
    }
    if(u.pathname.startsWith('/api/')&&u.pathname!=='/api/cerebro'&&u.pathname!=='/api/perfil'){
      return route.fulfill({status:404,contentType:'application/json',
         body:'{"estado":"NO_DATA","causa":"private_api_not_read_in_test"}'});
    }
    return route.continue();
   });
   await page.goto(base+'/app',{waitUntil:'domcontentloaded'});
   await page.waitForFunction(()=>window.PreceptorProfile==='personal_mvp',
      null,{timeout:9000});
   const profile=await page.evaluate(()=>window.PreceptorProfile);
   assert.equal(profile,'personal_mvp');
   await page.locator('#dicho').fill('synthetic Lisbon table personal profile proof');
   await page.locator('#form-chat').evaluate(form=>form.requestSubmit());
   await page.waitForFunction(()=>{
     const s=document.getElementById('estado');
     return s?.textContent?.includes('NO_DATA(personal_profile_private_route_denied)');
   },null,{timeout:9000});
   assert.equal(await page.locator('#dicho').inputValue(),
     'synthetic Lisbon table personal profile proof');
   assert.equal(await page.locator('#enviar').isEnabled(),true);
   assert.equal(await page.evaluate(()=>document.activeElement.id),'dicho');
   assert.equal(attempts.length,0,JSON.stringify(attempts));
   // Opt-in mini must not use a private server even when the host advertises it.
   const toggle=page.locator('#mini-local-toggle');
   assert.equal(await toggle.getAttribute('aria-pressed'),'false');
   await toggle.click();
   assert.equal(await toggle.getAttribute('aria-pressed'),'true');
   await page.locator('#dicho').fill('hello');
   await page.locator('#form-chat').evaluate(form=>form.requestSubmit());
   await page.waitForFunction(()=>document.querySelector('#hilo')?.textContent?.includes('Soy MINI-LOCAL'));
   assert.equal(attempts.length,0,JSON.stringify(attempts));
   result.user_profile=profile;
   result.reply='NO_DATA(personal_profile_private_route_denied)';
   console.log(JSON.stringify({width,host_talk_mode:result.host_talk_mode,profile,
     private_chat_attempts:result.private_chat_attempts,
     private_thread_attempts:result.private_thread_attempts,
     external_requests:result.external_requests,
     mini_status:'deterministic',result:'PASS'}));
   await ctx.close();
  }
 }finally{await browser.close()}
 assert.equal(result.attempted_posts,0);
 assert.equal(result.private_thread_attempts,0);
 assert.equal(result.external_requests,0);
 console.log(JSON.stringify(result));
})().catch(e=>{console.error('FAIL '+(e.stack||e));process.exitCode=1;});
