#!/usr/bin/env python3
"""The Sovereign's own decision tool. HE runs it, on HIS machine, with HIS key. Nobody else may.

    python3 firmar_decision.py <request_id> APPROVED|REJECTED|REVOKED --key ~/.ssh/<his registro_v2 key>
        [--allowed ~/.preceptoros/allowed_signers_cedula] [--api https://api.preceptoros.org] [--dry-run]

It builds preceptoros.deployment-decision/1 with a fresh window (Aduana accepts ≤300 s), signs it with
`ssh-keygen -Y sign -n preceptoros-deployment-decision`, VERIFIES the signature locally as principal «soberano»
against the allowed_signers file before sending, and POSTs it. The private key never leaves ssh-keygen.
"""
import argparse, json, os, re, secrets, subprocess, sys, tempfile, urllib.error, urllib.request
from datetime import datetime, timedelta, timezone

NS = "preceptoros-deployment-decision"
REF = re.compile(r"^[0-9a-f]{64}$")


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode("ascii")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("request_id"); p.add_argument("decision", choices=["APPROVED", "REJECTED", "REVOKED"])
    p.add_argument("--key", required=True)
    p.add_argument("--allowed", default=os.path.expanduser("~/.preceptoros/allowed_signers_cedula"))
    p.add_argument("--api", default="https://api.preceptoros.org")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args(argv)
    if not REF.fullmatch(a.request_id):
        sys.exit("request_id must be 64 lowercase hex")
    now = datetime.now(timezone.utc).replace(microsecond=0)
    fmt = "%Y-%m-%dT%H:%M:%SZ"
    body = {"schema": "preceptoros.deployment-decision/1", "request_id": a.request_id,
            "request_sha256": a.request_id, "decision": a.decision, "nonce": secrets.token_hex(16),
            "issued_at": (now - timedelta(seconds=5)).strftime(fmt),
            "expires_at": (now + timedelta(seconds=240)).strftime(fmt)}
    with tempfile.TemporaryDirectory() as tmp:
        doc = os.path.join(tmp, "decision.json")
        with open(doc, "wb") as f:
            f.write(canonical(body))
        subprocess.run(["ssh-keygen", "-q", "-Y", "sign", "-n", NS, "-f", a.key, doc], check=True)
        # The anchor file pins the soberano key for the cédula namespace; reuse THAT key for this namespace.
        anchor = [l.split() for l in open(a.allowed, encoding="ascii") if l.split()[:1] == ["soberano"]]
        if len(anchor) != 1:
            sys.exit("allowed_signers must hold exactly one «soberano» line: nothing sent")
        at = next((i for i, w in enumerate(anchor[0]) if w.startswith("ssh-")), None)
        if at is None or at + 1 >= len(anchor[0]):
            sys.exit("allowed_signers «soberano» line has no ssh key: nothing sent")
        keytype, keyb64 = anchor[0][at], anchor[0][at + 1]
        allowed = os.path.join(tmp, "allowed")
        with open(allowed, "w", encoding="ascii") as f:
            f.write(f'soberano namespaces="{NS}" {keytype} {keyb64}\n')
        with open(doc, "rb") as f:
            verified = subprocess.run(["ssh-keygen", "-Y", "verify", "-f", allowed, "-I", "soberano", "-n", NS,
                                       "-s", doc + ".sig"], stdin=f, capture_output=True, text=True)
        if verified.returncode != 0:
            sys.exit("local verification FAILED (wrong key or allowed_signers): nothing sent")
        body["firma_ssh"] = open(doc + ".sig", encoding="ascii").read()
    print(f"{a.decision} for {a.request_id[:12]}… signed and verified locally as «soberano»")
    if a.dry_run:
        print("dry run: not sent"); return 0
    url = f"{a.api}/api/v1/deployment-requests/{a.request_id}/decision"
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            status, reply = r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        status, reply = e.code, e.read().decode()
    print("Aduana:", status, reply[:300])
    return 0 if status in (200, 202) else 1


if __name__ == "__main__":
    raise SystemExit(main())
