"""Private local GitHub snapshot adapter; merged github_bootstrap stays canonical."""
import datetime as dt
from contextlib import closing
import json
import os
from pathlib import Path
import runpy
import tempfile
import threading
import unittest
from unittest import mock
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import github_bootstrap as G
import github_snapshot_read as R

NOW = dt.datetime(2026, 11, 20, 4, 0, tzinfo=dt.timezone.utc)


class GitHubSnapshotReadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.parent = self.root / "sources"
        self.parent.mkdir(mode=0o700)
        self.file = self.parent / "github-owner-snapshot.json"
        self.snapshot = {
            "schema": G.IN_SCHEMA, "source": "github.com", "owner": "owner-1",
            "repositories": [
                {"name": "lab", "full_name": "owner-1/lab",
                 "html_url": "https://github.com/owner-1/lab", "private": False,
                 "fork": False, "archived": False, "default_branch": "main",
                 "head_sha": "a" * 40},
                {"name": "private-secret", "full_name": "owner-1/private-secret",
                 "html_url": "https://github.com/owner-1/private-secret", "private": True,
                 "fork": False, "archived": False, "default_branch": "main"}
            ]
        }

    def save(self):
        self.file.write_text(json.dumps(self.snapshot), encoding="utf-8")
        self.file.chmod(0o600)
        os.utime(self.file, (NOW.timestamp(), NOW.timestamp()))

    def test_missing_is_no_data_and_does_not_create_file(self):
        out = R.read(self.root, now=NOW)
        self.assertEqual(out["cause"], "owner_snapshot_not_supplied")
        self.assertFalse(self.file.exists())

    def test_valid_public_projection_uses_existing_bootstrap(self):
        self.save()
        expected = G.propose(self.snapshot)
        out = R.read(self.root, now=NOW)
        self.assertEqual(out["schema"], G.OUT_SCHEMA)
        self.assertEqual(out["state"], "PROPOSED")
        self.assertEqual(out["public_repositories"], expected["public_repositories"])
        self.assertEqual(out["local_snapshot"]["state"], "OWNER_FILE_PRESENT")
        self.assertIn("github_live_head_not_checked", str(out))
        self.assertFalse(out["changed"])

    def test_private_name_is_not_exposed(self):
        self.save()
        out = R.read(self.root, now=NOW)
        self.assertNotIn("private-secret", json.dumps(out))
        self.assertEqual(out["private_repositories"]["count_only"], 1)
        self.assertIn("NO_DATA", str(out["capabilities"]["live_node"]))

    def test_file_read_does_not_mutate_source(self):
        self.save()
        before = self.file.read_bytes()
        R.read(self.root, now=NOW)
        self.assertEqual(self.file.read_bytes(), before)

    def test_stale_is_not_current_head(self):
        self.save()
        out = R.read(self.root, now=NOW + dt.timedelta(days=2))
        self.assertEqual(out["local_snapshot"]["state"], "STALE")
        self.assertEqual(out["source"], "OWNER_SUPPLIED_UNVERIFIED")

    def test_missing_dir(self):
        self.parent.rmdir()
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_not_supplied")

    def test_world_readable_dir(self):
        self.save()
        self.parent.chmod(0o755)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_directory_not_private")

    def test_world_readable_file(self):
        self.save()
        self.file.chmod(0o644)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_file_not_private")

    def test_symlink_file(self):
        self.save()
        source = self.root / "real.json"
        self.file.rename(source)
        self.file.symlink_to(source)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_file_not_private")

    def test_symlink_directory(self):
        self.save()
        new = self.root / "real"
        self.parent.rename(new)
        self.parent.symlink_to(new, target_is_directory=True)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_directory_not_private")

    def test_invalid_json(self):
        self.file.write_text("garbled", encoding="utf-8")
        self.file.chmod(0o600)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_invalid_or_unreadable")

    def test_duplicate_json_field(self):
        self.file.write_text('{"owner":"a","owner":"b"}', encoding="utf-8")
        self.file.chmod(0o600)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_invalid_or_unreadable")

    def test_invalid_extra_executable_field(self):
        self.snapshot["repositories"][0]["execute"] = "unsafe"
        self.save()
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "repository_shape_invalid")

    def test_invalid_extra_remote_location(self):
        self.snapshot["repositories"][0]["html_url"] = "https://malicious.example/a"
        self.save()
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "repository_url_invalid")

    def test_empty_file_and_oversized(self):
        self.file.write_bytes(b"")
        self.file.chmod(0o600)
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_size_invalid")
        self.file.write_bytes(b"x" * (R.MAX_BYTES + 1))
        self.assertEqual(R.read(self.root, now=NOW)["cause"], "owner_snapshot_size_invalid")


    def _http_get(self, *, host=None):
        loaded = runpy.run_path(str(Path(__file__).resolve().parent / "bin/preceptoros-pwa"),
                                run_name="github_read_http_probe")
        server = ThreadingHTTPServer(("127.0.0.1", 0), loaded["PWA"])
        server.ruta_db = str(self.root / "memory.db")
        server.modelo = "NO_DATA"
        port = server.server_port
        runner = threading.Thread(target=server.serve_forever, daemon=True)
        with mock.patch.object(loaded["_casa"], "raiz", return_value=self.root):
            runner.start()
            try:
                headers = {"Sec-Fetch-Site": "same-origin"}
                if host:
                    headers["Host"] = host
                req = urllib.request.Request(
                    "http://127.0.0.1:%d/api/lab/github" % port, headers=headers)
                try:
                    with urllib.request.urlopen(req, timeout=5) as response:
                        return response.status, json.load(response)
                except urllib.error.HTTPError as error:
                    with closing(error):
                        return error.code, json.load(error)
            finally:
                server.shutdown()
                server.server_close()
                runner.join(timeout=5)

    def test_http_loopback_proposal_is_inert(self):
        self.save()
        status, result = self._http_get()
        self.assertEqual(status, 200)
        self.assertEqual(result["state"], "PROPOSED")
        self.assertEqual(result["private_repositories"]["count_only"], 1)
        self.assertNotIn("private-secret", json.dumps(result))

    def test_http_host_spoof_is_denied(self):
        self.save()
        status, result = self._http_get(host="not-the-local-owner.example")
        self.assertEqual(status, 403)
        self.assertEqual(result["cause"], "local_owner_origin_required")
        self.assertNotIn("owner-1", json.dumps(result))

if __name__ == "__main__":
    unittest.main()
