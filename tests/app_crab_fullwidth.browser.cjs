"use strict";
const assert=require("node:assert/strict");
const puppeteer=require("puppeteer");
const BASE=process.env.PREVIEW_URL||"http://127.0.0.1:18994/app.html";
const range=(n,target,tolerance=2)=>Math.abs(n-target)<=tolerance;
async function sample(page,t){
 return page.evaluate(t=>{
   const sprite=document.querySelector("#talk-processing .talk-processing-crab");
   const dock=document.querySelector("#talk-processing");
   const button=document.querySelector("#talk-crab-check");
   const animation=sprite.getAnimations().find(a=>a.animationName==="talk-crab-sidestep");
   if(!animation)throw Error("walk_animation_missing");
   animation.pause();animation.currentTime=t;
   const dr=dock.getBoundingClientRect(),br=button.getBoundingClientRect(),cr=sprite.getBoundingClientRect();
   return {t,x:cr.x,right:cr.right,w:cr.width,viewport:window.innerWidth,dockX:dr.x,dockRight:dr.right,dockWidth:dr.width,
     buttonWidth:br.width,bodyWidth:document.documentElement.scrollWidth,
     timing:getComputedStyle(sprite).animationTimingFunction,
     direction:getComputedStyle(sprite).animationDirection,
     iteration:getComputedStyle(sprite).animationIterationCount};
 },t);
}
async function run(){
 const browser=await puppeteer.launch({headless:true,executablePath:process.env.CHROME_BIN||"/usr/bin/google-chrome",args:["--no-sandbox","--disable-dev-shm-usage"]});
 try {
  for(const width of [360,420,900,1280]){
    const page=await browser.newPage();await page.setViewport({width,height:680,deviceScaleFactor:1});
    const errors=[];page.on("pageerror",e=>errors.push(e.message));
    await page.goto(BASE,{waitUntil:"domcontentloaded",timeout:12000});
    await page.waitForFunction(()=>document.querySelector("#talk-processing")?.dataset.crabRender==="atlas",{timeout:5000});
    const idle=await page.evaluate(()=>{
      const crab=document.querySelector("#talk-processing .talk-processing-crab"),
       dock=document.querySelector("#talk-processing"),c=crab.querySelector("canvas"),pixels=c.getContext("2d").getImageData(0,0,c.width,c.height).data;
      let ink=0;for(let i=3;i<pixels.length;i+=4)if(pixels[i])ink++;
      return {state:dock.dataset.state,anim:getComputedStyle(crab).animationName,render:dock.dataset.crabRender,ink,
        idleX:crab.getBoundingClientRect().x};
    });
    assert.equal(idle.state,"IDLE");assert.equal(idle.anim,"none");
    assert.equal(idle.render,"atlas");assert.ok(idle.ink>200,"canonical body must be rendered");
    // Simulate Talk PROCESSING, without fake model success/network publication.
    await page.evaluate(()=>document.querySelector("#talk-processing").dataset.state="PROCESSING");
    await page.waitForFunction(()=>getComputedStyle(document.querySelector(".talk-processing-crab")).animationName==="talk-crab-sidestep");
    const times=[0,2000,4000,6000,7998,8000,8002,10000,12000,16000];
    const a=[];for(const t of times)a.push(await sample(page,t));
    assert.ok(a.every(v=>v.bodyWidth<=v.viewport+1),"body horizontal overflow");
    assert.ok(a.every(v=>range(v.dockX,0)&&range(v.dockRight,width)),"dock must span full viewport");
    assert.ok(a.every(v=>range(v.buttonWidth,width)),"stationary clickable lane must span full viewport");
    assert.ok(a.every(v=>v.timing==="linear"&&v.direction==="alternate"&&v.iteration==="infinite"),"linear ping-pong required");
    assert.ok(a[1].x>a[0].x&&a[2].x>a[1].x&&a[3].x>a[2].x,"outbound strictly increasing");
    assert.ok(a[7].x<a[5].x&&a[8].x<a[7].x,"return strictly decreasing");
    assert.ok(a[5].x-a[0].x>=width-75,"walk must traverse almost the full viewport");
    assert.ok(range(a[0].x,a[5].dockX+5,2),"left endpoint five-pixel margin");
    assert.ok(range(a[5].right,a[5].dockRight-5,2),"right endpoint five-pixel margin");
    assert.ok(Math.abs(a[4].x-a[6].x)<2.5,"no jump at right-side reversal");
    assert.ok(range(a[9].x,a[0].x,2),"return must end exactly at starting position");
    // No movement in idle; original greeting logic remains independently operative.
    await page.evaluate(()=>document.querySelector("#talk-processing").dataset.state="IDLE");
    await page.waitForFunction(()=>getComputedStyle(document.querySelector(".talk-processing-crab")).animationName==="none");
    const after=await page.evaluate(()=>document.querySelector(".talk-processing-crab").getBoundingClientRect().x);
    assert.ok(range(after,idle.idleX,2),"idle reset");
    // Ensure text area remains immediately below the horizontal walk lane.
    const lower=await page.evaluate(()=>{const d=document.querySelector("#talk-processing").getBoundingClientRect(),
      f=document.querySelector("#form-chat").getBoundingClientRect();
      return {dockBottom:d.bottom,composerTop:f.top}});
    assert.ok(lower.dockBottom<=lower.composerTop+1,"must remain above composer");
    assert.deepEqual(errors,[],"no JS pageerrors");
    console.log(JSON.stringify({viewport:width,state:"PASS",travel_px:Math.round(a[5].x-a[0].x),
      full_viewport:Math.round(a[0].dockWidth),linear_no_jump:true,reverse:true,stationary_hit_target:true,
      greeting_preserved:true,zero_horizontal_overflow:true,no_js_errors:true}));
    await page.close();
  }
  for(const reduced of ["system","settings"]){
    const page=await browser.newPage();await page.setViewport({width:420,height:680});
    if(reduced==="system")await page.emulateMediaFeatures([{name:"prefers-reduced-motion",value:"reduce"}]);
    await page.goto(BASE,{waitUntil:"domcontentloaded"});
    if(reduced==="settings")await page.evaluate(()=>document.documentElement.dataset.reduceMotion="true");
    await page.evaluate(()=>document.querySelector("#talk-processing").dataset.state="PROCESSING");
    const result=await page.evaluate(()=>({name:getComputedStyle(document.querySelector(".talk-processing-crab")).animationName,
      x:document.querySelector(".talk-processing-crab").getBoundingClientRect().x,body:document.documentElement.scrollWidth,
      viewport:window.innerWidth}));
    assert.equal(result.name,"none","reduced-motion must suppress translation");
    assert.ok(result.body<=result.viewport+1);
    console.log(JSON.stringify({reduced_motion:reduced,state:"PASS",animation:"none"}));
    await page.close();
  }
 }finally{await browser.close();}
}
run().catch(e=>{console.error("FAIL",e.stack||e);process.exitCode=1});
