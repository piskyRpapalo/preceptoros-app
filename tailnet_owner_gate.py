"""Owner-only HTTPS Serve browser context for the existing *model chat* route.

Not a grant issuer, login service, MCP gate or generic network permission.
Tailscale Serve strips client-supplied identity headers before injecting its
authenticated tailnet identity. A proxy-only header is trustworthy ONLY when
the backend is bound to 127.0.0.1, not if it is accessible from LAN.

This is a narrow opt-in for POST /api/hexelion/chat. It never permits
actions, shell, model downloads, agent dispatch or arbitrary model selection.
Empty environment settings keep it disabled. Do not add a second endpoint.
Reference: https://tailscale.com/docs/features/tailscale-serve#identity-headers
"""
from __future__ import annotations

import ipaddress
import re

_HOST = re.compile(r"^[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.[a-z0-9][a-z0-9-]{1,62}\.ts\.net$")
_LOGIN = re.compile(r"^[^\s@]{1,64}@[A-Za-z0-9.-]{1,160}$")


def authorize(headers, peer_ip, *, host, owner_login, backend_bind):
    """(bool, cause) with no echo of login or host.

    Requires the pre-existing private Tailscale Serve reverse proxy and a
    local-only backend. Matching an identity header is NOT an S1 task grant.
    """
    if type(host) is not str or not _HOST.fullmatch(host):
        return False, "remote_chat_owner_host_not_configured"
    if type(owner_login) is not str or not _LOGIN.fullmatch(owner_login):
        return False, "remote_chat_owner_identity_not_configured"
    if backend_bind not in ("127.0.0.1", "::1"):
        return False, "remote_chat_backend_not_loopback_bound"
    try:
        if not ipaddress.ip_address(peer_ip).is_loopback:
            return False, "remote_chat_proxy_not_loopback"
    except (TypeError, ValueError):
        return False, "remote_chat_proxy_not_loopback"
    if (headers.get("Host") != host
            or headers.get("Origin") != "https://" + host
            or headers.get("Sec-Fetch-Site") != "same-origin"):
        return False, "remote_chat_origin_not_matching"
    if headers.get("Tailscale-User-Login") != owner_login:
        return False, "remote_chat_owner_identity_not_matching"
    return True, "serve_identity_header_matches_owner_config"
