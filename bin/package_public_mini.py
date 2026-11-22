#!/usr/bin/env python3
"""Deterministic public-safe projection of the EXISTING six-panel PreceptorOS APP.

Consumes source APP HTML + the shared Android MINI/router. Does not create a
second product/backend. Deliberately excludes private-rack scripts and APIs.
Build only: no network, model downloads, deployment or signing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "interface"
OUT = ROOT / "dist" / "public-mini-app"
FILES = {
    "app.css": SOURCE / "app.css",
    "documents.js": SOURCE / "documents.js",
    "owner_model_slots.js": SOURCE / "owner_model_slots.js",
    "companion_onboarding.js": SOURCE / "companion_onboarding.js",
    "node_registration.js": SOURCE / "node_registration.js",
    "mini_project_guide.js": SOURCE / "mini_project_guide.js",
    "mini_recovery.js": SOURCE / "mini_recovery.js",
    "mvp_first_run.js": SOURCE / "mvp_first_run.js",
    "superbot_talk.js": SOURCE / "superbot_talk.js",
    "talk_crab_canvas.js": SOURCE / "talk_crab_canvas.js",
    "face/bubble/openworld_crab_body.js": SOURCE / "face/bubble/openworld_crab_body.js",
    # IMPORTANT: unchanged single source router shared with Android:
    "offline_mini.js": ROOT / "mvp-android" / "offline_mini.js",
    "assets/icono-192.png": ROOT / "assets" / "icono-192.png",
    "assets/icono-512.png": ROOT / "assets" / "icono-512.png",
    "assets/icono-512-maskable.png": ROOT / "assets" / "icono-512-maskable.png",
}

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def extract(source: str, tag: str, element_id: str) -> str:
    start_re = re.compile(r"<" + tag + r"\b[^>]*\bid=[\"']" + re.escape(element_id) + r"[\"'][^>]*>", re.I | re.S)
    matches = list(start_re.finditer(source))
    if len(matches) != 1:
        raise ValueError(f"missing_or_duplicate_APP_element:{tag}:{element_id}:{len(matches)}")
    start = matches[0].start()
    tokens = re.compile(r"</?" + tag + r"\b[^>]*>", re.I)
    depth = 0
    for token in tokens.finditer(source, start):
        if token.group().startswith("</"):
            depth -= 1
            if depth == 0:
                return source[start:token.end()]
        else:
            depth += 1
    raise ValueError(f"unbalanced_APP_element:{element_id}")

def node_section(source: str) -> str:
    anchor = source.index('id="node-registration-title"')
    starts = list(re.finditer(r"<section\b[^>]*>", source[:anchor], re.I))
    if not starts:
        raise ValueError("node_section_missing")
    start = starts[-1].start()
    # Extract from opening section by balancing sections.
    remainder = source[start:]
    tokens = re.compile(r"</?section\b[^>]*>", re.I)
    depth = 0
    for token in tokens.finditer(remainder):
        if token.group().startswith("</"):
            depth -= 1
            if depth == 0:
                return remainder[:token.end()]
        else:
            depth += 1
    raise ValueError("node_section_unbalanced")

def shell(source: str) -> str:
    # Preserve only selected owner-local components from the approved APP.
    # Pull from the real HTML rather than maintaining a second documents editor.
    docs = extract(source, "section", "notebook-document-editor")
    docs = re.sub(r'(<section\b[^>]*\bid="notebook-document-editor"[^>]*?)\s+hidden(?=[\s>])', r'\1', docs, count=1)
    intro = extract(source, "section", "mvp-first-run")
    agent_disclosure = extract(source, "details", "superbot-agent-disclosure")
    node_template = extract(source, "section", "node-public-template")
    mini_recover = extract(source, "section", "mini-recovery")
    node_identity_form = extract(source, "form", "node-identity-form")
    crab = extract(source, "div", "talk-processing")
    talk_input = extract(source, "form", "form-chat")
    talk_input = talk_input.replace("Use an @panel tag to route a question, @ayuda for local temporary help, or @name to address a preceptor in the shared thread.",
        "Ask the deterministic MINI about these four zones. No downloaded language model or rack connection is required.")
    talk_input = talk_input.replace("Lo que dices", "Your message").replace("Escribe tu respuesta…", "Ask MINI locally…").replace(">Dilo</button>", ">Send</button>")
    thread = extract(source, "ol", "hilo").replace("Shared thread: you, Hexelion and the rack preceptors", "Your local MINI conversation")
    node = node_section(source)
    if 'id="node-registration-purpose"' not in node or 'Sign deployment' not in node:
        raise ValueError("APP_344_preliminary_node_UI_not_found")
    tabs=("conversacion","cuaderno","lab","ajustes","modelos","settings")
    if "role=\"tab\"" not in source:
        raise ValueError("APP_six_panel_tab_roles_missing")
    for key in tabs:
        if len(re.findall(r'id="tab-'+key+r'"', source))!=1 or len(re.findall(r'id="panel-'+key+r'"',source))!=1:
            raise ValueError("APP_six_panel_identity_changed:"+key)
    if len(re.findall(r'id="tab-(?:conversacion|cuaderno|lab|ajustes|modelos|settings)"',source)) != 6:
        raise ValueError("APP_six_panel_count_changed")
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#152c38">
<meta name="description" content="PreceptorOS APP · six-panel public-safe deterministic projection; not a native Android APK.">
<link rel="manifest" href="./manifest.webmanifest">
<link rel="stylesheet" href="./app.css">
<link rel="stylesheet" href="./public-mini.css">
<title>PreceptorOS APP · local projection</title>
</head>
<body class="public-mini">
<header class="mini-head">
  <h1>PreceptorOS APP</h1>
  <p>This public-safe view of the approved six-panel APP uses the shared deterministic Mini Orchestrator.
  It is not the Android APK or a running Companion; owner data stays in this browser until explicit action.</p>
  <p id="mini-offline-badge" role="status" aria-live="polite" data-state="DETERMINISTIC_ONLY" data-acho="DETERMINISTIC_ONLY">DETERMINISTIC_ONLY · local guide ready</p>
  <nav class="pestanas" role="tablist" aria-label="Six PreceptorOS panels">
    <button id="tab-conversacion" type="button" role="tab" aria-controls="panel-conversacion" aria-selected="true">Talk</button>
    <button id="tab-cuaderno" type="button" role="tab" aria-controls="panel-cuaderno" aria-selected="false">Operations Data</button>
    <button id="tab-lab" type="button" role="tab" aria-controls="panel-lab" aria-selected="false">Lab</button>
    <button id="tab-ajustes" type="button" role="tab" aria-controls="panel-ajustes" aria-selected="false">My node</button>
    <button id="tab-modelos" type="button" role="tab" aria-controls="panel-modelos" aria-selected="false">Open World</button>
    <button id="tab-settings" type="button" role="tab" aria-controls="panel-settings" aria-selected="false">Settings</button>
  </nav>
</header>
<main id="public-mini-main">
<section class="panel" id="panel-conversacion" role="tabpanel" aria-labelledby="tab-conversacion" tabindex="0">
  <header class="panel-cabecera superbot-panel-header"><h2 class="sr">Talk</h2><h3>Agents</h3>
  """ + agent_disclosure + """
  </header>
  """ + intro + """
  <div class="talk-model-picker">
    <button id="modelos-toggle" type="button" aria-expanded="false" aria-controls="modelos-menu">Mini Orchestrator · local</button>
    <div id="modelos-menu" role="dialog" aria-label="Mini Orchestrator" hidden>
      <button id="mini-local-toggle" type="button" aria-pressed="true">Mini Orchestrator deterministic mode</button>
      <p id="mini-local-mode-status" role="status" aria-live="polite" data-state="DETERMINISTIC_ONLY" data-acho="DETERMINISTIC_ONLY">
        Deterministic routing is active. Experimental model generation: NO_DATA(no_native_runtime_in_public_projection).
      </p>
    </div>
  </div>
  <p>Ask MINI: “help”, “open Operations Data”, “status”. Unsupported model generation fails closed.</p>
  <button id="mini-start-project" type="button" class="probar">Create project</button>
  <section class="tarjeta" aria-labelledby="mini-guide-heading">
    <h3 id="mini-guide-heading">Ask how this MINI works</h3>
    <form id="mini-guide-form">
      <label for="mini-guide-ask">Question about projects, sources, documents, models or deployment</label>
      <input id="mini-guide-ask" maxlength="240" autocomplete="off" required>
      <button type="submit">Ask from local sources</button>
    </form>
    <p id="mini-guide-answer" role="status" aria-live="polite" data-state="NO_DATA" data-acho="NO_DATA">Local sources are in the APP code and the referenced publications, not an LLM.</p>
  </section>
  <ol class="hilo" id="hilo" aria-live="polite" aria-label="Local MINI conversation"></ol>
</section>
<section class="panel" id="panel-cuaderno" role="tabpanel" aria-labelledby="tab-cuaderno" tabindex="0" hidden>
  <header class="panel-cabecera"><h2>Operations Data</h2></header>
  <p>Documents are stored only when you choose Save. Browser storage is not encrypted. Do not place secrets here.</p>
""" + docs + """
</section>
<section class="panel" id="panel-lab" role="tabpanel" aria-labelledby="tab-lab" tabindex="0" hidden>
  <h2>Lab · create your project</h2>
  <p>Follow the six steps. Each project is editable; source links are references only, not downloaded or indexed documents.</p>
  <p id="lab-mini-recovery-state" role="status" aria-live="polite" data-state="NO_DATA" data-acho="NO_DATA" data-cause="no_previous_recovery">NO_DATA(no_previous_recovery). No local Mini project restored.</p>
  <section class="tarjeta" id="mini-project-guide">
    <h3>Create project → Describe purpose → Add documents → Review project → Configure AI → My node</h3>
    <label for="mini-project-template">Optional editable example</label>
    <select id="mini-project-template">
      <option value="custom">My own project</option>
      <option value="law">European AI &amp; Software Law</option>
      <option value="fairness">Digital Fairness Observatory</option>
    </select>
    <form id="mini-project-form">
      <label for="mini-project-title">Project name</label>
      <input id="mini-project-title" required maxlength="80" autocomplete="off">
      <label for="mini-project-purpose">Purpose</label>
      <textarea id="mini-project-purpose" required maxlength="600" rows="3"></textarea>
      <label for="mini-project-description">Description</label>
      <textarea id="mini-project-description" required maxlength="3000" rows="4"></textarea>
      <button type="submit" id="mini-project-save">Save project locally</button>
    </form>
    <p id="mini-project-status" role="status" aria-live="polite" data-state="DRAFT_ONLY" data-acho="DRAFT_ONLY">No project saved yet.</p>
    <ol id="mini-project-steps" aria-label="Your six project steps"></ol>
    <div class="mini-guide-actions">
      <button id="mini-to-documents" type="button">Add documents</button>
      <button id="mini-project-refresh" type="button">Refresh progress</button>
      <button id="mini-project-review" type="button" disabled>Review project</button>
      <button id="mini-project-export" type="button" disabled>Export project and documents</button>
      <button id="mini-to-node" type="button">My node</button>
    </div>
    <p id="mini-model-status" role="status" aria-live="polite" data-state="DETERMINISTIC_ONLY" data-acho="DETERMINISTIC_ONLY">DETERMINISTIC_ONLY</p>
    <pre id="mini-project-review-text" tabindex="0" aria-label="Local project review"></pre>
    <details><summary>Sources and limitations</summary>
      <p>Sources are versioned links to official publications. No remote document is fetched without your action.</p>
      <ul>
      <li><a href="https://eur-lex.europa.eu/eli/reg/2024/1689/oj/eng" target="_blank" rel="noopener noreferrer">AI Act · 2024 original OJ</a></li>
      <li><a href="https://eur-lex.europa.eu/eli/reg/2022/2065/oj/eng" target="_blank" rel="noopener noreferrer">Digital Services Act · 2022 original OJ</a></li>
      <li><a href="https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52024SC0245" target="_blank" rel="noopener noreferrer">Commission Digital Fairness fitness check · 2024</a></li>
      </ul>
      <p>Legal interpretation: NO_DATA(model_not_verified). LAB DFA benchmark receipts: NO_DATA(not_bundled).</p>
    </details>
  </section>
</section>
<section class="panel" id="panel-ajustes" role="tabpanel" aria-labelledby="tab-ajustes" tabindex="0" hidden>
  <header class="panel-cabecera"><h2>My node</h2></header>
  <p>Your Companion belongs to you. A local draft is never a verified or publicly admitted node.</p>
  <button id="mvp-first-run-reopen" type="button">Show three-step introduction again</button>
  <details id="ajustes-nodo" open><summary><h3>Node identity</h3></summary>
  """ + node_template + mini_recover + """
  <p>The suggested ID below is not unique, signed or deployed. Local provisioning is unavailable in this static preview.</p>
  """ + node_identity_form + """
  <p id="node-identity-status" role="status" aria-live="polite" data-state="DRAFT_ONLY" data-acho="DRAFT_ONLY">Local suggestion only. No registration request sent.</p>
  """ + node + """
  </details>
  <details><summary>Model preferences (local draft)</summary><div id="owner-model-slots-mount"></div></details>
  <p role="note">Admission requires the authorized Android bridge, a signed owner review and a verified heartbeat. NO_DATA(native_intake_not_connected).</p>
</section>
<section class="panel" id="panel-modelos" role="tabpanel" aria-labelledby="tab-modelos" tabindex="0" hidden>
  <header class="panel-cabecera"><h2>Open World</h2></header>
  <p>Explore as a visitor without registering your Companion. Nothing from this device is published here automatically.</p>
  <a id="openworld-visit" href="https://preceptoros.org/openworld/" target="_blank" rel="noopener noreferrer">Explore public Open World (requires your action and connection)</a>
  <p id="openworld-visit-status" role="status" aria-live="polite" data-state="READY" data-acho="READY">OpenWorld visitor access starts only after you select the link. No account or node is created.</p>
  <p role="status" data-state="NO_DATA" data-acho="NO_DATA" data-cause="admission_not_verified">NO_DATA(signed_companion_admission_not_verified). Your Companion is not LIVE.</p>
</section>
<section class="panel" id="panel-settings" role="tabpanel" aria-labelledby="tab-settings" tabindex="0" hidden>
  <header class="panel-cabecera"><h2>Settings</h2></header>
  <p>Local accessibility preferences apply only to this projection. No sound plays automatically.</p>
  <button id="mini-text-large" type="button" aria-pressed="false">Larger text</button>
  <button id="mini-contrast-toggle" type="button" aria-pressed="false">High contrast</button>
  <button id="mini-reduced-motion" type="button" aria-pressed="false">Reduce motion</button>
  <button id="mini-speech-stop" type="button">Stop speech</button>
  <p role="status" id="mini-settings-status" data-state="READY" data-acho="READY" aria-live="polite">Settings ready. Sound is off.</p>
</section>
</main>
<div class="mini-compose">
""" + talk_input + """
</div>
""" + crab + """
<script>window.PreceptorMiniBrowserEnabled=true;window.PreceptorProfile='personal_mvp';</script>
<script src="./face/bubble/openworld_crab_body.js"></script>
<script src="./talk_crab_canvas.js"></script>
<script src="./companion_onboarding.js"></script>
<script src="./documents.js"></script>
<script src="./owner_model_slots.js"></script>
<script src="./node_registration.js"></script>
<script src="./mini_project_guide.js"></script>
<script src="./mini_recovery.js"></script>
<script src="./offline_mini.js"></script>
<script src="./mvp_first_run.js"></script>
<script src="./superbot_talk.js"></script>
<script src="./public-boot.js"></script>
</body>
</html>
"""

BOOT = r"""/* Thin six-panel adapter for the EXISTING APP's owner-safe local modules.
 * No backend, network client, model download, remote registration or second app.
 */
(function () {
 'use strict';
 const id=x=>document.getElementById(x);
 const tabs=[['conversacion','Talk'],['cuaderno','Operations Data'],['lab','Lab'],
             ['ajustes','My node'],['modelos','Open World'],['settings','Settings']];
 const select=(name,focus=false)=>{
   if(!tabs.some(([key])=>key===name))return false;
   tabs.forEach(([key])=>{
     const chosen=key===name,button=id('tab-'+key),panel=id('panel-'+key);
     button.setAttribute('aria-selected',String(chosen));
     button.tabIndex=chosen?0:-1;
     panel.hidden=!chosen;
   });
   if(focus)id('tab-'+name).focus();
   id('mini-offline-badge').textContent='DETERMINISTIC_ONLY · '+tabs.find(([x])=>x===name)[1]+' · local only';
   return true;
 };
 tabs.forEach(([name],index)=>{
   const b=id('tab-'+name);
   b.addEventListener('click',()=>select(name));
   b.addEventListener('keydown',e=>{
     if(!['ArrowLeft','ArrowRight','Home','End'].includes(e.key))return;
     e.preventDefault();
     const next=e.key==='Home'?0:e.key==='End'?tabs.length-1:
       (index+(e.key==='ArrowRight'?1:tabs.length-1))%tabs.length;
     select(tabs[next][0],true);
   });
 });
 // The SHARED MINI router and existing project guide still target this old
 // internal button name. It is a hidden compatibility alias, NOT a seventh tab.
 const legacyDocumentTarget=document.createElement('button');
 legacyDocumentTarget.id='tab-documentos';
 legacyDocumentTarget.hidden=true;
 legacyDocumentTarget.tabIndex=-1;
 legacyDocumentTarget.setAttribute('aria-hidden','true');
 legacyDocumentTarget.type='button';
 legacyDocumentTarget.addEventListener('click',()=>select('cuaderno',true));
 document.body.append(legacyDocumentTarget);
 id('mini-start-project').addEventListener('click',()=>select('lab',true));
 const modelToggle=id('modelos-toggle'),modelMenu=id('modelos-menu');
 const setMenu=open=>{modelMenu.hidden=!open;modelToggle.setAttribute('aria-expanded',String(open));};
 modelToggle.addEventListener('click',()=>setMenu(modelMenu.hidden));
 document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!modelMenu.hidden){setMenu(false);modelToggle.focus();}});
 id('mini-local-toggle').addEventListener('click',()=>{
   id('mini-local-mode-status').textContent='Deterministic Mini routing is already active. No native model is bundled with this static projection.';
 });
 // Local static preview MUST NOT submit a provisioning request or fake an ID receipt.
 id('node-identity-form').addEventListener('submit',e=>{
   e.preventDefault();
   const status=id('node-identity-status');
   status.textContent='NO_DATA(local_node_provision_requires_owner_device_runtime). No identity saved or published.';
   status.dataset.state=status.dataset.acho='NO_DATA';
 });
 window.PreceptorDocuments.mount(document);
 window.PreceptorOwnerModelSlots.mount(document,window.localStorage);
 window.PreceptorNodeRegistration.mount(document);
 window.PreceptorMiniProjectGuide.mount(document,window.localStorage,
   window.PreceptorCompanionOnboarding,window.PreceptorDocuments,window.PreceptorOwnerModelSlots);
 window.PreceptorMiniRecovery.mount(document,window.localStorage,{
   guide:window.PreceptorMiniProjectGuide,
   companion:window.PreceptorCompanionOnboarding,
   crypto:window.crypto
 });
 const status=id('offline-mini-status');
 if(status){status.hidden=false;status.textContent='DETERMINISTIC_ONLY · shared Mini router, no model or network';}
 const form=id('form-chat');
 if(form && !form.dataset.miniMounted){
   id('mini-offline-badge').textContent='NO_DATA(mini_router_not_loaded)';
 }
 const press=(element,active)=>{
   element.setAttribute('aria-pressed',String(active));return active;
 };
 const prefKey='preceptoros.public-mini.settings/1';
 const opts={large:false,contrast:false,motion:false};
 function paint(){
   document.documentElement.dataset.miniLargeText=String(opts.large);
   document.documentElement.dataset.miniContrast=String(opts.contrast);
   document.documentElement.dataset.reduceMotion=String(opts.motion);
   for(const [idName,key] of [['mini-text-large','large'],['mini-contrast-toggle','contrast'],['mini-reduced-motion','motion']])
     press(id(idName),opts[key]);
 }
 try{
   const raw=JSON.parse(localStorage.getItem(prefKey)||'null');
   if(raw && raw.schema===prefKey)
     for(const key of Object.keys(opts))opts[key]=raw[key]===true;
 }catch{}
 paint();
 for(const [btn,key] of [['mini-text-large','large'],['mini-contrast-toggle','contrast'],['mini-reduced-motion','motion']])
   id(btn).addEventListener('click',()=>{
     opts[key]=!opts[key];
     paint();
     try{localStorage.setItem(prefKey,JSON.stringify({schema:prefKey,...opts}));}catch{}
     const s=id('mini-settings-status');
     s.textContent=key+' preference '+(opts[key]?'enabled':'disabled')+' on this device.';
     s.dataset.state=s.dataset.acho='LOCAL_PREFERENCE';
   });
 id('mini-speech-stop').addEventListener('click',()=>{
   try{speechSynthesis.cancel();}catch{}
   const s=id('mini-settings-status');s.textContent='Speech stop requested. No sound was started.';
   s.dataset.state=s.dataset.acho='STOP_REQUESTED';
 });
 if('serviceWorker' in navigator)navigator.serviceWorker.register('./sw.js',{scope:'./'}).catch(()=>{
   id('mini-offline-badge').textContent='DETERMINISTIC_ONLY · offline caching unavailable; local guide still works';
 });
 select('conversacion');
})();
"""

CSS = r"""/* Approved APP six-panel, public-safe projection; same owner-local modules. */
*{box-sizing:border-box}
body.public-mini{max-width:56rem;min-width:0;margin:0 auto;padding:1rem;background:var(--ground,#1e1b2c);color:var(--ink,#f4efff)}
.public-mini .mini-head{padding:1rem;border-bottom:1px solid #9baeb9;position:relative}
.public-mini h1{margin:.2rem 0 .7rem;font-size:clamp(1.4rem,4vw,2rem)}
.public-mini .pestanas{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:.25rem;margin:1rem 0}
@media (min-width:720px){.public-mini .pestanas{grid-template-columns:repeat(6,minmax(0,1fr))}}
.public-mini .pestanas button{min-width:0;white-space:normal;min-height:3rem;padding:.55rem .2rem;background:#e8f1f5;color:#123}
.public-mini .pestanas button[aria-selected=true]{background:#1b5068;color:white;outline:2px solid #15445d;outline-offset:1px}
.public-mini .panel{position:static!important;height:auto!important;overflow:visible!important;max-height:none!important;padding:.5rem 0 7rem;display:block}
.public-mini .panel[hidden]{display:none!important}
.public-mini .tarjeta{max-width:none;padding:1rem;border:1px solid #c2d0d8;border-radius:.5rem;margin:.8rem 0;background:#fff}
.public-mini button,.public-mini input,.public-mini textarea,.public-mini select{font:inherit}
.public-mini input:not([type=checkbox]),.public-mini textarea,.public-mini select{width:100%;max-width:100%;padding:.7rem;min-height:2.75rem;margin:.2rem 0 .8rem}
.public-mini button{min-height:2.75rem;border-radius:.3rem;padding:.45rem .7rem;cursor:pointer}
.public-mini label{display:block;font-weight:600;margin-top:.5rem}
.public-mini button:focus-visible,.public-mini a:focus-visible,.public-mini input:focus-visible,.public-mini textarea:focus-visible{outline:3px solid #ab5e00;outline-offset:2px}
.public-mini .mini-guide-actions{display:flex;gap:.5rem;flex-wrap:wrap;margin:1rem 0}
.public-mini .mini-compose{position:sticky;bottom:0;background:var(--ground,#1e1b2c);border-top:2px solid #c1d1d7;padding:.6rem;z-index:2}
.public-mini .mini-compose textarea{min-height:2.8rem;max-height:6rem}
.public-mini .hilo{min-height:3rem;max-height:22rem;overflow:auto;list-style:none;padding:.25rem}
.public-mini pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:25rem;overflow:auto;background:#edf2f5;padding:.75rem}
.public-mini [data-state=NO_DATA]{font-style:italic}
.public-mini details,.public-mini fieldset{max-width:100%}
.public-mini .owner-models-grid{display:grid;grid-template-columns:1fr;gap:1rem}
@media (min-width:720px){.public-mini .owner-models-grid{grid-template-columns:1fr 1fr}}
/* Document editor and first-run are the same HTML elements as the APP source. */
.public-mini #notebook-document-editor{display:block;position:static!important}
.public-mini .mvp-first-run{margin:.7rem 0;padding:.65rem;border:1px solid currentColor;border-radius:.5rem}
.public-mini .mvp-first-run[hidden],.public-mini [hidden]{display:none!important}
.public-mini .superbot-panel-header{display:flex;gap:.75rem;align-items:center;flex-wrap:wrap}
.public-mini .superbot-agents{min-width:6rem;max-width:100%;margin:0}
.public-mini #modelos-menu{padding:.5rem;border:1px solid currentColor;border-radius:.3rem}
.public-mini #ajustes-nodo{margin:.6rem 0}
.public-mini #node-public-template{padding:.5rem}
.public-mini [data-state=NO_DATA]{font-style:normal}
.public-mini [data-state=NO_DATA]::before{content:"";display:none}
html[data-mini-large-text=true] body.public-mini{font-size:1.2rem}
html[data-mini-contrast=true] body.public-mini{background:#000!important;color:#fff!important}
html[data-mini-contrast=true] .public-mini button{background:#fff;color:#000}
html[data-reduce-motion=true] #talk-processing .talk-processing-crab{animation:none!important}
@media (prefers-reduced-motion: reduce){#talk-processing .talk-processing-crab{animation:none!important}}
@media (max-width:390px){body.public-mini{padding:.4rem}.public-mini .pestanas button{font-size:.82rem}}
"""
SW = r"""/* Public APP static shell. Never intercept or cache /api or remote requests. */
const CACHE='preceptoros-public-mini-recover-v1';
const BASE=new URL('./',self.registration.scope);
const ASSETS=['./','./index.html','./app.css','./public-mini.css','./documents.js',
'./owner_model_slots.js','./companion_onboarding.js','./node_registration.js',
'./mini_project_guide.js','./mini_recovery.js','./offline_mini.js','./mvp_first_run.js','./superbot_talk.js',
'./talk_crab_canvas.js','./face/bubble/openworld_crab_body.js','./public-boot.js','./manifest.webmanifest',
'./assets/icono-192.png','./assets/icono-512.png','./assets/icono-512-maskable.png'];
self.addEventListener('install',event=>{
  event.waitUntil(caches.open(CACHE).then(cache=>cache.addAll(ASSETS)));
  self.skipWaiting();
});
self.addEventListener('activate',event=>{
  event.waitUntil(caches.keys().then(keys=>Promise.all(keys.filter(k=>k.startsWith('preceptoros-public-mini-')&&k!==CACHE)
    .map(k=>caches.delete(k)))).then(()=>self.clients.claim()));
});
self.addEventListener('fetch',event=>{
  const request=event.request,url=new URL(request.url);
  if(request.method!=='GET'||url.origin!==self.location.origin||
     !url.pathname.startsWith(BASE.pathname)||url.pathname.includes('/api/'))return;
  event.respondWith(caches.match(request).then(hit=>hit||fetch(request)));
});
"""

def build(out: Path) -> dict:
    source=(SOURCE/"app.html").read_text(encoding="utf-8")
    if out.exists():shutil.rmtree(out)
    app=out/"app";app.mkdir(parents=True)
    for name,path in FILES.items():
        dest=app/name;dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,dest)
    (app/"index.html").write_text(shell(source),encoding="utf-8")
    (app/"public-boot.js").write_text(BOOT,encoding="utf-8")
    (app/"public-mini.css").write_text(CSS,encoding="utf-8")
    (app/"manifest.webmanifest").write_text(json.dumps({
         "id":"/app/","name":"PreceptorOS APP · local projection","short_name":"PreceptorOS",
        "start_url":"/app/","scope":"/app/","display":"standalone",
        "theme_color":"#152c38","background_color":"#f7f8f7",
        "icons":[
            {"src":"./assets/icono-192.png","sizes":"192x192","type":"image/png"},
            {"src":"./assets/icono-512.png","sizes":"512x512","type":"image/png"},
            {"src":"./assets/icono-512-maskable.png","sizes":"512x512","type":"image/png","purpose":"maskable"}
        ]},indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    hashes={p.relative_to(app).as_posix():sha(p.read_bytes()) for p in sorted(app.rglob("*")) if p.is_file()}
    version=sha(json.dumps(hashes,sort_keys=True).encode())[:12]
    (app/"sw.js").write_text(SW.replace("preceptoros-public-mini-'","preceptoros-public-mini-"+version+"'"),encoding="utf-8")
    hashes={p.relative_to(app).as_posix():sha(p.read_bytes()) for p in sorted(app.rglob("*")) if p.is_file()}
    source_head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    receipt={"schema":"preceptoros.public-mini-package/2","source_repository":"piskyRpapalo/preceptoros-app",
             "source_head":source_head, "mode":"SIX_ZONE_PUBLIC_SAFE_DETERMINISTIC_ONLY",
             "source_panels":["conversacion","cuaderno","lab","ajustes","modelos","settings"],
             "projection_not_android_apk":True,"approved_app_sw":"preceptoros-armazon-v236",
             "public_entry":"/app/","redirect_required":"/app -> /app/",
             "no_model_download":True,"no_rack_connection":True,"files":hashes}
    (app/"package-manifest.json").write_text(json.dumps(receipt,sort_keys=True,indent=2)+"\n",encoding="utf-8")
    archive=out.parent/"public-mini-app.zip"
    archive.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive,"w",compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for file in sorted(app.rglob("*")):
            if not file.is_file():continue
            info=zipfile.ZipInfo(file.relative_to(out).as_posix(),date_time=(1980,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            info.external_attr=0o644 << 16
            z.writestr(info,file.read_bytes(),compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    package_sha=sha(archive.read_bytes())
    (out.parent/"public-mini-app.sha256").write_text(package_sha+"  public-mini-app.zip\n",encoding="ascii")
    return {"zip":str(archive),"sha256":package_sha,"source_head":source_head,
            "files":len(hashes),"size":archive.stat().st_size,"entry":"/app/"}

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--out",type=Path,default=OUT)
    args=parser.parse_args()
    print(json.dumps(build(args.out.resolve()),sort_keys=True))
