/* Exactly six main zones. Memory lives in Notebook; Boundary and Harness in Lab.
 * The sections remain local readers, not duplicate tabs or authorization channels.
 */
"use strict";
(function (root) {
  const zonas = Object.freeze([
    Object.freeze({ id: "conversacion", panel: "conversacion", titulo: "Conversación" }),
    Object.freeze({ id: "cuaderno", panel: "cuaderno", titulo: "Operations Data" }),
    Object.freeze({ id: "lab", panel: "lab", titulo: "Lab" }),
    Object.freeze({ id: "modelos", panel: "modelos", titulo: "Modelos" }),
    Object.freeze({ id: "ajustes", panel: "ajustes", titulo: "Ajustes" }),
    Object.freeze({ id: "settings", panel: "settings", titulo: "Settings" }),
  ]);
  root.PreceptorZonas = Object.freeze({ zonas });
})(window);
