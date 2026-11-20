/* PreceptorOS APP first run and owner-local public chatbot template.
 * No fetch, no model download, no auto-submission, no hidden publication.
 * Only owner actions write to storage; never stores a node credential here. */
(function (root) {
  "use strict";
  const d=root.document;
  if (!d) return;
  const $=id=>d.getElementById(id);
  const seenKey="preceptoros.app-first-run/1";
  const draftKey="preceptoros.node-public-template/1";
  const defaultName="My companion";
  const defaultDescription="A personal experimental assistant for research, writing and learning. Its owner controls its data and permissions.";
  const defaultPrompt="You are an experimental PreceptorOS companion. Answer clearly and briefly using only the capabilities available to you. Do not invent facts, tools, connections or actions. Explain uncertainty. Never disclose private information. Your owner must authorize any external action.";
  const clean=(v,n)=>typeof v==="string" && v.trim().length>0 && v.trim().length<=n &&
    ![...v].some(c=>c.charCodeAt(0)<32 || c.charCodeAt(0)===127 || c==="<" || c===">") ? v.trim() : null;
  function mark(el,state,cause,text) {
    if (!el) return;
    el.dataset.state=state;el.dataset.acho=state;el.dataset.cause=cause;
    if (typeof text==="string")el.textContent=text;
  }
  const guide=$("mvp-first-run"),feedback=$("mvp-first-run-state");
  function showGuide() {
    if (!guide) return;
    guide.hidden=false;
    mark(guide,"GUIDE_ONLY","reopened_by_owner");
    mark(feedback,"GUIDE_ONLY","intro_open","Introduction is available. No node request has been sent.");
    guide.scrollIntoView?.({block:"nearest",behavior:"auto"});
    $("mvp-first-run-title")?.setAttribute("tabindex","-1");
    $("mvp-first-run-title")?.focus({preventScroll:true});
  }
  function openNode() {
    $("tab-ajustes")?.click();
    const identity=$("ajustes-nodo");
    if (!identity) return;
    identity.open=true;
    $("mynode-identity-toggle")?.setAttribute("aria-expanded","true");
    const field=$("node-default-name");
    field?.focus({preventScroll:true});
    field?.scrollIntoView?.({block:"nearest",behavior:"auto"});
  }
  function goMini() {
    // A previous MINI export is not discoverable across browser/WebView origins.
    // Bring its explicit owner-controlled recovery control into view instead
    // of misleadingly treating a model switch as identity recognition.
    if ($("mini-recovery")) {
      $("tab-ajustes")?.click();
      const node=$("ajustes-nodo");
      if (node) node.open=true;
      $("mynode-identity-toggle")?.setAttribute("aria-expanded","true");
      $("mini-recovery-file")?.focus({preventScroll:true});
      $("mini-recovery")?.scrollIntoView?.({block:"nearest",behavior:"auto"});
      mark(feedback,"NO_DATA","prior_export_required",
        "Choose your earlier MINI project export to recover locally. Ownership and node admission are not verified.");
      return;
    }
    $("tab-conversacion")?.click();
    // The existing Mini toggle lives inside the model picker dialog.
    // Reveal its existing owner before transferring focus; no implicit click.
    if ($("modelos-menu")?.hidden)$("modelos-toggle")?.click();
    $("mini-local-toggle")?.focus({preventScroll:true});
    mark(feedback,"GUIDE_ONLY","mini_mode_not_activated",
      "Mini Orchestrator is optional. Activate offline mode yourself; this guide did not run a model.");
  }
  if (guide) {
    try {if (root.localStorage.getItem(seenKey)==="done")guide.hidden=true;}
    catch {mark(feedback,"NO_DATA","local_storage_unavailable",
      "This browser cannot remember introduction preferences. No node data has been sent.");}
    $("mvp-first-run-mini")?.addEventListener("click",goMini);
    $("mvp-first-run-node")?.addEventListener("click",openNode);
    $("mvp-first-run-finish")?.addEventListener("click",()=>{
      try {
        root.localStorage.setItem(seenKey,"done");
        guide.hidden=true;
        mark(feedback,"SAVED_LOCAL","explicit_owner_choice","Introduction dismissed on this device.");
      } catch {
        mark(feedback,"NO_DATA","local_storage_unavailable",
          "Unable to remember your choice on this device. No information was sent.");
      }
    });
    $("mvp-first-run-reopen")?.addEventListener("click",()=>{
      $("tab-conversacion")?.click();showGuide();
    });
  }
  const box=$("node-public-template"),name=$("node-default-name"),
    description=$("node-default-description"),prompt=$("node-default-prompt"),status=$("node-default-status");
  if (!box||!name||!description||!prompt||!status)return;
  $("lab-first-experiment")?.addEventListener("click",()=>{
    $("tab-cuaderno")?.click();
    const writer=$("plan-escribir");
    if (!writer) return;
    writer.open=true;
    $("notebook-plan-toggle")?.setAttribute("aria-expanded","true");
    $("plan-titulo")?.focus({preventScroll:true});
    // No initial text is inserted, stored, or dispatched without owner action.
  });
  function draftState(kind,cause,text) {
    mark(box,kind,cause); mark(status,kind,cause,text);
  }
  // Read only a previously owner-saved and schema-checked local draft.
  try {
    const raw=root.localStorage.getItem(draftKey);
    if (raw) {
      const saved=JSON.parse(raw);
      const n=saved?.schema==="preceptoros.node-public-template/1" && clean(saved.name,64);
      const p=saved?.schema==="preceptoros.node-public-template/1" && clean(saved.prompt,1024);
      const text=saved?.schema==="preceptoros.node-public-template/1" &&
        (saved.description===undefined ? defaultDescription : clean(saved.description,240));
      if (n&&p&&text) {
        name.value=n;description.value=text;prompt.value=p;
        draftState("SAVED_LOCAL","owner_saved_draft",
          "Local public-chatbot draft restored. Not published or connected to a model.");
      } else {
        draftState("NO_DATA","saved_template_invalid",
          "The saved draft could not be validated. Editable example retained; nothing published.");
      }
    }
  } catch {
    draftState("NO_DATA","local_storage_unavailable",
      "Unable to load local draft. The editable example is available; nothing published.");
  }
  $("node-default-save")?.addEventListener("click",()=>{
    const n=clean(name.value,64),what=clean(description.value,240),
      instructions=clean(prompt.value,1024);
    if (!n||!what||!instructions) {
      draftState("NO_DATA","template_invalid",
        "Enter a name, short description and instructions (max 64, 240 and 1024 characters).");
      return;
    }
    const record={schema:"preceptoros.node-public-template/1",name:n,description:what,prompt:instructions};
    try {
      root.localStorage.setItem(draftKey,JSON.stringify(record));
      draftState("SAVED_LOCAL","explicit_owner_save",
        "Saved on this device only. No node registered, agent started or content published.");
    } catch {
      draftState("NO_DATA","local_storage_unavailable",
        "This device could not save your draft. No request or publication was sent.");
    }
  });
  $("node-default-reset")?.addEventListener("click",()=>{
    name.value=defaultName;description.value=defaultDescription;prompt.value=defaultPrompt;
    draftState("DRAFT_ONLY","example_restored_not_saved",
      "Example restored in the editor. Select Keep these defaults to save it on this device.");
  });
  // Suggest a new local draft identity; never authorize, sign or register it.
  // The existing owner ID is immutable from this helper.
  $("node-default-id")?.addEventListener("click",()=>{
    const input=$("node-identity-id"),proposed=$("node-registration-name");
    if (!input || !root.crypto?.getRandomValues) {
      draftState("NO_DATA","secure_random_or_form_unavailable",
        "This device cannot safely suggest an ID. You may enter your own ID.");
      return;
    }
    if (input.value.trim()) {
      draftState("DRAFT_ONLY","existing_node_identity_preserved",
        "A node ID is already present. Nothing was changed or registered.");
      input.focus({preventScroll:true});
      return;
    }
    const slug=(clean(name.value,64)||"companion").normalize("NFKD")
      .replace(/[̀-ͯ]/g,"").toLowerCase()
      .replace(/[^a-z0-9]+/g,"-").replace(/^-|-$/g,"").slice(0,24)||"companion";
    const random=new Uint32Array(1); root.crypto.getRandomValues(random);
    const candidate="nodo."+String(100000+(random[0]%900000))+"."+slug;
    input.value=candidate;
    input.dispatchEvent(new Event("input",{bubbles:true}));
    if (proposed&&!proposed.value.trim()) {
      proposed.value=candidate;
      proposed.dispatchEvent(new Event("input",{bubbles:true}));
    }
    draftState("DRAFT_ONLY","suggestion_only_not_verified",
      "Suggested ID copied to the local identity form. It is not saved, registered, unique or approved.");
    input.focus({preventScroll:true});
  });
  root.PreceptorFirstRun=Object.freeze({
    state:()=>Object.freeze({guide:guide?.hidden?"DISMISSED":"GUIDE_ONLY",
      template:box.dataset.state,publication:"NOT_AUTHORIZED",model:"NOT_VERIFIED"})
  });
})(typeof window==="object"?window:globalThis);
