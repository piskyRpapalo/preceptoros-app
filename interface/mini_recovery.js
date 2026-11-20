/* PreceptorOS Mini recovery (01): import existing public Mini project export.
 * This is local project/document recovery, never owner identity authorization.
 * Reuses preceptoros.mini-project-export/1 + MiniProjectGuide validation.
 * No fetch, no device scan, no secret/key import, no grant, no node registration.
 */
(function (root) {
  'use strict';
  const schema='preceptoros.mini-project-export/1';
  const recordSchema='preceptoros.mini-recovery/1';
  const projectKey='preceptoros.public-mini.project.v1';
  const documentsKey='preceptoros.documents.v1';
  const recoveryKey=recordSchema;
  const maxBytes=262144;
  const maxDocs=12;
  const maxRecordBytes=24576;
  const keys=Object.freeze(['schema','project','documents','source_links','declared_by','sent','model_weights_included']);
  const plain=x=>x!==null&&typeof x==='object'&&!Array.isArray(x)&&Object.getPrototypeOf(x)===Object.prototype;
  const fail=cause=>Object.freeze({ok:false,state:'NO_DATA',cause,changed:false});
  const encode=value=>new TextEncoder().encode(value);
  function canonical(value) {
    if (Array.isArray(value)) return '['+value.map(canonical).join(',')+']';
    if (plain(value)) return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
    return JSON.stringify(value);
  }
  async function sha256(text, cryptoImpl) {
    const subtle=cryptoImpl && cryptoImpl.subtle;
    if (!subtle) throw Error('secure_digest_unavailable');
    return [...new Uint8Array(await subtle.digest('SHA-256',encode(text)))]
      .map(x=>x.toString(16).padStart(2,'0')).join('');
  }
  function validate(bundle, guide, companion) {
    if (!plain(bundle)||Object.keys(bundle).some(k=>!keys.includes(k)) ||
        keys.some(k=>!Object.hasOwn(bundle,k))) return fail('export_shape_invalid');
    if (bundle.schema!==schema || bundle.declared_by!=='browser_owner' ||
        bundle.sent!==false || bundle.model_weights_included!==false) return fail('export_authority_mismatch');
    if (!plain(bundle.project) || bundle.project.schema!=='preceptoros.mini-project/1' ||
        bundle.project.state!=='DRAFT_ONLY' || bundle.project.owner!=='local_browser' ||
        bundle.project.deployment!=='NOT_SUBMITTED') return fail('project_source_unverified');
    if (!guide||typeof guide.validate!=='function') return fail('existing_mini_validator_missing');
    const checked=guide.validate(bundle.project,companion);
    if (!checked.ok) return fail(checked.cause||'existing_project_invalid');
    // An export may be well formed yet claim a different slug/owner/field.
    // Require exact round-trip to the canonical *existing* Mini validator.
    if (canonical(bundle.project)!==canonical(checked.value))
      return fail('project_field_mismatch');
    const expectedSources=(guide.templates && guide.templates[bundle.project.template]?.sources)||[];
    if (canonical(bundle.source_links)!==canonical(expectedSources))
      return fail('source_links_mismatch');
    if (!Array.isArray(bundle.documents)||bundle.documents.length>maxDocs) return fail('document_count_invalid');
    const docs=[];
    for (const d of bundle.documents) {
      if (!plain(d)||Object.keys(d).some(k=>!['title','content','modified'].includes(k))||
          typeof d.title!=='string'||!d.title.trim()||d.title.length>80||
          typeof d.content!=='string'||d.content.length>100000||
          !(d.modified===null||d.modified===undefined||
            (typeof d.modified==='string'&&d.modified.length<=35))) return fail('document_shape_invalid');
      docs.push({title:d.title.trim(),content:d.content,modified:d.modified||null});
    }
    if (!Array.isArray(bundle.source_links)||bundle.source_links.length>10) return fail('source_links_invalid');
    for (const item of bundle.source_links) {
      if (!plain(item)||typeof item.title!=='string'||item.title.length>120||
          typeof item.url!=='string'||item.url.length>240||
          typeof item.version!=='string'||item.version.length>40) return fail('source_links_invalid');
    }
    return Object.freeze({ok:true,project:checked.value,docs});
  }
  async function prepare(raw, deps) {
    if (typeof raw!=='string'||!raw.trim()) return fail('export_missing');
    if (encode(raw).length>maxBytes) return fail('export_oversized_utf8');
    let value;
    try {value=JSON.parse(raw);}catch (_) {return fail('export_json_invalid');}
    const data=validate(value,deps.guide,deps.companion);
    if (!data.ok)return data;
    try {
      // Only local project+documents. Names or an unsigned export do NOT establish
      // an owner credential or a previously signed node identity.
      const fingerprint=await sha256(canonical({
        schema:schema,project:data.project,documents:data.docs
      }),deps.crypto);
      return Object.freeze({ok:true,state:'DRAFT_ONLY',fingerprint,
        project:data.project,docs:data.docs,documentCount:data.docs.length,
        ownership:'NO_DATA(no_signed_owner_proof)',authority:'NONE',changed:false});
    }catch (_) {return fail('secure_digest_unavailable');}
  }
  function read(storage) {
    try {
      const text=storage.getItem(recoveryKey);
      if (!text) return fail('no_previous_recovery');
      if (encode(text).length>maxRecordBytes) return fail('recovery_record_oversized');
      const record=JSON.parse(text);
      if (!plain(record)||record.schema!==recordSchema||record.state!=='UNVERIFIED_LOCAL'||
        !/^[0-9a-f]{64}$/.test(record.fingerprint||'')||
        typeof record.title!=='string'||record.title.length>80 ||
        !Number.isInteger(record.documents)||record.documents<0||record.documents>maxDocs ||
        record.authority!=='NONE'||record.ownerProof!=='NO_DATA(no_signed_owner_proof)')
        return fail('recovery_record_invalid');
      if(record.projectSnapshot===undefined)return fail('recovery_snapshot_missing');
      if(typeof record.projectSnapshot!=='string'||
         encode(record.projectSnapshot).length>16384)return fail('recovery_snapshot_invalid');
      const stored=storage.getItem(projectKey);
      if(!stored)return fail('recovered_project_missing');
      const current=JSON.parse(stored);
      if(!plain(current)||canonical(current)!==record.projectSnapshot||
         current.title!==record.title)return fail('recovered_project_changed');
      return Object.freeze({ok:true,...record,changed:false});
    }catch (_){return fail('recovery_storage_unavailable');}
  }
  async function apply(raw, consent, storage, deps) {
    if(consent!==true) return fail('explicit_owner_consent_required');
    const pending=await prepare(raw,deps);
    if(!pending.ok)return pending;
    if(!storage||typeof storage.getItem!=='function'||typeof storage.setItem!=='function')
      return fail('owner_storage_unavailable');
    const old={};
    try {
      for(const key of [projectKey,documentsKey,recoveryKey]) old[key]=storage.getItem(key);
      if(old[recoveryKey]!==null){
        const previous=read(storage);
        if(!previous.ok&&previous.cause==='recovery_snapshot_missing'){
          if(!old[projectKey]||!old[documentsKey])return fail('recovered_content_missing');
          const legacy=JSON.parse(old[recoveryKey]);
          if(legacy.fingerprint!==pending.fingerprint)return fail('different_existing_recovery_refused');
          if(canonical(JSON.parse(old[projectKey]))!==canonical(pending.project))
            return fail('recovered_project_changed');
          const docs=JSON.parse(old[documentsKey]);
          if(!Array.isArray(docs)||pending.docs.some(d=>
            !docs.some(saved=>saved&&saved.title===d.title&&saved.content===d.content)))
            return fail('recovered_documents_changed');
          const upgraded={...legacy,projectSnapshot:canonical(pending.project)};
          try{
            storage.setItem(recoveryKey,JSON.stringify(upgraded));
            if(storage.getItem(recoveryKey)!==JSON.stringify(upgraded))throw Error('writeback');
          }catch(_){
            try{storage.setItem(recoveryKey,old[recoveryKey]);}
            catch(__){return fail('rollback_not_verified');}
            return fail('owner_storage_write_failed');
          }
          return Object.freeze({...read(storage),alreadyRecovered:true,migrated:true,changed:true});
        }
        if(!previous.ok)return fail(previous.cause==='recovered_project_changed' ?
          previous.cause : 'existing_recovery_unreadable');
        if(previous.fingerprint===pending.fingerprint) {
          if(!old[projectKey]||!old[documentsKey])return fail('recovered_content_missing');
          const docs=JSON.parse(old[documentsKey]);
          if(!Array.isArray(docs)||pending.docs.some(d=>
            !docs.some(saved=>saved&&saved.title===d.title&&saved.content===d.content)))
            return fail('recovered_documents_changed');
          return Object.freeze({...previous,state:'UNVERIFIED_LOCAL',alreadyRecovered:true});
        }
        return fail('different_existing_recovery_refused');
      }
      if(old[projectKey]!==null){
        const existing=JSON.parse(old[projectKey]);
        if(canonical(existing)!==canonical(pending.project))return fail('existing_project_conflict');
      }
      const savedDocs=old[documentsKey] ? JSON.parse(old[documentsKey]) : [];
      if(!Array.isArray(savedDocs)||savedDocs.length>1000)return fail('documents_storage_invalid');
      const merged=savedDocs.slice();
      for(let i=0;i<pending.docs.length;i++) {
        const d=pending.docs[i];
        if(merged.some(x=>x&&x.title===d.title&&x.content===d.content))continue;
        if(merged.some(x=>x&&x.title===d.title))return fail('document_title_conflict');
        merged.push({id:'mini-'+pending.fingerprint.slice(0,18)+'-'+i,
          title:d.title,content:d.content,created:d.modified||'NO_DATA(source_modified_time_missing)',
          modified:d.modified||'NO_DATA(source_modified_time_missing)',state:'saved'});
      }
      const record={schema:recordSchema,state:'UNVERIFIED_LOCAL',
        fingerprint:pending.fingerprint,title:pending.project.title,
        documents:pending.documentCount,ownerProof:'NO_DATA(no_signed_owner_proof)',
        authority:'NONE',sourceSchema:schema,
        projectSnapshot:canonical(pending.project)};
      // Preserve pre-existing user data. Roll back every touched key on failure.
      let wrote=false;
      try{
        storage.setItem(projectKey,JSON.stringify(pending.project));wrote=true;
        storage.setItem(documentsKey,JSON.stringify(merged));
        storage.setItem(recoveryKey,JSON.stringify(record));
        if(storage.getItem(recoveryKey)!==JSON.stringify(record))
          throw Error('recovery_readback_failed');
      }catch(_){
        if(wrote){
          try{
            for(const key of [projectKey,documentsKey,recoveryKey]){
              if(old[key]===null)storage.removeItem(key);
              else storage.setItem(key,old[key]);
            }
          }catch(__){return fail('rollback_not_verified');}
        }
        return fail('owner_storage_write_failed');
      }
      return Object.freeze({ok:true,...record,changed:true});
    }catch(_){return fail('owner_storage_unavailable_or_corrupt');}
  }
  function mount(doc,storage,deps){
    const host=doc.getElementById('mini-recovery');
    if(!host||host.dataset.mounted==='1')return false;
    host.dataset.mounted='1';
    const by=id=>doc.getElementById(id);
    const state=by('mini-recovery-state'),lab=by('lab-mini-recovery-state');
    const source=by('mini-recovery-json'),file=by('mini-recovery-file');
    const consent=by('mini-recovery-consent'),review=by('mini-recovery-preview');
    const previewBtn=by('mini-recovery-preview-button'),importBtn=by('mini-recovery-import');
    function paint(text,level,cause){
      for(const e of [state,lab].filter(Boolean)){
        e.textContent=text;e.dataset.state=e.dataset.acho=level;e.dataset.cause=cause;
      }
    }
    function sync(){
      const last=read(storage);
      if(last.ok)paint('UNVERIFIED_LOCAL · Recovered MINI project: '+last.title+
        '. Content SHA-256 '+last.fingerprint.slice(0,16)+
        '…; owner proof NO_DATA. No node request or model activation.',
        'UNVERIFIED_LOCAL','no_signed_owner_proof');
      else paint('NO_DATA('+last.cause+') · No previous MINI project linked on this device.',
        'NO_DATA',last.cause);
    }
    let staged=null,raw=null;
    file?.addEventListener('change',async()=>{
      staged=null;raw=null;
      const item=file.files&&file.files[0];
      if(!item)return;
      if(item.size>maxBytes){paint('NO_DATA(export_oversized_utf8)','NO_DATA','export_oversized_utf8');return;}
      try{
        const content=await item.text();
        source.value=content;paint('File selected locally. Preview before importing.',
          'DRAFT_ONLY','awaiting_owner_review');
      }catch(_){paint('NO_DATA(file_read_failed)','NO_DATA','file_read_failed');}
    });
    previewBtn?.addEventListener('click',async()=>{
      raw=source.value;
      staged=await prepare(raw,deps);
      if(!staged.ok){
        review.textContent='NO_DATA('+staged.cause+')';
        paint(review.textContent,'NO_DATA',staged.cause);
        importBtn.disabled=true;return;
      }
      review.textContent='Project: '+staged.project.title+'; documents: '+
        staged.documentCount+'; project+documents SHA-256 (NOT owner fingerprint): '+staged.fingerprint+
        '. No signed owner credential included. Model and node permissions NOT imported.';
      paint('DRAFT_ONLY · Review the file, then consent explicitly.',
        'DRAFT_ONLY','owner_consent_not_yet_given');
      importBtn.disabled=!consent.checked;
    });
    consent?.addEventListener('change',()=>{importBtn.disabled=!(staged?.ok&&consent.checked);});
    source?.addEventListener('input',()=>{staged=null;raw=null;importBtn.disabled=true;});
    importBtn?.addEventListener('click',async()=>{
      importBtn.disabled=true;
      const result=await apply(raw,consent.checked,storage,deps);
      if(!result.ok){paint('NO_DATA('+result.cause+') · No node requested.',
        'NO_DATA',result.cause);return;}
      consent.checked=false;
      sync();
      review.textContent='Local project restored. This is NOT verified owner or node identity; reopen Lab to inspect the documents.';
    });
    sync();return true;
  }
  const API=Object.freeze({schema:schema,recordSchema:recordSchema,maxBytes:maxBytes,
    validate,prepare,apply,read,mount,canonical});
  root.PreceptorMiniRecovery=API;
  if(typeof module==='object'&&module.exports)module.exports=API;
})(typeof window==='undefined'?globalThis:window);
