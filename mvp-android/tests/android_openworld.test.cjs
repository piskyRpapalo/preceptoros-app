"use strict";
const test=require("node:test"),assert=require("node:assert/strict"),vm=require("node:vm"),fs=require("node:fs"),path=require("node:path"),os=require("node:os"),cp=require("node:child_process");
const root=path.resolve(__dirname,"..");
const bridge=fs.readFileSync(path.join(root,"android_openworld_bridge.js"),"utf8");
const policy=fs.readFileSync(path.join(root,"app/src/main/java/org/preceptoros/mvp/OpenWorldVisitorPolicy.java"),"utf8");
const activity=fs.readFileSync(path.join(root,"app/src/main/java/org/preceptoros/mvp/MainActivity.java"),"utf8");
const local=fs.readFileSync(path.join(root,"app/src/main/res/raw/local_bridge.js"),"utf8");
function fixture(native=true){
 const sent=[], listeners={};
 const link={href:"https://preceptoros.org/openworld/",dataset:{},addEventListener:(n,f)=>listeners[n]=f};
 const status={dataset:{},textContent:""};
 const document={getElementById:id=>id==="openworld-visit"?link:id==="openworld-visit-status"?status:null};
 const win={document,PreceptorAndroidOpenWorld:native?{open:url=>new Promise(resolve=>sent.push({url,resolve}))}:undefined};win.window=win;
 vm.runInNewContext(bridge,{window:win,document,Promise});
 return {link,status,sent,click:trusted=>listeners.click({preventDefault(){},isTrusted:trusted})};
}
test("visitor route policy compiles and accepts only the exact HTTPS entry",()=>{
 const dir=fs.mkdtempSync(path.join(os.tmpdir(),"ow-policy-"));
 try {
  fs.writeFileSync(path.join(dir,"PolicyCheck.java"),`import org.preceptoros.mvp.OpenWorldVisitorPolicy; public class PolicyCheck { public static void main(String[] a) { for(String u:a) System.out.println(OpenWorldVisitorPolicy.accepts(u)); } }`);
  const source=path.join(root,"app/src/main/java/org/preceptoros/mvp/OpenWorldVisitorPolicy.java");
  cp.execFileSync("javac",["-d",dir,source,path.join(dir,"PolicyCheck.java")]);
  fs.writeFileSync(path.join(dir,"PolicyCheck.java"),`import org.preceptoros.mvp.OpenWorldVisitorPolicy; public class PolicyCheck { public static void main(String[] a) { for(String u:a) System.out.println(OpenWorldVisitorPolicy.accepts(u)+":"+OpenWorldVisitorPolicy.allowsNavigation(u)); } }`);
  cp.execFileSync("javac",["-d",dir,source,path.join(dir,"PolicyCheck.java")]);
  const urls=["https://preceptoros.org/openworld/","http://preceptoros.org/openworld/","https://preceptoros.org/","https://preceptoros.org/openworld/?go=hexelion","https://preceptoros.org/openworld/../owner","https://preceptoros.org/openworld/%2e%2e/owner","https://preceptoros.org.evil/openworld/","https://user@preceptoros.org/openworld/","https://preceptoros.org:443/openworld/","javascript:alert(1)"];
  const got=cp.execFileSync("java",["-cp",dir,"PolicyCheck",...urls],{encoding:"utf8"}).trim().split(/\r?\n/);
  assert.deepEqual(got,["true:true","false:false","false:false","false:true",...Array(6).fill("false:false")]);
 } finally { fs.rmSync(dir,{recursive:true,force:true}); }
});
test("no bridge means no visitor handoff; remote route is not native capability",()=>{
 const x=fixture(false); assert.equal(x.link.dataset.androidOpenWorldBound,undefined); assert.equal(x.sent.length,0);
 assert.match(local,/open: url => ask\('openworld', url/);
 assert.match(activity,/case "openworld"[\s\S]*openWorld\(value\)/);
 assert.match(activity,/new Intent\(this, OpenWorldActivity\.class\)/);
 assert.match(activity,/ownPageReady\)/);
 assert.match(activity,/evaluateBundledScript\(view, "android_openworld_bridge\.js"\)/);
});
test("untrusted synthetic click is refused before native request",async()=>{
 const x=fixture();x.click(false);assert.equal(x.sent.length,0);assert.equal(x.status.dataset.state,"NO_DATA");
});
test("explicit user tap requests the fixed visitor route and reports no node admission",async()=>{
 const x=fixture();x.click(true);assert.equal(x.sent.length,1);assert.equal(x.sent[0].url,"https://preceptoros.org/openworld/");
 x.sent[0].resolve(true);await new Promise(r=>setImmediate(r));
 assert.equal(x.status.dataset.state,"VISITOR_HANDOFF");assert.equal(x.status.dataset.acho,"VISITOR_HANDOFF");
 assert.match(x.status.textContent,/No account or node was created/);
});
test("non-exact link fails closed and Android remote bridge stays origin scoped",async()=>{
 const x=fixture();x.link.href="https://evil.example/";x.click(true);assert.equal(x.sent.length,0);assert.equal(x.status.dataset.cause,"user_action_or_route_invalid");
 assert.match(activity,/Collections\.singleton\(OwnerFrameAccess\.ORIGIN\)/);
 assert.doesNotMatch(activity,/Collections\.singleton\([^\n]*preceptoros\.org/);
 assert.match(activity,/setAllowFileAccess\(false\)/);assert.match(activity,/MIXED_CONTENT_NEVER_ALLOW/);
 const remote=fs.readFileSync(path.join(root,"app/src/main/java/org/preceptoros/mvp/OpenWorldActivity.java"),"utf8");
 assert.doesNotMatch(remote,/addJavascriptInterface|WebMessageListener|PreceptorLocalNative|PreceptorJoinNative|PreceptorHeartbeatNative|PrivateTalkNative/);
 assert.match(remote,/allowsNavigation\(request\.getUrl\(\)\.toString\(\)\)/);
});
test("browser loss or absent handler never fabricates LIVE or node identity",()=>{
 assert.match(bridge,/openworld_handoff_unavailable/);assert.match(bridge,/VISITOR_HANDOFF/);
 assert.doesNotMatch(bridge,/LIVE|node\.register|credential|cedula/i);
 assert.match(policy,/static final String URL = "https:\/\/preceptoros\.org\/openworld\/"/);
});
