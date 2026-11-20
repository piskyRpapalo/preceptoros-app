# RETOMA DEL CEREBRO · owner-only remote model chat over existing APP door

Status: DRAFT / exact-head HITL review. 2026-11-20.
Coordinates: private Mesa #51, APP shared Rack LAB PR #369.
This is a narrowly scoped second software slice, not another application,
MCP, model server, permission system, or mission.

## Problem and source

The canonical APP's Talk calls POST /api/hexelion/chat and receives a
verified-citation model reply from the existing rack proxy. Currently only
a local browser origin or a loopback CLI voice is allowed. Tailscale Serve
already makes the read-only APP available across the owner's tailnet, but
an external phone browser's HTTPS Origin is deliberately refused by the
local chat gate. The owner wants secure model discussion while travelling.

Official source for the identity boundary:
https://tailscale.com/docs/features/tailscale-serve#identity-headers .
Tailscale Serve strips client-provided identity headers and injects
Tailscale-User-Login for authenticated tailnet requests. This is trustworthy
only on a backend that listens exclusively on loopback. Tailscale membership
alone does not substitute for the existing S1 task authorization.

## Adaptation to the current rack

- Preserve the EXACT POST /api/hexelion/chat route, no new listening port or
  Ollama endpoint. Only this route can opt into a remote person.
- The remote owner gate remains OFF unless a private operator explicitly
  configures both PRECEPTOROS_CHAT_TAILNET_HOST (exact two-label .ts.net name)
  and PRECEPTOROS_CHAT_OWNER_LOGIN (exact owner login). Values are never in Git.
- Require real loopback listener and peer, exact HTTPS Origin, exact Host,
  Sec-Fetch-Site=same-origin, and Serve-injected owner identity.
- Remote requests MAY ask the fixed Hexelion model a normal text question,
  subject to the existing context, citations and 1,023-byte reply constraint.
- Remote requests MAY NOT execute existing /commands, native MCP actions,
  interpreted natural-language tools, local energy commands, or claim a CLI
  voice. Deny before writing to the conversation journal. Local authorized
  browser behavior remains unchanged.
- A model file in a device/backend is not an activated endpoint. Additional
  locally hosted or remote rack models must later use a host-verified allowlist,
  fixed model digest, S1 host grant and LoRA/KV pin; user-provided URLs or
  free-form model identifiers are not accepted in this slice.
- No added CORS wildcard and no authentication or secrets in browser
  localStorage. Tailscale Serve stays private; NEVER use public Funnel for
  this route.

## Measurable and limits

Synthetic tests: correct exact owner context accepted; missing environment,
wrong peer, wildcard binding, forged login, wrong Origin, cross-site calls,
remote actions, and impersonated CLI voice denied. Explicit tests verify no
MCP dispatch or journal append for denied remote action requests.

This result is a *gate contract*, not a live authorized remote inference.
NO_DATA(real_owner_header_on_phone) · NO_DATA(S1_remote_model_grant) ·
NO_DATA(multi_model_remote_catalog) · NO_DATA(Tank3_HTTPS_chat_E2E) ·
NO_DATA(owner_host_configuration_enabled).

## Next physical acceptance

1. Exact-head APP CI and human review/FIRMO before merge. Verify current
   PWA backend is bound to loopback, and Serve proxy is private.
2. Owner configures its private exact host/login via its already controlled
   service environment (not GitHub, UI or browser). Keep model capability
   *off* until negative tests pass on the live endpoint.
3. On an authorized phone with Tailscale, open the existing private APP and
   test one read-only model question while another independent process
   witnesses model digest, no action dispatch, response citations and receipt.
4. Repeat from non-owner/share login: HTTP403 before writing or dispatch.
   Verify after Serve identity revocation and after stale model failure.
5. Only then report VERIFIED(owner_remote_model_chat_E2E). Android's offline
   APK is a separate origin requiring a signed, owner-controlled native
   transport or the existing external-browser link; this code does not
   silently upgrade a native APK.

Rollback: unset the two private env settings; the route immediately returns
to the original local-only behavior. No user data or models are migrated.

— Codex GPT-6 · Olin. All status is explicit; no fabricated owner signature.
