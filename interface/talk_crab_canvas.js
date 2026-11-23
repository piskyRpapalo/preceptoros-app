/* Talk visual adapter. Body geometry + gait are exact, source-pinned Open World
 * public/game/crab_body.js. Only the rendering context (small canvas) differs.
 * Source SHA-256: e332c81bdee87a90a3aa76e7e34dea32c5f493879b64c1f97104510a6e3404b0
 * No network, no task inference, no model-success claim. At rest the crab stands still: it moves only while a
 * real engine event says a model is loading, generating or speaking (data-state), and stops on anything else.
 */
(function (root) {
  'use strict';
  const box = root.document.getElementById('talk-processing');
  const canvas = box && box.querySelector('canvas.talk-crab-canvas');
  if (!canvas) return;
  const B = root.AtlasCrabBody;
  if (!B || typeof B.draw !== 'function' || typeof B.pose !== 'function') {
    box.dataset.crabRender = 'NO_DATA';
    box.dataset.crabCause = 'openworld_body_missing';
    return;
  }
  const g = canvas.getContext('2d');
  if (!g) {
    box.dataset.crabRender = 'NO_DATA';
    box.dataset.crabCause = 'canvas_not_supported';
    return;
  }
  // Palette from WEB public/game/comic_tokens.js; map_painter.js' four color functions.
  const T = {
    NEUTRAL: {ink:'#1E1826',paper:'#F2F5F7'},
    FRONT_DOOR: {cyan:'#7FD1E8','FIRMADO.base':'#5C7CFF','PROPUESTA.base':'#FFB454'}
  };
  function rgbOf(s) {
    const m = /^#([0-9a-f]{2})([0-9a-f]{2})([0-9a-f]{2})/i.exec(s);
    return m ? [parseInt(m[1],16),parseInt(m[2],16),parseInt(m[3],16)] : [128,128,128];
  }
  const H = {
    T, rgbOf,
    mix(a,b,k) { return a.map((v,j)=>Math.round(v+(b[j]-v)*k)); },
    shade(a,f) { return a.map(v=>Math.max(0,Math.min(255,Math.round(v*f)))); },
    css(a) { return '#'+a.map(v=>('0'+v.toString(16)).slice(-2)).join(''); }
  };
  const W=88, HEIGHT=58, dpr=Math.min(2,Math.max(1,root.devicePixelRatio||1));
  canvas.width=Math.round(W*dpr); canvas.height=Math.round(HEIGHT*dpr);
  const media=root.matchMedia && root.matchMedia('(prefers-reduced-motion: reduce)');
  const reduced=()=>!!(media && media.matches) || root.document.documentElement.dataset.reduceMotion==='true';
  const check=root.document.getElementById('talk-crab-check');
  const label=root.document.getElementById('talk-processing-label');
  const details=root.document.getElementById('talk-crab-detail');
  let raf=0, nextGreet=0, origin=0, scene='rest';
  const moving=new Set(['PROCESSING','SIMULATED','LOADING','GENERATING','SPEAKING']);
  const active=()=>!box.hidden && moving.has(box.dataset.state);
  const visible=()=>!box.hidden && !root.document.hidden;
  function oval(ctx,x,y,rx,ry,angle,from,to) { ctx.ellipse(x,y,rx,ry,angle,from,to); }
  function paint(t) {
    g.setTransform(dpr,0,0,dpr,0,0);
    g.clearRect(0,0,W,HEIGHT);
    const elapsed=Math.max(0,t-origin);
    let pose=B.pose(0,1,1);
    if (!reduced() && scene==='processing') {
      // Same tripod gait as Open World; the CSS moves its canvas side to side.
      const step=Math.floor(elapsed/B.GLIDE), progress=(elapsed%B.GLIDE)/B.GLIDE;
      pose=B.pose(step,progress,1);
    } else if (!reduced() && scene==='greeting') {
      // Open World's own claw greeting: B.pose(..., gp<1) raises and opens
      // the claws twice in GREET milliseconds. Then its legs briefly step.
      if (elapsed<B.GREET) pose=B.pose(0,1,elapsed/B.GREET);
      else if (elapsed<B.GREET+480) pose=B.pose(0,(elapsed-B.GREET)/480,1);
    }
    B.draw(g,W/2,HEIGHT-4,1.15,pose,H,0.5,oval);
    box.dataset.crabRender='atlas';
  }
  function stop() {
    if (raf) root.cancelAnimationFrame(raf);
    if (nextGreet) root.clearTimeout(nextGreet);
    raf=0; nextGreet=0;
  }
  function frame(t) {
    raf=0;
    if (!visible() || reduced()) return;
    paint(t);
    if (scene==='processing' && active()) raf=root.requestAnimationFrame(frame);
    else if (scene==='greeting' && !active() && t-origin<B.GREET+480) raf=root.requestAnimationFrame(frame);
    else if (!active()) { scene='rest'; paint(t); }
  }
  function beginGreeting() {
    stop();
    if (!visible() || reduced() || active()) {
      scene=active()?'processing':'rest';
      paint(root.performance.now());
      return;
    }
    scene='greeting'; origin=root.performance.now();
    paint(origin); raf=root.requestAnimationFrame(frame);
  }
  function sync() {
    stop();
    origin=root.performance.now();
    scene=active()?'processing':'rest';
    paint(origin);
    if (!visible() || reduced()) return;
    if (active()) raf=root.requestAnimationFrame(frame);
  }
  if (check) check.addEventListener('click',()=>{
    const state=box.dataset.state;
    details.textContent=state==='PROCESSING'
      ? 'Talk is processing a request. No reply has been verified yet.'
      : state==='SIMULATED'
        ? 'Animation preview only. No model request is running.'
        : 'Talk has no request in progress. The crab is resting.';
    details.hidden=false;
    if (state==='IDLE') beginGreeting();
  });
  new MutationObserver(sync).observe(box,{attributes:true,attributeFilter:['hidden','data-state']});
  new MutationObserver(sync).observe(root.document.documentElement,{attributes:true,attributeFilter:['data-reduce-motion']});
  root.document.addEventListener('visibilitychange',sync);
  if (media) { if (media.addEventListener) media.addEventListener('change',sync); else if (media.addListener) media.addListener(sync); }

  // Optional local preview retains its explicit simulated label and cannot
  // confuse a real chat response with a graphical activity test.
  const url=new URL(root.location.href);
  if (root.location.hostname==='127.0.0.1' && root.location.port==='18894' &&
      url.searchParams.get('crab_demo')==='1') {
    const form=root.document.getElementById('form-chat');
    let preview=true;
    function endDemo() {
      if (!preview) return;
      preview=false;
      box.dataset.state='IDLE';
      box.dataset.acho='silent';
      box.dataset.demo='off';
      label.textContent=''; label.hidden=true;
      if (details) { details.hidden=true; details.textContent=''; }
      close.remove();
    }
    if (form) form.addEventListener('submit',endDemo,true);
    label.textContent='Motion preview · simulated'; label.hidden=false;
    box.dataset.demo='simulated';
    box.dataset.acho='simulated';
    box.dataset.state='SIMULATED';
    const close=root.document.createElement('button');
    close.type='button';close.className='talk-crab-preview-stop';
    close.textContent='End preview';
    close.addEventListener('click',endDemo);
    box.appendChild(close);
  }
  sync();
})(window);
