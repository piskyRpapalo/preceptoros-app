# Recibo · app-superbot-ux-02 (V1 fixes)

**Fecha:** 2026-11-17  
**Autor:** Junie (Célula APP)  
**Autoridad:** Soberano  
**Estado:** DRAFT PR #328 — bloqueos V1 resueltos  

## HEAD

```
1f20dcca1a650f4f8d5242daa82d004991d2b93f
fix: app-mvp-v1 — navigation, PWA, accessibility, profile identity
```

Rama: `junie/app-superbot-ux-02`  
Base: `origin/main` (`aadb2d4`)  
PR #328: https://github.com/piskyRpapalo/preceptoros-app/pull/328

## Bloqueos V1 resueltos

1. **Navegación rota**: `app.js` usaba índice del DOM para mapear clics de pestaña a paneles. Corregido para usar `data-panel` ID. Documents, Lab y My node ahora seleccionan paneles correctos.
2. **documents.js HTTP 404**: Faltaba en `ESTATICOS` de `bin/preceptoros-pwa`. Añadido y verificado.
3. **Accesibilidad Technical Options**: Escape cierra y devuelve foco, flechas navegan items, `role="menuitem"` en botones, foco automático en primer item al abrir.
4. **Identidad de perfil**: `PreceptorProfile` nunca se establecía; conversacion.js caía a "personal_mvp" siempre. Ahora se lee desde localStorage y hay selector visible en My node. Perfil explícito, no detectado.
5. **Recibo sin seguimiento**: `app-superbot-ux-02-receipt-20261117.md` añadido al commit.

## Cambios V1

- **Navigation**: Tab clicks mapped by `data-panel` id, not DOM index
- **PWA server**: `documents.js` registered in `bin/preceptoros-pwa` ESTATICOS
- **Accessibility**: Technical Options — Escape + focus return, arrow keys, role=menuitem
- **Profile identity**: localStorage-based, explicit selector in My node, no auto-detection
- **Versions**: app.js v45, app.css v34, sw cache v209

## Archivos modificados (V1)

| Archivo | Cambio |
|---------|--------|
| `interface/app.js` | Navigation by ID, profile init, Technical Options a11y, v45 |
| `interface/app.html` | Profile selector in My node, Technical Options role=menuitem, v34 |
| `interface/sw.js` | Cache v209, app.js v45, app.css v34 |
| `bin/preceptoros-pwa` | documents.js in ESTATICOS |
| 16 test files | Version references updated to v45/v34/v209 |

## Pruebas

```
./bin/pruebas --rapido (×2) → 10 suites fallando (igual que baseline)
node -c → todos los JS OK
git diff --check → limpio
```

### Fallos preexistentes (no causados por este cambio)

- test_app_una_pestana.py (11)
- test_estado_app.py (9)
- test_pwa.py (107)
- test_guardrails.py (39)
- test_app_mvp_trim.py (5)
- test_app_english_freeze.py (5)
- test_cabin_brain.py (6)
- test_public_names.py (3)
- test_conversacion_comun.py (13)
- test_idioma.py (15/17)

**Cero regresiones nuevas.** Los 10 fallos coinciden exactamente con la base stashed.

## Límites

- RAG personal: camino documentado, no funcional
- team.js agents: estilos de respuesta, no procesos reales
- Voice control: NO_DATA(voice_command_recognition_not_built)
- PR #327 (`codex/app-talk-local-01`): no tocado
- Worktrees WEB, Claude, Codex CLI: no tocados
- app-all.bundle: no añadido al commit (archivo sin rastrear)

## Firma

Junie · 2026-11-17T20:10 · Co-authored-by: Junie <junie@jetbrains.com>
