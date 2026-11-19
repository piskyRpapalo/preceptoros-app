/* preceptoros.ui-preferences/1 · browser-only reversible preferences.
 * Values are allowlisted; no node, model, document or network mutation.
 */
"use strict";
(function (win, doc) {
  const root = doc.documentElement;
  const themeInputs = [...doc.querySelectorAll('input[name="settings-theme"]')];
  const textInputs = [...doc.querySelectorAll('input[name="settings-text"]')];
  const motion = doc.getElementById("settings-reduce-motion");
  const reset = doc.getElementById("settings-reset");
  const status = doc.getElementById("settings-status");
  const key = "preceptoros.ui-preferences/1";
  const schemes = ["system","light","dark"];
  const sizes = ["normal","large"];
  const systemDark = win.matchMedia("(prefers-color-scheme: dark)");
  const systemMotion = win.matchMedia("(prefers-reduced-motion: reduce)");
  const defaults = { theme:"light", text:"normal", reducedMotion:false };
  let settings = {...defaults};

  try {
    const value = JSON.parse(win.localStorage.getItem(key) || "null");
    if (value && typeof value === "object") {
      if (schemes.includes(value.theme)) settings.theme=value.theme;
      if (sizes.includes(value.text)) settings.text=value.text;
      settings.reducedMotion = value.reducedMotion === true;
    }
  } catch { /* A blocked or corrupt preference file never prevents using APP. */ }

  function paint() {
    const dark = settings.theme === "dark" ||
      (settings.theme === "system" && systemDark.matches);
    const reduce = settings.reducedMotion || systemMotion.matches;
    root.dataset.theme = dark ? "dark" : "light";
    root.dataset.themeChoice = settings.theme;
    root.dataset.textScale = settings.text;
    root.dataset.reduceMotion = String(reduce);
    root.style.colorScheme = dark ? "dark" : "light";
    const meta = doc.querySelector('meta[name="theme-color"]');
    if (meta) meta.content=dark ? "#1a1830" : "#f4ecda";
    for (const el of themeInputs) el.checked=el.value===settings.theme;
    for (const el of textInputs) el.checked=el.value===settings.text;
    if (motion) motion.checked=settings.reducedMotion;
    if (status) {
      status.dataset.acho="ok";
      status.dataset.state="LOCAL";
      status.textContent="Display preferences apply in this browser only.";
    }
  }
  function save() {
    try {win.localStorage.setItem(key,JSON.stringify(settings));}
    catch {if (status) status.textContent="Display changed for this visit; local saving is unavailable.";}
  }
  function update(next) { settings={...settings,...next};paint();save(); }
  for (const input of themeInputs) input.addEventListener("change", () => {
    if (input.checked && schemes.includes(input.value)) update({theme:input.value});
  });
  for (const input of textInputs) input.addEventListener("change", () => {
    if (input.checked && sizes.includes(input.value)) update({text:input.value});
  });
  if (motion) motion.addEventListener("change",()=>update({reducedMotion:motion.checked}));
  if (reset) reset.addEventListener("click",()=>{
    settings={...defaults};paint();save();
    if (status) status.textContent="Display defaults restored. Node identity and documents were not touched.";
  });
  systemDark.addEventListener("change",()=>{if(settings.theme==="system")paint();});
  systemMotion.addEventListener("change",paint);
  paint();
  win.PreceptorPreferences = Object.freeze({get:()=>({...settings}),set:update});
})(window,document);
