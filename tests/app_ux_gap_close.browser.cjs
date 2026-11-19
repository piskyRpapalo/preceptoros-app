/* Six-tab APP MVP, single-owner Memory, Lab operator groups and collapsed accordions.
 * Static loopback preview: no private API effects, live receipt claims or node admission.
 */
'use strict';
const { chromium } = require('playwright-core');
const assert = require('node:assert/strict');
const { spawn } = require('node:child_process');
const path = require('node:path');
const root = path.resolve(process.env.PREVIEW_ROOT || path.resolve(__dirname, '..'));
const port = Number(process.env.PREVIEW_PORT || 18893);
const url = 'http://127.0.0.1:' + port + '/app.html';

async function ready(child) {
  for (let i = 0; i < 50; i++) {
    if (child.exitCode !== null) throw new Error('isolated preview exited');
    try { if ((await fetch(url)).ok) return; } catch {}
    await new Promise(resolve => setTimeout(resolve, 100));
  }
  throw new Error('preview unavailable');
}

(async () => {
  const server = spawn('python3', ['-m', 'http.server', String(port), '--bind', '127.0.0.1',
    '--directory', path.join(root, 'interface')], { stdio: 'ignore' });
  let browser;
  try {
    await ready(server);
    browser = await chromium.launch({
      headless: true, executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome',
      args: ['--no-sandbox', '--disable-dev-shm-usage'],
    });
    const cases = [];
    for (const viewport of [
      { width: 900, height: 968 }, { width: 420, height: 680 }, { width: 360, height: 640 },
    ]) {
      const context = await browser.newContext({ viewport, serviceWorkers: 'block', reducedMotion: 'reduce' });
      const page = await context.newPage();
      const errors = [];
      page.on('pageerror', e => errors.push(e.message));
      await page.goto(url, { waitUntil: 'domcontentloaded' });
      await page.waitForFunction(() => !!window.PreceptorPanelFlow);
      const structure = await page.evaluate(() => {
        const get = id => document.getElementById(id);
        const panels = [...document.querySelectorAll('[role="tabpanel"]')].map(x => x.id);
        const tabs = [...document.querySelectorAll('#pestanas [role="tab"]')];
        const grouped = ['panel-cuaderno','panel-lab','panel-ajustes'];
        const allClosed = grouped.every(id => [...get(id).querySelectorAll('details')].every(x => !x.open));
        const nest = (parent, child) => get(parent)?.contains(get(child));
        const ids = [...document.querySelectorAll('[id]')].map(x => x.id);
        const duplicateIds = ids.filter((id, at) => ids.indexOf(id) !== at);
        return {
          tabs: tabs.map(x => x.getAttribute('aria-label')),
          panels, allClosed, duplicateIds,
          editorInsideNotebook: nest('panel-cuaderno','notebook-document-editor'),
          memoryInsideNotebook: nest('panel-cuaderno','notebook-memory-group'),
          compassInsideMemory: nest('notebook-memory-group','compass-container'),
          redactionInsideMemory: nest('notebook-memory-group','tarjeta-frontera'),
          boundaryInsideLab: nest('panel-lab','lab-boundary-group'),
          harnessInsideLab: nest('panel-lab','lab-harness-group'),
          loopsInsideLab: nest('panel-lab','lab-loops'),
          nodeContainsIdentity: nest('ajustes-nodo','node-identity-form'),
          nodeContainsBuilding: nest('room-building','room-building-form'),
          noAdvancedControl: !get('advanced-mode-toggle') && !get('technical-options-toggle'),
          noAdvancedTabs: !get('tab-mando') && !get('tab-gobierno') && !get('tab-harness'),
          noDocumentsTab: !get('tab-documentos'),
          worldSandbox: get('openworld-frame').getAttribute('sandbox'),
          worldHref: get('openworld-frame').nextElementSibling?.href,
          menuInTalk: nest('panel-conversacion','modelos-toggle'),
          arrowOverflow: get('pestanas').scrollWidth > get('pestanas').clientWidth + 1,
        };
      });
      assert.deepEqual(structure.tabs, ['Talk','Operations Data','Lab','My node','Open World','Settings']);
      const iconLabels = await page.evaluate(() => {
        const get = id => document.getElementById(id);
        const svg = id => {
          const e = get(id), style = getComputedStyle(e, '::before');
          return { name: e.getAttribute('aria-label'), svg: style.backgroundImage.includes('data:image/svg+xml'),
            w: style.width, h: style.height };
        };
        return {
          pictures: ['tab-conversacion', 'tab-cuaderno', 'tab-lab', 'tab-ajustes'].map(svg),
          globe: getComputedStyle(get('tab-modelos'), '::before').content,
          world: get('tab-modelos').getAttribute('aria-label'),
          title: get('tab-modelos').getAttribute('title'),
          heading: get('h-modelos').textContent,
        };
      });
      assert.deepEqual(iconLabels.pictures.map(x => x.name),
        ['Talk','Operations Data','Lab','My node']);
      assert.ok(iconLabels.pictures.every(x => x.svg && x.w === '28px' && x.h === '28px'));
      assert.equal(iconLabels.globe, '"🌐"');
      assert.deepEqual([iconLabels.world, iconLabels.title, iconLabels.heading],
        ['Open World','Open World','Open World']);

      assert.deepEqual(structure.panels, ['panel-conversacion','panel-cuaderno','panel-lab','panel-modelos','panel-ajustes','panel-settings']);
      assert.deepEqual(structure.duplicateIds, []);
      assert.equal(structure.allClosed, true);
      for (const key of ['editorInsideNotebook','memoryInsideNotebook','compassInsideMemory',
        'redactionInsideMemory','boundaryInsideLab','harnessInsideLab','loopsInsideLab',
        'nodeContainsIdentity','nodeContainsBuilding','noAdvancedControl','noAdvancedTabs',
        'noDocumentsTab','menuInTalk']) assert.equal(structure[key], true, key);
      assert.equal(structure.arrowOverflow, false);
      assert.ok(structure.worldSandbox.includes('allow-scripts'));
      assert.ok(structure.worldHref.includes('preceptoros.org/openworld/'));

      // A second row is the sole home for interactive panel actions.
      // The controls match width, height and shape, even on 360px.
      async function checkRow(id, panel, labels, firstReading) {
        const row = page.locator('#' + id);
        await page.waitForTimeout(350);
        const state = await row.evaluate(el => {
          const p = el.closest('[role="tabpanel"]');
          const box = e => {
            const r = e.getBoundingClientRect();
            return { top:r.top,bottom:r.bottom,width:r.width,height:r.height };
          };
          const bs = [...el.children].filter(x =>
            x.tagName === 'BUTTON' || x.classList.contains('talk-model-picker'))
            .map(x => x.matches('button') ? x : x.querySelector('#modelos-toggle'));
          return {
            panel:p.id, headerBottom:box(p.querySelector(':scope > header')).bottom,
            actionTop:box(el).top,actionBottom:box(el).bottom,
            firstReadTop:box(p.querySelector('#' + el.dataset.firstRead) || document.getElementById(el.dataset.firstRead)).top,
            buttons:bs.map(x => ({text:x.textContent.trim(),...box(x),
              radius:getComputedStyle(x).borderRadius}))
          };
        }).catch(e => { console.error('ACTION_ROW_EVALUATION_ERROR',id,e.message);return null; });
        assert.ok(state, id + ' exists');
        assert.equal(state.panel,panel);
        assert.ok(state.actionTop >= state.headerBottom-2,'actions follow title: '+id);
        assert.ok(state.actionBottom <= state.firstReadTop+3,'actions precede reading: '+id);
        assert.deepEqual(state.buttons.map(x=>x.text),labels);
        assert.ok(state.buttons.every(x=>x.height >= 44),'44px targets: '+id);
        assert.ok(Math.max(...state.buttons.map(x=>x.height))-
          Math.min(...state.buttons.map(x=>x.height))<=2,'equal height: '+id);
        assert.ok(Math.max(...state.buttons.map(x=>x.width))-
          Math.min(...state.buttons.map(x=>x.width))<=2,'equal width: '+id);
        assert.ok(state.buttons.every(x=>x.radius===state.buttons[0].radius),'equal radius: '+id);
      }
      await page.locator('#talk-actions').evaluate(el=>el.dataset.firstRead='form-chat');
      await checkRow('talk-actions','panel-conversacion',['Choose model','Refresh'],'conv-interlocutor');
      await page.locator('#modelos-toggle').click();
      assert.equal(await page.locator('#modelos-menu').isVisible(),true);
      await page.locator('#modelos-toggle').click();
      assert.equal(await page.locator('#modelos-menu').isHidden(),true);

      // Keyboard follows the actual public tab order.
      await page.locator('#tab-conversacion').focus();
      for (const tab of ['cuaderno','lab','ajustes','modelos']) {
        await page.keyboard.press('ArrowRight');
        assert.equal(await page.locator('#tab-' + tab).getAttribute('aria-selected'), 'true');
      }
      await page.keyboard.press('ArrowLeft');
      assert.equal(await page.locator('#tab-ajustes').getAttribute('aria-selected'), 'true');

      await page.locator('#mynode-actions').evaluate(el=>el.dataset.firstRead='ajustes-estado');
      await checkRow('mynode-actions','panel-ajustes',['Node identity','Create building','Refresh'],'ajustes-nodo');
      await page.locator('#mynode-identity-toggle').click();
      assert.equal(await page.locator('#ajustes-nodo').evaluate(el=>el.open), true);
      assert.equal(await page.locator('#mynode-identity-toggle').getAttribute('aria-expanded'),'true');
      await page.locator('#mynode-identity-toggle').click();
      await page.locator('#mynode-building-toggle').click();
      assert.equal(await page.locator('#room-building').evaluate(el=>el.open),true);
      await page.locator('#mynode-building-toggle').click();

      // Explicit Refresh is a GET-only identity reading, never node admission.
      let identityReadMethod = null;
      await page.route('**/api/nodo/identity',route => {
        identityReadMethod = route.request().method();
        return route.fulfill({status:200,contentType:'application/json',
          body:JSON.stringify({estado:'configurada',node_id:'synthetic-test-only'})});
      });
      await page.locator('#mynode-actions > button.refrescar').click();
      await page.waitForFunction(()=>document.getElementById('ajustes-estado').dataset.state==='MEASURED');
      assert.equal(identityReadMethod,'GET');
      assert.match(await page.locator('#ajustes-estado').textContent(),/not.*LIVE node/);

      // My node is fully closed by default, even its identity/building/setup details.
      for (const id of ['ajustes-nodo','room-building','ajustes-dispositivo','mvp-journey-guide'])
        assert.equal(await page.locator('#'+id).evaluate(el=>el.open), false, id);
      await page.locator('#ajustes-nodo > summary').click();
      assert.equal(await page.locator('#ajustes-nodo').evaluate(el=>el.open), true);
      assert.equal(await page.locator('#node-identity-advanced').evaluate(el=>el.open), false);
      await page.locator('#ajustes-nodo > summary').click();

      await page.locator('#tab-cuaderno').click();
      await page.locator('#notebook-actions').evaluate(el=>el.dataset.firstRead='notebook-subtitle');
      await checkRow('notebook-actions','panel-cuaderno',
        ['Document Editor','Write a plan','Refresh'],'notebook-memory-group');
      await page.locator('#notebook-plan-toggle').click();
      assert.equal(await page.locator('#plan-escribir').evaluate(el=>el.open),true);
      assert.equal(await page.locator('#notebook-plan-toggle').getAttribute('aria-expanded'),'true');
      await page.locator('#plan-titulo').fill('Synthetic plan – not stored');
      await page.locator('#notebook-plan-toggle').click();
      assert.equal(await page.locator('#plan-escribir').evaluate(el=>el.open),false);

      // Notebook owns Memory, whose private memory/compass is itself a further disclosure.
      await page.locator('#tab-cuaderno').click();
      assert.equal(await page.locator('#notebook-memory-group').evaluate(el=>el.open), false);
      await page.locator('#notebook-memory-group > summary').click();
      assert.equal(await page.locator('#notebook-memory-group').evaluate(el=>el.open), true);
      assert.equal(await page.locator('#command-memory-management').evaluate(el=>el.open), false);
      assert.ok(await page.locator('#compass-container').count());
      await page.locator('#notebook-memory-group > summary').click();
      assert.equal(await page.locator('#notebook-memory-group').evaluate(el=>el.open), false);

      // One document editor backed by the original browser store.
      const editorBtn = page.locator('#notebook-document-editor-toggle');
      assert.equal(await editorBtn.getAttribute('aria-expanded'),'false');
      await editorBtn.click();
      assert.equal(await page.locator('#notebook-document-editor').isVisible(), true);
      await page.locator('#documentos-nuevo-btn').click();
      await page.locator('#documentos-titulo').fill('MVP test note');
      await page.locator('#documentos-contenido').fill('Synthetic proof; no sensitive data');
      await page.locator('#documentos-guardar').click();
      const files = await page.evaluate(() => {
        const items = [];
        for (let i=0; i<localStorage.length; ++i) {
          const key=localStorage.key(i);
          if (key && key.includes('document')) items.push({key,value:localStorage.getItem(key)});
        }
        return items;
      });
      assert.equal(files.length, 1);
      assert.ok(files[0].value.includes('MVP test note'));
      await editorBtn.click();
      assert.equal(await page.locator('#notebook-document-editor').isHidden(), true);

      await page.locator('#tab-lab').click();
      await page.locator('#lab-actions').evaluate(el=>el.dataset.firstRead='lab-estado');
      await checkRow('lab-actions','panel-lab',['Benchmarks','Refresh'],'lab-runs-status');
      await page.locator('#lab-bench-toggle').click();
      assert.equal(await page.locator('#lab-bench-group').evaluate(el=>el.open),true);
      await page.locator('#lab-bench-toggle').click();
      assert.equal(await page.locator('#lab-bench-group').evaluate(el=>el.open),false);

      // Lab owns both operators, each explicitly opened.
      await page.locator('#tab-lab').click();
      for (const id of ['lab-loops-group','lab-boundary-group','lab-harness-group']) {
        assert.equal(await page.locator('#'+id).evaluate(el=>el.open),false);
        await page.locator('#'+id+' > summary').click();
        assert.equal(await page.locator('#'+id).evaluate(el=>el.open),true);
        await page.locator('#'+id+' > summary').click();
        assert.equal(await page.locator('#'+id).evaluate(el=>el.open),false);
      }
      assert.deepEqual(errors,[], 'client exceptions');
      cases.push({ viewport, tabs:structure.tabs, all_sections_closed:true,
        memory_and_lab_groups:'PASS', documents_storage:'PASS',
        world_embed:'DOM only; NO_DATA(external_frame_not_checked)',
        screen_reader:'NO_DATA(manual_AT_not_run)' });
      await context.close();
    }
    console.log(JSON.stringify({ schema:'preceptoros.app-ux-five-tabs/2',status:'PASS',
      browser:'Chromium',cases },null,2));
  } finally {
    if (browser) await browser.close();
    server.kill('SIGTERM');
  }
})().catch(error=>{console.error(error.stack||error);process.exitCode=1});
