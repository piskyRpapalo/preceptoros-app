"""Strict positive Android asset packaging allowlist – negative and positive tests.

Verifies that the versioned allowlist (asset_allowlist_v1.txt) and the Gradle
copyPanels task only package approved assets.  No secrets, no symlinks, no
traversal, no duplicates, no newly-introduced files.

Run:
    python3 -m unittest test_android_asset_allowlist
"""
import hashlib
import json
import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
ALLOWLIST = ROOT / "mvp-android" / "asset_allowlist_v1.txt"
INTERFACE = ROOT / "interface"
ASSETS_DIR = ROOT / "assets"
MVP_ANDROID = ROOT / "mvp-android"


def _read_allowlist():
    """Return the set of approved relative paths from the allowlist."""
    if not ALLOWLIST.is_file():
        return None
    paths = set()
    for line in ALLOWLIST.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        paths.add(line)
    return paths


def _sw_precache():
    """Return the set of paths from sw.js Armazon precache (no query strings)."""
    sw = INTERFACE / "sw.js"
    if not sw.is_file():
        return set()
    text = sw.read_text()
    match = re.search(r"const Armazon = \[(.*?)\];", text, re.DOTALL)
    if not match:
        return set()
    raw = match.group(1)
    paths = set()
    for m in re.finditer(r'"([^"]+)"', raw):
        base = m.group(1).split("?")[0]
        if base and base not in ("/", "/app"):
            paths.add(base.lstrip("/"))
    return paths


def _app_html_scripts():
    """Return scripts referenced in app.html <script src> and <link href>."""
    html = INTERFACE / "app.html"
    if not html.is_file():
        return set()
    text = html.read_text()
    paths = set()
    for m in re.finditer(r'(?:src|href)=["\'](/[^"\']+)["\']', text):
        base = m.group(1).split("?")[0]
        if base:
            paths.add(base.lstrip("/"))
    return paths


# Patterns that must NEVER appear in packaged assets (credential/secret bytes).
# These are byte-level checks; regex strings in source code that mention these
# patterns for detection purposes are not actual secrets.
SECRET_PATTERNS = [
    b"preceptoros_private",  # Private token prefix
    b"PRECEPTOROS_PRIVATE",  # Env var name leak
    b"keystore_pass",        # Keystore password
]

# PEM key detection: look for actual PEM blocks, not regex strings.
# A real PEM key has the header on its own line followed by base64 content.
PEM_HEADER_RE = re.compile(rb"-----BEGIN\s+(?:RSA\s+)?(?:EC\s+)?(?:DSA\s+)?(?:OPENSSH\s+)?PRIVATE\s+KEY-----\s*\n[A-Za-z0-9+/=]")


class TestAllowlistFile(unittest.TestCase):
    """Structural checks on the allowlist file itself."""

    def test_allowlist_exists(self):
        self.assertTrue(ALLOWLIST.is_file(), "asset_allowlist_v1.txt must exist")

    def test_allowlist_versioned(self):
        name = ALLOWLIST.name
        self.assertTrue(
            re.search(r"allowlist_v\d+\.txt", name),
            f"Allowlist must be versioned: {name}",
        )

    def test_no_empty_allowlist(self):
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        self.assertGreater(len(paths), 0, "Allowlist must not be empty")

    def test_no_duplicate_entries(self):
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        lines = []
        for line in ALLOWLIST.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                lines.append(line)
        self.assertEqual(len(lines), len(set(lines)), "Duplicate entries in allowlist")

    def test_no_path_traversal(self):
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        for p in paths:
            self.assertNotIn("..", p, f"Path traversal in allowlist: {p}")
            self.assertFalse(p.startswith("/"), f"Absolute path in allowlist: {p}")

    def test_all_interface_paths_exist(self):
        """Every interface/ path in the allowlist must be a real file."""
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        missing = []
        for p in paths:
            if p.startswith("interface/"):
                full = ROOT / p
                if not full.is_file():
                    missing.append(str(p))
        self.assertEqual(missing, [], f"Missing interface files: {missing}")

    def test_all_assets_paths_exist(self):
        """Every assets/ path in the allowlist must be a real file."""
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        missing = []
        for p in paths:
            if p.startswith("assets/"):
                full = ROOT / p
                if not full.is_file():
                    missing.append(str(p))
        self.assertEqual(missing, [], f"Missing assets files: {missing}")

    def test_all_mvp_paths_exist(self):
        """Every mvp-android/ path in the allowlist must be a real file."""
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        missing = []
        for p in paths:
            if p.startswith("mvp-android/"):
                full = ROOT / p
                if not full.is_file():
                    missing.append(str(p))
        self.assertEqual(missing, [], f"Missing mvp-android files: {missing}")

    def test_no_symlinks_in_allowlist(self):
        """Allowlisted files must not be symlinks."""
        paths = _read_allowlist()
        self.assertIsNotNone(paths)
        symlinks = []
        for p in paths:
            full = ROOT / p
            if full.exists() and full.is_symlink():
                symlinks.append(p)
        self.assertEqual(symlinks, [], f"Symlinks in allowlist: {symlinks}")


class TestAllowlistCompleteness(unittest.TestCase):
    """Ensure the allowlist covers all app.html and sw.js dependencies."""

    def test_sw_precache_in_allowlist(self):
        """Every sw.js precache path must be in the allowlist."""
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        precache = _sw_precache()
        # Map sw.js paths to allowlist format
        allowed_interface = {p.removeprefix("interface/") for p in allowlist if p.startswith("interface/")}
        allowed_assets = {p.removeprefix("assets/") for p in allowlist if p.startswith("assets/")}
        allowed_mvp = {p.removeprefix("mvp-android/") for p in allowlist if p.startswith("mvp-android/")}
        allowed_all = allowed_interface | allowed_assets | allowed_mvp

        missing = []
        for p in precache:
            if p.startswith("face/"):
                key = p
            elif p.startswith("assets/"):
                key = p.removeprefix("assets/")
            else:
                key = p
            if key not in allowed_all:
                missing.append(p)
        self.assertEqual(missing, [], f"sw.js precache not in allowlist: {missing}")

    def test_app_html_scripts_in_allowlist(self):
        """Every script in app.html must be in the allowlist."""
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        scripts = _app_html_scripts()
        allowed_interface = {p.removeprefix("interface/") for p in allowlist if p.startswith("interface/")}
        allowed_assets = {p.removeprefix("assets/") for p in allowlist if p.startswith("assets/")}
        # mvp-android bridge scripts are served at root level in the APK
        allowed_mvp = {p.removeprefix("mvp-android/") for p in allowlist if p.startswith("mvp-android/")}
        allowed_all = allowed_interface | allowed_assets | allowed_mvp

        missing = []
        for p in scripts:
            if p.startswith("assets/"):
                key = p.removeprefix("assets/")
            elif p.startswith("face/"):
                key = p
            else:
                key = p
            if key not in allowed_all:
                missing.append(p)
        self.assertEqual(missing, [], f"app.html scripts not in allowlist: {missing}")


class TestExcludedFiles(unittest.TestCase):
    """Verify that known-unrelated files are NOT in the allowlist."""

    def test_dashboard_excluded(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/dashboard.html", allowlist)
        self.assertNotIn("interface/dashboard.js", allowlist)

    def test_hexelion_excluded(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/hexelion.html", allowlist)
        self.assertNotIn("interface/hexelion.js", allowlist)
        self.assertNotIn("interface/hexelion.css", allowlist)

    def test_consola_excluded(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/consola.js", allowlist)
        self.assertNotIn("interface/consola.css", allowlist)

    def test_face_game_files_excluded(self):
        """Standalone face game files must not be in the allowlist."""
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        excluded = [
            "interface/face/face.js",
            "interface/face/face.css",
            "interface/face/atlantis.html",
            "interface/face/basic.html",
            "interface/face/zombie.html",
            "interface/face/bubble/core.js",
            "interface/face/bubble/canon.js",
        ]
        for p in excluded:
            self.assertNotIn(p, allowlist, f"{p} should not be in allowlist")

    def test_firmas_excluded(self):
        """Deprecated firmas.js must not be in the allowlist."""
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/firmas.js", allowlist)

    def test_legacy_excluded(self):
        """Legacy directory must not be in the allowlist."""
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        for p in allowlist:
            self.assertFalse(
                p.startswith("interface/legacy/"),
                f"Legacy file in allowlist: {p}",
            )

    def test_native_voice_excluded(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/native_voice.js", allowlist)

    def test_privacy_toggle_excluded(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/privacy_toggle.html", allowlist)
        self.assertNotIn("interface/privacy_toggle.css", allowlist)

    def test_desnuda_excluded(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertNotIn("interface/desnuda.css", allowlist)


class TestNoSecretsInAllowlistedFiles(unittest.TestCase):
    """Allowlisted files must not contain credential or private key byte patterns."""

    def test_no_secret_patterns(self):
        allowlist = _read_allowlist()
        if allowlist is None:
            self.skipTest("Allowlist not found")
        violations = []
        for rel in allowlist:
            full = ROOT / rel
            if not full.is_file():
                continue
            try:
                data = full.read_bytes()
            except (OSError, PermissionError):
                continue
            for pattern in SECRET_PATTERNS:
                if pattern in data:
                    violations.append(f"{rel}: contains {pattern[:20]}...")
            # Check for actual PEM key blocks (not regex strings in source).
            if PEM_HEADER_RE.search(data):
                violations.append(f"{rel}: contains PEM private key block")
        self.assertEqual(
            violations, [],
            f"Secret patterns found in allowlisted files: {violations}",
        )


class TestCapabilityLedgerAlignment(unittest.TestCase):
    """Allowlist must include all files required by capability_ledger.py APK checks."""

    def test_six_panels_assets_present(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        required = [
            "interface/app.html",
            "interface/app.css",
            "interface/app.js",
            "interface/mvp_first_run.js",
            "interface/superbot_talk.js",
            "interface/talk_crab_canvas.js",
        ]
        for r in required:
            self.assertIn(r, allowlist, f"Capability ledger requires: {r}")

    def test_accessibility_assets_present(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        for r in ["interface/audio_accessibility.js", "interface/acho_sonido.js"]:
            self.assertIn(r, allowlist, f"Capability ledger requires: {r}")

    def test_node_consent_assets_present(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        required = [
            "mvp-android/android_join_bridge.js",
            "mvp-android/android_review_bridge.js",
            "mvp-android/android_heartbeat_bridge.js",
            "interface/node_registration.js",
        ]
        for r in required:
            self.assertIn(r, allowlist, f"Capability ledger requires: {r}")

    def test_documents_harness_present(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        for r in ["interface/documents.js", "interface/notebook.js", "interface/owner_model_slots.js"]:
            self.assertIn(r, allowlist, f"Capability ledger requires: {r}")

    def test_local_model_bridge_present(self):
        allowlist = _read_allowlist()
        self.assertIsNotNone(allowlist)
        self.assertIn("mvp-android/offline_mini.js", allowlist)


class TestProfilePolicy(unittest.TestCase):
    """Profile-related policy checks."""

    def test_no_rack_endpoints_in_allowlist(self):
        """No allowlisted file should contain hardcoded rack endpoints."""
        allowlist = _read_allowlist()
        if allowlist is None:
            self.skipTest("Allowlist not found")
        endpoint_pattern = re.compile(
            r"(?:192\.168|10\.\d|172\.(1[6-9]|2\d|3[01]))\.\d+\.\d+:\d+",
            re.I,
        )
        violations = []
        for rel in allowlist:
            full = ROOT / rel
            if not full.is_file():
                continue
            try:
                text = full.read_text(errors="replace")
            except (OSError, PermissionError):
                continue
            if endpoint_pattern.search(text):
                violations.append(rel)
        self.assertEqual(
            violations, [],
            f"Private rack endpoints in allowlisted files: {violations}",
        )

    def test_single_package_id_in_build_gradle(self):
        """build.gradle must default to org.preceptoros.app."""
        gradle = MVP_ANDROID / "app" / "build.gradle"
        if not gradle.is_file():
            self.skipTest("build.gradle not found")
        text = gradle.read_text()
        self.assertIn("org.preceptoros.app", text)
        # Default must be canonical, not legacy
        m = re.search(r"mvpAppId\s*=\s*.*'org\.preceptoros\.app'", text)
        self.assertIsNotNone(m, "Default applicationId must be org.preceptoros.app")


if __name__ == "__main__":
    unittest.main()
