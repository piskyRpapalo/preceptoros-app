'use strict';
/* Day D room e2e: one local building draft on the actual APP HTTP server.
 * Browser evidence only. Windows/Android physical device = NO_DATA.
 */
const { test } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawn } = require('node:child_process');
const { chromium } = require('playwright-core');
const root = path.resolve(__dirname, '..');
const port = Number(process.env.DAYD_BUILDING_PORT || 18927);
const base = 'http://127.0.0.1:' + port;
async function ready(proc) {
  for (let i=0; i<70; i++) {
    if (proc.exitCode !== null) throw Error('server exited before ready');
    try { if ((await fetch(base+'/app')).ok) return; } catch (_) {}
    await new Promise(r=>setTimeout(r,85));
  }
  throw Error('APP HTTP server did not start');
}

test('one-building draft in a clean browser: 900, 420, 360', { timeout: 120000 }, async ()=>{
  const home = fs.mkdtempSync(path.join(os.tmpdir(),'dayd-building-'));
  const service = spawn('python3',[path.join(root,'bin/preceptoros-pwa')], {
    cwd:root,
    env:{...process.env, HOME:home, PRECEPTOROS_HEXELION_ENDPOINT:'',
      PRECEPTOROS_PWA_PUERTO:String(port), PRECEPTOROS_PWA_BIND:'127.0.0.1'},
    stdio:'ignore',
  });
  let browser;
  try {
    await ready(service);
    browser = await chromium.launch({headless:true,
      executablePath:process.env.CHROME_PATH || '/usr/bin/google-chrome',
      args:['--no-sandbox','--disable-dev-shm-usage']});
    for (const viewport of [{width:900,height:760},{width:420,height:640},{width:360,height:640}]) {
      const context = await browser.newContext({viewport,acceptDownloads:true,serviceWorkers:'block'});
      const page = await context.newPage();
      let effectPosts=0;
      page.on('request',r=>{if(r.method()==='POST' &&
        (r.url().startsWith(base+'/api/') || r.url().includes('github.com'))) effectPosts++;});
      await page.goto(base+'/app',{waitUntil:'domcontentloaded'});
      await page.waitForFunction(()=>!!window.PreceptorCompanionOnboarding?.renderBuildingDraft);
      await page.locator('#tab-ajustes').click();
      assert.equal(await page.locator('#room-building-status').getAttribute('data-state'),'NO_DATA');
      assert.equal(await page.locator('#room-building-status').getAttribute('data-acho'),'NO_DATA');
      assert.equal(await page.locator('#room-building-download').isDisabled(),true);
      const box=page.locator('#room-building');
      await box.scrollIntoViewIfNeeded();
      for(const id of ['#room-building-name','#room-building-purpose','#room-building-create','#room-building-download','#room-building-clear']) {
        const h=await page.locator(id).evaluate(e=>e.getBoundingClientRect().height);
        assert.ok(h>=44, id + ' tap target height '+h);
      }
      const overflow=await box.evaluate(el=>el.scrollWidth-el.clientWidth);
      assert.ok(overflow<=3,'room card overflow '+overflow+'px at '+viewport.width);
      await page.locator('#room-building-name').fill('My Solar Workshop');
      await page.locator('#room-building-purpose').fill('Help neighbors repair their tools');
      await page.locator('#room-building-create').click();
      assert.equal(await page.locator('#room-building-status').getAttribute('data-state'),'DRAFT_ONLY');
      assert.equal(await page.locator('#room-building-status').getAttribute('data-acho'),'DRAFT_ONLY');
      const text=await page.locator('#room-building-draft').textContent();
      assert.match(text,/Schema: preceptoros.room-building-draft\/1/);
      assert.match(text,/Building count: 1/);
      assert.match(text,/NO_DATA\(world_publication_not_verified\)/);
      assert.match(text,/Companion and request review later/);
      assert.equal(effectPosts,0,'no backend write, repo submission, or inbox request');
      const downloaded=page.waitForEvent('download');
      await page.locator('#room-building-download').click();
      const dl=await downloaded;
      assert.equal(await page.locator('#room-building-status').getAttribute('data-cause'),
        'download_started_not_verified_saved');
      assert.match(await page.locator('#room-building-status').textContent(),/download requested/);
      assert.equal(dl.suggestedFilename(),'building-draft-my-solar-workshop.md');
      const localFile=await dl.path();
      const content=fs.readFileSync(localFile,'utf8');
      assert.equal(content,text,'download bytes must match the visible draft');
      await page.locator('#room-building-purpose').fill('sk-abcdefghijklmno');
      assert.equal(await page.locator('#room-building-download').isDisabled(),true);
      await page.locator('#room-building-create').click();
      assert.equal(await page.locator('#room-building-status').getAttribute('data-state'),'NO_DATA');
      assert.equal(await page.locator('#room-building-download').isDisabled(),true);
      await page.locator('#room-building-clear').click();
      assert.equal(await page.locator('#room-building-name').inputValue(),'');
      assert.equal(await page.locator('#room-building-purpose').inputValue(),'');
      assert.equal(effectPosts,0,'no write effects including after validation errors');
      assert.equal(await page.locator('#room-building-name').evaluate(e=>e===document.activeElement),true);
      console.log(JSON.stringify({schema:'preceptoros.room-building-browser/1',viewport,
        result:'PASS',download:'PASS',a11y_tap:'PASS',keyboard_focus:'PASS',
        effects_POST:effectPosts,publication:'NO_DATA(not_submitted)',physical_device:'NO_DATA(not_run)'}));
      await context.close();
    }
  } finally {
    if (browser) await browser.close();
    service.kill('SIGTERM');
    fs.rmSync(home,{recursive:true,force:true});
  }
});
