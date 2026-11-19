"use strict";
const {chromium}=require('playwright-core');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'/usr/bin/google-chrome',
  args:['--no-sandbox','--disable-dev-shm-usage']});
 const results=[];
 try {
 for(const viewport of [{width:360,height:640},{width:420,height:680},{width:900,height:900}]){
  const context=await browser.newContext({viewport,serviceWorkers:'block',colorScheme:'light'});
  const page=await context.newPage();
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(process.env.PREVIEW_URL||'http://127.0.0.1:18894/app.html',{waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PreceptorPanelFlow && !!window.PreceptorPreferences);
  const meta=await page.evaluate(()=>{
   const nav=document.querySelector('#pestanas');
   const labels=[...nav.querySelectorAll('[role=tab]')].map(b=>b.getAttribute('aria-label'));
   const settings=document.getElementById('tab-settings');
   const style=getComputedStyle(settings,'::before');
   return {labels, overflow:nav.scrollWidth>nav.clientWidth+1,gear:style.content,
    font:style.fontSize,topStatus:document.querySelector('#connection-status')?.textContent,
    killInsideSettings:!!document.querySelector('#panel-settings #connection-kill'),
    killInHeader:!!document.querySelector('.identidad #connection-kill'),
    allClosed:[...document.querySelectorAll('#panel-settings details')].every(x=>!x.open),
    prefs:window.PreceptorPreferences.get()};
  });
  assert.deepEqual(meta.labels,['Talk','Operations Data','Lab','My node','Open World','Settings']);
  assert.equal(meta.killInsideSettings,true);
  assert.equal(meta.killInHeader,false);
  assert.equal(meta.allClosed,true);
  assert.equal(meta.overflow,false);
  assert.ok(meta.gear.includes('⚙'));
  await page.locator('#tab-settings').click();
  await page.locator('#settings-appearance > summary').click();
  await page.locator('input[name=settings-theme][value=dark]').check();
  const palette=await page.evaluate(()=>({theme:document.documentElement.dataset.theme,
   color:getComputedStyle(document.body).color,
   bg:getComputedStyle(document.body).backgroundColor,
   storage:localStorage.getItem('preceptoros.ui-preferences/1')}));
  assert.equal(palette.theme,'dark');assert.match(palette.storage,/"theme":"dark"/);
  const darkColor=palette.color;
  await page.locator('input[name=settings-theme][value=light]').check();
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'light');
  const lightColor=await page.evaluate(()=>getComputedStyle(document.body).color);
  assert.notEqual(lightColor,darkColor);
  await page.locator('#settings-accessibility > summary').click();
  await page.locator('input[name=settings-text][value=large]').check();
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.textScale),'large');
  await page.locator('#settings-reduce-motion').check();
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.reduceMotion),'true');
  await page.locator('#settings-connection > summary').click();
  await page.locator('#connection-kill').click();
  assert.equal(await page.locator('#connection-kill').getAttribute('aria-pressed'),'true');
  await page.locator('#connection-kill').click();
  assert.equal(await page.locator('#connection-kill').getAttribute('aria-pressed'),'false');
  await page.locator('#settings-about > summary').click();
  await page.locator('#settings-reset').click();
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.textScale),'normal');
  assert.equal(await page.evaluate(()=>window.PreceptorPreferences.get().theme),'light');
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PreceptorPreferences);
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.textScale),'normal');
  assert.equal(await page.evaluate(()=>window.PreceptorPreferences.get().theme),'light');
  await page.locator('#tab-settings').click();
  await page.locator('#settings-appearance > summary').click();
  await page.locator('input[name=settings-theme][value=dark]').check();
  await page.reload({waitUntil:'domcontentloaded'});
  await page.waitForFunction(()=>!!window.PreceptorPreferences);
  assert.equal(await page.evaluate(()=>document.documentElement.dataset.theme),'dark');
  assert.equal(await page.evaluate(()=>window.PreceptorPreferences.get().theme),'dark');
  assert.deepEqual(errors,[]);
  results.push({width:viewport.width,tabs:6,gear:'PASS',theme:'PASS',persist:'PASS',
   text_size:'PASS',reduce_motion:'PASS',kill:'PASS',errors:errors.length});
  await context.close();
 }
 console.log(JSON.stringify({schema:'preceptoros.settings-six-tabs/1',status:'PASS',results},null,2));
 }finally{await browser.close();}
})().catch(e=>{console.error(e.stack||String(e));process.exitCode=1});
