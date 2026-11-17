/* Zonas de la pestaña única: datos de presentación, sin navegación ni autoridad.
 * Four main zones: Chat · Documents · Lab · My node.
 * Advanced zones (Command, Boundary, Notebook, Harness, World) are hidden by default
 * and accessible via Technical Options in the header.
 */
"use strict";
(function (root) {
  const zonas = Object.freeze([
    Object.freeze({ id: "mando", panel: "mando", titulo: "Mando" }),
    Object.freeze({ id: "conversacion", panel: "conversacion", titulo: "Conversación" }),
    Object.freeze({ id: "gobierno", panel: "gobierno", titulo: "Gobierno" }),
    Object.freeze({ id: "cuaderno", panel: "cuaderno", titulo: "Cuaderno" }),
    Object.freeze({ id: "lab", panel: "lab", titulo: "Lab" }),
    Object.freeze({ id: "harness", panel: "harness", titulo: "Harness" }),
    Object.freeze({ id: "modelos", panel: "modelos", titulo: "Modelos" }),
    Object.freeze({ id: "ajustes", panel: "ajustes", titulo: "Ajustes" }),
    Object.freeze({ id: "documentos", panel: "documentos", titulo: "Documentos" }),
  ]);
  root.PreceptorZonas = Object.freeze({ zonas });
})(window);
