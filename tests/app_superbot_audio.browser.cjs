"use strict";
const puppeteer=require("/home/pisky/.npm/_npx/4b4c857f6efdfb61/node_modules/puppeteer");
const assert=require("node:assert/strict");
const base=process.env.PREVIEW_URL||"http://127.0.0.1:18894/app.html";
(async()=>{
 const browser=await puppeteer.launch({headless:true,executablePath:"/usr/bin/google-chrome",args:["--no-sandbox","--disable-dev-shm-usage"]});
 try{
  for(const width of [360,420,900]){
   // Different volunteers do not share the same origin storage or audio opt-in.
   const userContext=await browser.createBrowserContext();
   const page=await userContext.newPage();
   await page.setViewport({width,height:720});
   const errors=[];page.on("pageerror",e=>errors.push(e.message));
   await page.evaluateOnNewDocument(()=>{
     window.__audioWitness={tones:0,speeches:[],cancels:0,mic:0};
     const param=()=>({setValueAtTime(){},exponentialRampToValueAtTime(){}});
     const Osc=function(){this.frequency=param();this.connect=()=>{};this.start=()=>{window.__audioWitness.tones++};this.stop=()=>{};};
     const Gain=function(){this.gain=param();this.connect=()=>{};};
     window.AudioContext=function(){this.state="running";this.currentTime=0;this.destination={};this.createGain=()=>new Gain();this.createOscillator=()=>new Osc();};
     Object.defineProperty(window,"SpeechSynthesisUtterance",{configurable:true,value:function(text){this.text=text;this.lang="en";this.rate=1;}});
     Object.defineProperty(window,"speechSynthesis",{configurable:true,value:{
       speak(utter){window.__audioWitness.speeches.push({text:utter.text,rate:utter.rate});setTimeout(()=>utter.onstart?.(),4);setTimeout(()=>utter.onend?.(),35);},
       cancel(){window.__audioWitness.cancels++;}
     }});
   });
   await page.goto(base,{waitUntil:"domcontentloaded"});
   await page.waitForFunction(()=>!!window.PreceptorAudioAccessibility&&!!window.PreceptorSuperbotTalk);
   const initial=await page.evaluate(()=>({
      title:document.querySelector('#panel-conversacion .superbot-heading h3')?.textContent,
      talkTitleHidden:getComputedStyle(document.getElementById('h-conversacion')).clip!=='auto',
      superbotCount:document.getElementById("superbot-agent-count")?.textContent,
      audioWitness:window.__audioWitness,duplicateAudioIds:document.querySelectorAll("#acho-sonido").length,
      tabCount:document.querySelectorAll('.pestanas [role="tab"]').length,
      bodyOverflow:document.documentElement.scrollWidth>innerWidth
   }));
   assert.equal(initial.title,"Agents");assert.equal(initial.talkTitleHidden,true);
   assert.match(initial.superbotCount,/plan unavailable/);
   assert.equal(initial.duplicateAudioIds,1);
   assert.equal(initial.tabCount,6);assert.equal(initial.bodyOverflow,false);
   assert.equal(initial.audioWitness.tones,0);assert.equal(initial.audioWitness.speeches.length,0);
   await page.click("#tab-settings");
   await page.click("#settings-accessibility > summary");
   const defaults=await page.evaluate(()=>({
      sound:document.getElementById("acho-sonido").checked,
      speak:document.getElementById("settings-speech-enable").checked,
      readDisabled:document.getElementById("settings-speech-read").disabled
   }));
   assert.deepEqual(defaults,{sound:false,speak:false,readDisabled:true});
   await page.click("#settings-sound-test");
   const before=await page.evaluate(()=>({
      status:document.getElementById("settings-audio-status").dataset.state,
      tones:window.__audioWitness.tones
   }));
   assert.equal(before.status,"BLOCKED");assert.equal(before.tones,0);
   await page.click('label[for="acho-sonido"]');
   await page.click("#settings-sound-test");
   const tone=await page.evaluate(()=>({
      status:document.getElementById("settings-audio-status").dataset.state,
      tones:window.__audioWitness.tones,
      soundStored:localStorage.getItem("preceptoros.acho.sound")
   }));
   assert.equal(tone.status,"LOCAL");assert.ok(tone.tones>=2);assert.equal(tone.soundStored,"on");
   await page.click('label[for="settings-speech-enable"]');
   const ready=await page.evaluate(()=>({readDisabled:document.getElementById("settings-speech-read").disabled,
     speak:document.getElementById("settings-speech-enable").checked}));
   assert.equal(ready.readDisabled,false);assert.equal(ready.speak,true);
   await page.select("#settings-speech-rate","1.2");
   await page.click("#settings-speech-read");
   await new Promise(r=>setTimeout(r,65));
   const spoken=await page.evaluate(()=>({words:window.__audioWitness.speeches,st:document.getElementById("settings-audio-status").dataset.state,
      mic:window.__audioWitness.mic}));
   assert.ok(spoken.words[0]?.text.includes("PreceptorOS. Settings."));
   assert.equal(spoken.words[0]?.rate,1.2);
   assert.equal(spoken.st,"LOCAL");assert.equal(spoken.mic,0);
   await page.click("#settings-speech-stop");
   const stopped=await page.evaluate(()=>({state:document.getElementById("settings-audio-status").dataset.state,
      cancels:window.__audioWitness.cancels}));
   assert.equal(stopped.state,"LOCAL");assert.ok(stopped.cancels>=1);
   await page.reload({waitUntil:"domcontentloaded"});
   const persisted=await page.evaluate(()=>({sound:document.getElementById("acho-sonido").checked,
      speak:document.getElementById("settings-speech-enable").checked,
      rate:document.getElementById("settings-speech-rate").value}));
   assert.equal(persisted.sound,true);assert.equal(persisted.speak,true);assert.equal(persisted.rate,"1.2");
   await page.close();
   const syn=await userContext.newPage();await syn.setViewport({width,height:720});
   const synErrors=[];syn.on("pageerror",e=>synErrors.push(e.message));
   await syn.goto(base+"?plan=synthetic",{waitUntil:"domcontentloaded"});
   await syn.waitForFunction(()=>document.getElementById("superbot-agent-count").textContent.includes("agents referenced"),{timeout:9000});
   const swarm=await syn.evaluate(()=>({count:document.getElementById("superbot-agent-count").textContent,
      state:document.getElementById("superbot-agent-disclosure").dataset.state,
      name:document.getElementById("superbot-orchestrator").textContent,
      cards:document.querySelectorAll("#superbot-agent-tabs [role=tab]").length}));
   assert.match(swarm.count,/05 agents referenced in plan · SYNTHETIC/);
   assert.equal(swarm.state,"SYNTHETIC");assert.match(swarm.name,/SYNTHETIC/);
   assert.equal(swarm.cards,5);
   await syn.click("#superbot-agent-disclosure > summary");
   const tabs=await syn.evaluate(()=>[...document.querySelectorAll("#superbot-agent-tabs [role=tab]")].map(n=>n.textContent));
   assert.equal(tabs.length,5);
   await syn.$eval("#superbot-agent-tabs [role=tab]",b=>b.focus());
   await syn.keyboard.press("ArrowRight");
   const selected=await syn.evaluate(()=>({
      tab:document.querySelector("#superbot-agent-tabs [role=tab][aria-selected=true]")?.textContent,
      detail:document.getElementById("superbot-agent-detail").textContent,
      focus:document.activeElement?.textContent,
      canExecute:!!document.querySelector("#superbot-agent-disclosure [data-action=dispatch]"),
      overflow:document.documentElement.scrollWidth>innerWidth
   }));
   assert.equal(selected.tab,selected.focus);
   assert.ok(selected.detail.includes("Functions: "));
   assert.ok(selected.detail.includes("not proof of an installed, authorized or running agent"));
   assert.equal(selected.canExecute,false);assert.equal(selected.overflow,false);
   assert.deepEqual(synErrors,[]);assert.deepEqual(errors,[]);
   console.log(JSON.stringify({gate:"PASS",viewport:width,settings:{soundDefaultOff:true,speechDefaultOff:true,toneAfterConsent:true,speechOnDemand:true,stop:true,stored:true},
    superbot:{synthetic:true,agentReferenceCount:5,tabs:tabs,keyboard:true,noDispatch:true},jsErrors:0}));
   await syn.close();
   await userContext.close();
  }
 }finally{await browser.close();}
})().catch(e=>{console.error("FAIL",e.stack||e);process.exitCode=1});
