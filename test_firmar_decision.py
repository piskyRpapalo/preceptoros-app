"""HEX-NODE3-11: the Sovereign's own decision tool signs only with the anchor key and verifies before sending."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, skipUnless
import importlib.util
import io
import json
import shutil
import subprocess
from contextlib import redirect_stdout
from unittest import mock

spec = importlib.util.spec_from_file_location("firmar_decision", Path(__file__).parent / "bin" / "firmar_decision.py")
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)
REF = "ab" * 32


@skipUnless(shutil.which("ssh-keygen"), "OpenSSH unavailable")
class SovereignTool(TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.d = Path(tmp.name)
        for name in ("anchor", "other"):
            subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C", "comment here",
                            "-f", str(self.d / name)], check=True)
        # Same shape as the real anchor file: cédula namespace only.
        (self.d / "allowed").write_text('soberano namespaces="preceptoros-cedula" '
                                        + (self.d / "anchor.pub").read_text())

    def run_tool(self, key, *extra, post=None):
        out = io.StringIO()
        with redirect_stdout(out), mock.patch.object(F.urllib.request, "urlopen", post or mock.Mock()) as sent:
            try:
                code = F.main([REF, "APPROVED", "--key", str(self.d / key), "--allowed", str(self.d / "allowed"), *extra])
            except SystemExit as exc:
                code = exc.code
        return code, out.getvalue(), sent

    def test_anchor_key_signs_verifies_and_sends_a_fresh_canonical_decision(self):
        reply = mock.MagicMock(status=202)
        reply.__enter__.return_value = reply
        reply.read.return_value = b"{}"
        code, _out, sent = self.run_tool("anchor", post=mock.Mock(return_value=reply))
        self.assertEqual(code, 0)
        request = sent.call_args[0][0]
        self.assertTrue(request.full_url.endswith(f"/api/v1/deployment-requests/{REF}/decision"))
        body = json.loads(request.data)
        self.assertEqual(set(body), {"schema", "request_id", "request_sha256", "decision", "nonce", "issued_at",
                                     "expires_at", "firma_ssh"})
        self.assertEqual((body["request_id"], body["request_sha256"], body["decision"]), (REF, REF, "APPROVED"))
        self.assertIn("BEGIN SSH SIGNATURE", body["firma_ssh"])
        self.assertNotIn("PRIVATE KEY", request.data.decode())

    def test_any_other_key_is_refused_locally_and_nothing_is_sent(self):
        code, _out, sent = self.run_tool("other")
        self.assertIn("verification FAILED", str(code))
        sent.assert_not_called()

    def test_dry_run_and_bad_reference_send_nothing(self):
        code, out, sent = self.run_tool("anchor", "--dry-run")
        self.assertEqual(code, 0); self.assertIn("dry run", out); sent.assert_not_called()
        with self.assertRaises(SystemExit):
            F.main(["not-a-ref", "APPROVED", "--key", str(self.d / "anchor"), "--allowed", str(self.d / "allowed")])
