# APP-MVP-TRIM · Rack APP simplified navigation

Owner: preceptoros-app. Proposal, not a deployment.
Source: APP interface/app.html, interface/app.js, interface/zonas.js, interface/sw.js;
Sovereign's 2026-11-17 directive to retire the 3D creator and drop video-creator proposals.

## Problem
The live rack APP exposes nine panels, including a 3D draft-only feature whose printing engine is
not integrated. This distracts from essential activities; a node proposal looks too
similar to deployment even though end-to-end deployment was not measured.

## Adaptation
Four default tabs: Command, Talk, World, Settings. Boundary, Notebook, Lab and Harness are opt-in
specialist tabs available from Settings, including incoming deep links. The 3D panel and
its client-only logic, navigation, old UI-only tests and styles are removed. Existing 3D browser
storage is NOT cleared or migrated. No video creator exists in the active app shell.
The node setup shortcut opens existing local identity controls and performs a read only.
It never creates SSH keys or claims to deploy a node.

## Acceptance and measurement
- Eight panels, four visible by default, four available when requested.
- Main, historical payload schemas, backend endpoints, machine stores and signed grants unchanged.
- Keyboard and arrow navigation skip hidden tabs; deep links to advanced panels reveal them.
- Eye/ear/machine state agrees: labels, status text, data-state and data-acho.
- Chrome loopback browser smoke at 360 and 420 px; zero unexpected JS exceptions.
- Two full bin/pruebas gates, sabotage RED and MVP-specific tests.
- APP SW cache increment proposed v205 and script query pins reconciled; Mesa lease pending.

## Limits
NO_DATA(physical_phone_update_not_tested).
NO_DATA(remote_node_deployment_E2E_not_verified).
NO_DATA(screen_reader_assistive_hardware_not_tested).
No change to WEB/OpenWorld APK or public distribution.
Do not merge or deploy without Sovereign exact-head FIRMO.
