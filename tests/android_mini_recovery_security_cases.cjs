'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {readFileSync}=require('node:fs');
const main=readFileSync('mvp-android/app/src/main/java/org/preceptoros/mvp/MainActivity.java','utf8');
const html=readFileSync('interface/app.html','utf8');
const js=readFileSync('interface/mini_recovery.js','utf8');
const bridge=readFileSync('mvp-android/app/src/main/java/org/preceptoros/mvp/DeploymentJoinBridge.java','utf8');
test('Android recovery file picker is explicit system OpenDocument, not a filesystem scan',()=>{
 assert.match(main,/onShowFileChooser\(/);
 assert.match(main,/Intent\.ACTION_OPEN_DOCUMENT/);
 assert.match(main,/Intent\.CATEGORY_OPENABLE/);
 assert.match(main,/picker\.setType\("application\/json"\)/);
 assert.match(main,/MINI_RECOVERY_PICKER/);
 assert.match(main,/onActivityResult/);
 assert.match(main,/pendingMiniRecoveryFile/);
 assert.match(main,/ownPageReady\s*\|\|\s*!START\.equals\(view\.getUrl\(\)\)/);
});
test('Android does not grant arbitrary file or network authority in recovery path',()=>{
 assert.match(main,/s\.setAllowFileAccess\(false\)/);
 assert.doesNotMatch(main,/READ_EXTERNAL_STORAGE|MANAGE_EXTERNAL_STORAGE|WRITE_EXTERNAL_STORAGE/);
 assert.doesNotMatch(js,/fetch\(/);
 assert.doesNotMatch(js,/XMLHttpRequest|WebSocket|location\.href\s*=/);
 assert.match(js,/UNVERIFIED_LOCAL/);
 assert.match(js,/NO_DATA\(no_signed_owner_proof\)/);
});
test('My node and Lab mirror recovery status for speech and machine readers',()=>{
 for(const id of ['mini-recovery','mini-recovery-file','mini-recovery-preview-button',
 'mini-recovery-consent','mini-recovery-import','mini-recovery-state','lab-mini-recovery-state']){
  assert.match(html,new RegExp('id="'+id+'"'));
 }
 assert.match(html,/data-acho="NO_DATA"/);
 assert.match(html,/role="status" aria-live="polite"/);
 assert.match(html,/mini_recovery\.js/);
});
test('Native request keeps independent second owner confirmation and fixed destination',()=>{
 assert.match(bridge,/Send a node review request\?/);
 assert.match(bridge,/new AlertDialog/);
 assert.match(bridge,/api\.preceptoros\.org/);
 assert.doesNotMatch(js,/requestPreliminary|requestDeploymentReview/);
});
