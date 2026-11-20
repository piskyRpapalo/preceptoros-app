"""PUBLIC profile byte-level verification — no private API routes in staged assets.

Verifies that the PUBLIC profile allowlist and Gradle staging exclude all files
containing private internal command route strings. This is the negative proof
required by the P0 PUBLIC/BYO rule.

Forbidden patterns (must NOT appear in any PUBLIC-staged asset):
  /api/hexelion/chat, /api/hexelion/decision, /api/hexelion/search
  /api/hitl
  /api/nodo/identity, /api/nodo/edificio, /api/nodo/export

Run:
    python3 -m unittest test_android_public_profile
"""
import hashlib
import json
import os
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MVP_ANDROID = ROOT / "mvp-android"
APP_BUILD_GRADLE = MVP_ANDROID / "app" / "build.gradle"
ALLOWLIST_OWNER = MVP_ANDROID / "asset_allowlist_v1.txt"
ALLOWLIST_PUBLIC = MVP_ANDROID / "asset_allowlist_public.txt"
GRADLEW = MVP_ANDROID / "gradlew"

# Byte-level forbidden patterns — private internal command routes.
FORBIDDEN_ROUTES = [
    b'/api/hexelion/chat',
    b'/api/hexelion/decision',
    b'/api/hexelion/search',
    b'/api/hitl',
    b'/api/nodo/identity',
    b'/api/nodo/edificio',
    b'/api/nodo/export',
]

# Forbidden credential and private-infrastructure byte patterns.
# These are the synthetic shapes the PUBLIC verifier must reject.
FORBIDDEN_CREDENTIAL_PATTERNS = [
    # GitHub PAT shape: ghp_ + 32 alphanumeric chars (synthetic, not real)
    b'ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA',
    # Private rack hostname
    b'onexstation',
    # PEM private key header
    b'-----BEGIN RSA PRIVATE KEY-----',
]

# Files known to contain forbidden routes (must be excluded from PUBLIC).
KNOWN_FORBIDDEN_FILES = {
    'interface/app.js',
    'interface/hitl.js',
    'interface/hitl.css',
    'interface/node_building.js',
}


def _read_allowlist(path):
    """Return the set of approved relative paths from the allowlist."""
    if not path.is_file():
        return None
    paths = set()
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        paths.add(line)
    return paths


def _gradle_available():
    """Check if Gradle wrapper is executable."""
    return GRADLEW.exists() and os.access(GRADLEW, os.X_OK)


def _run_gradle(args, timeout=120):
    """Run a Gradle command and return (returncode, stdout, stderr)."""
    cmd = [str(GRADLEW), "--offline", "--console=plain"] + list(args)
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=str(MVP_ANDROID),
    )
    return result.returncode, result.stdout, result.stderr


class TestPublicAllowlistExcludesForbidden(unittest.TestCase):
    """PUBLIC allowlist must NOT include files with private API routes."""

    def test_public_allowlist_exists(self):
        self.assertTrue(
            ALLOWLIST_PUBLIC.is_file(),
            "asset_allowlist_public.txt must exist for PUBLIC profile",
        )

    def test_forbidden_files_not_in_public_allowlist(self):
        """Files known to contain private routes must be excluded from PUBLIC."""
        public = _read_allowlist(ALLOWLIST_PUBLIC)
        self.assertIsNotNone(public)
        for f in KNOWN_FORBIDDEN_FILES:
            self.assertNotIn(
                f, public,
                f"{f} contains private API routes and must not be in PUBLIC allowlist",
            )

    def test_forbidden_routes_not_in_public_allowlisted_files(self):
        """No file in the PUBLIC allowlist may contain forbidden route strings."""
        public = _read_allowlist(ALLOWLIST_PUBLIC)
        if public is None:
            self.skipTest("PUBLIC allowlist not found")
        violations = []
        for rel in public:
            full = ROOT / rel
            if not full.is_file():
                continue
            try:
                data = full.read_bytes()
            except (OSError, PermissionError):
                continue
            for pattern in FORBIDDEN_ROUTES:
                if pattern in data:
                    violations.append(f"{rel}: contains {pattern.decode()}")
        self.assertEqual(
            violations, [],
            f"PUBLIC allowlist files contain forbidden private API routes: {violations}",
        )

    def test_owner_allowlist_includes_forbidden(self):
        """OWNER allowlist may include files with private routes (they are owner-only)."""
        owner = _read_allowlist(ALLOWLIST_OWNER)
        if owner is None:
            self.skipTest("OWNER allowlist not found")
        # At least app.js should be in OWNER (it's the main app script).
        self.assertIn(
            "interface/app.js", owner,
            "OWNER allowlist should include interface/app.js",
        )


class TestPublicAllowlistCompleteness(unittest.TestCase):
    """PUBLIC allowlist must include essential six-panel assets."""

    def test_six_panel_core_present(self):
        """PUBLIC allowlist must include core six-panel assets."""
        public = _read_allowlist(ALLOWLIST_PUBLIC)
        self.assertIsNotNone(public)
        required = [
            "interface/app.css",
            "interface/superbot_talk.js",
            "interface/talk_crab_canvas.js",
            "interface/documents.js",
            "interface/mvp_first_run.js",
            "interface/mini_project_guide.js",
            "interface/mini_recovery.js",
            "interface/node_registration.js",
            "interface/companion_onboarding.js",
            "interface/owner_model_slots.js",
        ]
        for r in required:
            self.assertIn(r, public, f"PUBLIC allowlist missing essential asset: {r}")

    def test_pwa_icons_present(self):
        public = _read_allowlist(ALLOWLIST_PUBLIC)
        self.assertIsNotNone(public)
        for icon in ["assets/icono-192.png", "assets/icono-512.png", "assets/icono-512-maskable.png"]:
            self.assertIn(icon, public, f"PUBLIC allowlist missing icon: {icon}")

    def test_android_bridges_present(self):
        public = _read_allowlist(ALLOWLIST_PUBLIC)
        self.assertIsNotNone(public)
        for bridge in [
            "mvp-android/android_review_bridge.js",
            "mvp-android/offline_mini.js",
            "mvp-android/android_join_bridge.js",
            "mvp-android/android_heartbeat_bridge.js",
        ]:
            self.assertIn(bridge, public, f"PUBLIC allowlist missing bridge: {bridge}")

    def test_licenses_present(self):
        public = _read_allowlist(ALLOWLIST_PUBLIC)
        self.assertIsNotNone(public)
        for lic in [
            "mvp-android/legal/ATTRIBUTIONS.txt",
            "mvp-android/legal/Apache-2.0.txt",
            "mvp-android/legal/llama.cpp-MIT.txt",
        ]:
            self.assertIn(lic, public, f"PUBLIC allowlist missing license: {lic}")


class TestBuildGradlePublicProfile(unittest.TestCase):
    """build.gradle must implement PUBLIC profile asset filtering."""

    def test_public_allowlist_referenced(self):
        """build.gradle must reference asset_allowlist_public.txt."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        self.assertIn(
            "asset_allowlist_public.txt",
            text,
            "build.gradle must reference asset_allowlist_public.txt for PUBLIC profile",
        )

    def test_forbidden_routes_defined(self):
        """build.gradle must define forbidden route patterns for PUBLIC verification."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        self.assertIn(
            "PUBLIC_FORBIDDEN_ROUTES",
            text,
            "build.gradle must define PUBLIC_FORBIDDEN_ROUTES",
        )

    def test_verify_public_assets_task(self):
        """build.gradle must register verifyPublicAssets task."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        self.assertIn(
            "verifyPublicAssets",
            text,
            "build.gradle must register verifyPublicAssets task",
        )

    def test_generate_public_projection_task(self):
        """build.gradle must register generatePublicProjection task."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        self.assertIn(
            "generatePublicProjection",
            text,
            "build.gradle must register generatePublicProjection task",
        )

    def test_public_profile_default(self):
        """Default profile must be PUBLIC (not OWNER)."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        # Check that default falls back to PUBLIC
        self.assertIn("'PUBLIC'", text, "Default profile must be PUBLIC")


class TestPublicGradleCopy(unittest.TestCase):
    """Gradle copyPanels with PUBLIC profile must produce clean assets."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_public_copy_panels_no_forbidden_routes(self):
        """After copyPanels with PUBLIC profile, no staged asset contains forbidden routes."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"

        # Clean first
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        # Run copyPanels with PUBLIC profile (default)
        rc, stdout, stderr = _run_gradle(["copyPanels"])
        combined = stdout + "\n" + stderr

        if rc != 0:
            # Clean up
            if assets_dir.exists():
                import shutil
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            self.fail(f"copyPanels PUBLIC failed (rc={rc}): {combined[-2000:]}")

        # Byte-level scan of staged assets
        violations = []
        if assets_dir.exists():
            for f in assets_dir.rglob("*"):
                if not f.is_file():
                    continue
                if f.suffix in {'.gguf', '.png', '.svg', '.jar'}:
                    continue
                try:
                    data = f.read_bytes()
                    for pattern in FORBIDDEN_ROUTES:
                        if pattern in data:
                            violations.append(f"{f.name}: contains {pattern.decode()}")
                except (OSError, PermissionError):
                    continue

        # Cleanup
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        self.assertEqual(
            violations, [],
            f"PUBLIC staged assets contain forbidden private API routes: {violations}",
        )

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_owner_copy_panels_includes_app_js(self):
        """After copyPanels with OWNER profile, app.js IS present (expected)."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"

        # Clean first
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        # Run copyPanels with OWNER profile
        rc, stdout, stderr = _run_gradle(["-PappProfile=OWNER", "copyPanels"])
        combined = stdout + "\n" + stderr

        if rc != 0:
            # Clean up
            if assets_dir.exists():
                import shutil
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            self.fail(f"copyPanels OWNER failed (rc={rc}): {combined[-2000:]}")

        # app.js should be present in OWNER
        app_js = assets_dir / "app.js"
        if not app_js.exists():
            # Cleanup
            if assets_dir.exists():
                import shutil
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            self.fail("OWNER profile should include app.js")

        # Cleanup
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)


class TestPublicAppHtmlStructure(unittest.TestCase):
    """PUBLIC staged app.html must have six tab ids, public-boot.js, and zero private routes."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_public_app_html_six_tabs_and_boot(self):
        """After copyPanels with PUBLIC profile, app.html has six tab ids + public-boot.js and no private routes."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"

        # Clean first
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        # Run copyPanels with PUBLIC profile (default)
        rc, stdout, stderr = _run_gradle(["copyPanels"])
        combined = stdout + "\n" + stderr

        if rc != 0:
            # Clean up
            if assets_dir.exists():
                import shutil
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            self.fail(f"copyPanels PUBLIC failed (rc={rc}): {combined[-2000:]}")

        # Read the staged app.html
        app_html = assets_dir / "app.html"
        if not app_html.exists():
            # Cleanup
            if assets_dir.exists():
                import shutil
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
            self.fail("PUBLIC staging must contain app.html")

        html_text = app_html.read_text()

        # Assert six tab ids present
        expected_tabs = [
            "tab-conversacion",
            "tab-cuaderno",
            "tab-lab",
            "tab-ajustes",
            "tab-modelos",
            "tab-settings",
        ]
        for tab_id in expected_tabs:
            self.assertIn(
                f'id="{tab_id}"',
                html_text,
                f"PUBLIC app.html must contain tab id: {tab_id}",
            )

        # Assert public-boot.js is referenced
        self.assertIn(
            "public-boot.js",
            html_text,
            "PUBLIC app.html must reference public-boot.js",
        )

        # Assert zero private command routes
        for route in FORBIDDEN_ROUTES:
            self.assertNotIn(
                route,
                app_html.read_bytes(),
                f"PUBLIC app.html must NOT contain private route: {route.decode()}",
            )

        # Cleanup
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)


class TestPublicProjectionInjection(unittest.TestCase):
    """If unsafe assets are injected into PUBLIC staging, verification must catch them."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_injected_unsafe_asset_caught(self):
        """A file with forbidden routes placed in assets/ must be caught by verifyPublicAssets."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Inject a fake file with forbidden routes
        injected = assets_dir / "injected_unsafe.js"
        injected.write_text('fetch("/api/hexelion/chat", {method:"POST"});')

        try:
            # Run verifyPublicAssets — should fail
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            if rc == 0:
                self.fail(
                    "verifyPublicAssets should have rejected injected unsafe asset"
                )

            # Check error message mentions the violation
            self.assertIn(
                "PUBLIC profile asset violation",
                combined,
                f"Expected violation message, got: {combined[-500:]}",
            )
        finally:
            # Cleanup
            if injected.exists():
                injected.unlink()
            if assets_dir.exists():
                import shutil
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)


class TestPublicSecurityGateNegativeFixtures(unittest.TestCase):
    """Negative fixtures: inject synthetic secrets into PUBLIC staging and verify rejection.

    Each test injects a synthetic credential shape into a temporary staged asset,
    runs verifyPublicAssets, and asserts nonzero exit with a cause-class message.
    No real secrets are involved; cleanup is guaranteed via try/finally.
    """

    @staticmethod
    def _clean_assets():
        """Remove only generated contents of the assets directory."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_github_pat_rejected(self):
        """A synthetic GitHub PAT (ghp_ + 32 A chars) in a staged .js must be rejected."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_pat.js"
        # Synthetic token — NOT a real credential
        injected.write_text('// synthetic test token\nvar t = "ghp_AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA";\n')

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject synthetic GitHub PAT shape",
            )
            self.assertIn(
                "FORBIDDEN_PATTERN",
                combined,
                f"Expected FORBIDDEN_PATTERN cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_private_hostname_rejected(self):
        """A private rack hostname (onexstation) in a staged .js must be rejected."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_host.js"
        injected.write_text('// synthetic test host\nvar h = "onexstation.local";\n')

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject private rack hostname",
            )
            self.assertIn(
                "FORBIDDEN_PATTERN",
                combined,
                f"Expected FORBIDDEN_PATTERN cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_pem_private_key_rejected(self):
        """A synthetic PEM private key header in a staged .js must be rejected."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_pem.js"
        injected.write_text(
            '// synthetic test PEM\n'
            'var k = "-----BEGIN RSA PRIVATE KEY-----\\nMIIBogIBAAJBALt...\n-----END RSA PRIVATE KEY-----";\n'
        )

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject synthetic PEM private key",
            )
            self.assertIn(
                "FORBIDDEN_PATTERN",
                combined,
                f"Expected FORBIDDEN_PATTERN cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_private_route_in_allowlisted_asset_rejected(self):
        """A synthetic private API route injected into an allowlisted asset must be rejected."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        # Stage a clean PUBLIC build first, then overwrite one allowlisted file
        rc, stdout, stderr = _run_gradle(["copyPanels"])
        if rc != 0:
            self._clean_assets()
            self.skipTest(f"copyPanels not available for this test: {stderr[-300:]}")

        # Overwrite an allowlisted bridge with a tainted version
        injected = assets_dir / "android_review_bridge.js"
        injected.write_text(
            '// synthetic tainted bridge\n'
            'function bridge() { fetch("/api/hexelion/chat", {}); }\n'
        )

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject private route in allowlisted asset",
            )
            self.assertIn(
                "FORBIDDEN_ROUTE",
                combined,
                f"Expected FORBIDDEN_ROUTE cause class, got: {combined[-500:]}",
            )
        finally:
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_tailscale_magicdns_rejected(self):
        """A Tailscale MagicDNS hostname (.ts.net) in a staged .js must be rejected."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_tailscale.js"
        injected.write_text('// synthetic Tailscale host\nvar h = "soberano.tailb9e0f7.ts.net";\n')

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject Tailscale MagicDNS hostname",
            )
            self.assertIn(
                "FORBIDDEN_PATTERN",
                combined,
                f"Expected FORBIDDEN_PATTERN cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_rfc1918_ip_rejected(self):
        """An RFC1918 private IPv4 address with port in a staged .js must be rejected."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_rfc1918.js"
        injected.write_text('// synthetic private endpoint\nvar e = "192.168.10.25:21434";\n')

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject RFC1918 private IPv4 address",
            )
            self.assertIn(
                "FORBIDDEN_PATTERN",
                combined,
                f"Expected FORBIDDEN_PATTERN cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_synthetic_pem_in_png_rejected(self):
        """A PEM private key marker embedded in a PNG binary must be rejected (byte-stream scan)."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_pem_probe.png"
        # Minimal valid-ish PNG header (8 bytes) + PEM marker embedded in binary data
        png_header = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        pem_marker = b'-----BEGIN PRIVATE KEY-----'
        # Pad with random-looking bytes to simulate binary content
        padding = bytes(range(256)) * 4
        injected.write_bytes(png_header + padding + pem_marker + padding)

        try:
            rc, stdout, stderr = _run_gradle(["verifyPublicAssets"])
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject PEM marker embedded in PNG binary",
            )
            self.assertIn(
                "FORBIDDEN_PATTERN",
                combined,
                f"Expected FORBIDDEN_PATTERN cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_clean_public_staging_passes(self):
        """A clean PUBLIC staging (no injected secrets) must pass verifyPublicAssets."""
        self._clean_assets()
        try:
            rc, stdout, stderr = _run_gradle(["copyPanels"])
            combined = stdout + "\n" + stderr

            if rc != 0:
                self.skipTest(f"copyPanels PUBLIC not available: {combined[-300:]}")

            # Now verify should pass on clean staging
            rc2, stdout2, stderr2 = _run_gradle(["verifyPublicAssets"])
            combined2 = stdout2 + "\n" + stderr2

            self.assertEqual(
                rc2, 0,
                f"verifyPublicAssets should pass on clean PUBLIC staging: {combined2[-500:]}",
            )
        finally:
            self._clean_assets()


class TestLargeBinaryStreamingScan(unittest.TestCase):
    """Large synthetic binary probes to verify the forward-only streaming scanner.

    These tests create 220000-byte PNG-like binaries with markers at specific
    byte offsets that cross 64KiB block boundaries, proving the scanner:
    - Terminates correctly on large files (no infinite loop)
    - Detects markers at byte 65529 (crosses the 65536 boundary)
    - Detects markers at byte 155000 (well past first blocks)
    - Passes clean 220000-byte binaries without false positives
    Each subprocess.run uses timeout=20 to catch hangs.
    """

    @staticmethod
    def _clean_assets():
        """Remove only generated contents of the assets directory."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        if assets_dir.exists():
            import shutil
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

    def _make_synthetic_png(self, size, marker, offset):
        """Build a synthetic binary file of exactly `size` bytes with `marker` at `offset`.

        Uses PNG header bytes and random-looking padding to simulate a real binary.
        """
        data = bytearray(size)
        # Write PNG magic header
        png_header = bytes([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A])
        data[:len(png_header)] = png_header
        # Fill with repeating byte pattern (simulates binary content)
        for i in range(len(png_header), size):
            data[i] = (i * 7 + 13) % 256
        # Embed the marker at the specified offset
        marker_bytes = marker if isinstance(marker, bytes) else marker.encode('ascii')
        data[offset:offset + len(marker_bytes)] = marker_bytes
        return bytes(data)

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_binary_marker_at_65529_crosses_64k_boundary(self):
        """A 220000-byte binary with '/api/hitl' at byte 65529 must be rejected.

        Offset 65529 is 7 bytes before the 65536 boundary, so the marker string
        '/api/hitl' (9 bytes) spans bytes 65529..65537 — crossing the block boundary.
        This proves the tail overlap mechanism catches cross-boundary markers.
        """
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_large_boundary.png"
        # 220000 bytes, marker '/api/hitl' at offset 65529
        data = self._make_synthetic_png(220000, b'/api/hitl', 65529)
        injected.write_bytes(data)

        try:
            rc, stdout, stderr = _run_gradle(
                ["verifyPublicAssets"], timeout=20
            )
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject marker at byte 65529 (crosses 64KiB boundary)",
            )
            self.assertIn(
                "FORBIDDEN_ROUTE",
                combined,
                f"Expected FORBIDDEN_ROUTE cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_binary_marker_at_155000_past_first_blocks(self):
        """A 220000-byte binary with '/api/hitl' at byte 155000 must be rejected.

        Offset 155000 is well past the first 64KiB block (block 2, offset ~23928
        within the second 64KiB chunk). This proves the scanner processes all
        blocks and does not terminate early or skip binary regions.
        """
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_large_deep.png"
        # 220000 bytes, marker '/api/hitl' at offset 155000
        data = self._make_synthetic_png(220000, b'/api/hitl', 155000)
        injected.write_bytes(data)

        try:
            rc, stdout, stderr = _run_gradle(
                ["verifyPublicAssets"], timeout=20
            )
            combined = stdout + "\n" + stderr

            self.assertNotEqual(
                rc, 0,
                "verifyPublicAssets must reject marker at byte 155000 (past first blocks)",
            )
            self.assertIn(
                "FORBIDDEN_ROUTE",
                combined,
                f"Expected FORBIDDEN_ROUTE cause class, got: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_clean_220000_binary_passes(self):
        """A clean 220000-byte binary with no markers must pass verifyPublicAssets.

        This proves the streaming scanner terminates correctly at EOF on large
        files and does not produce false positives on binary data.
        """
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)
        injected = assets_dir / "synthetic_clean_large.png"
        # 220000 bytes of clean binary data (no forbidden markers)
        data = self._make_synthetic_png(220000, b'', 0)
        injected.write_bytes(data)

        try:
            rc, stdout, stderr = _run_gradle(
                ["verifyPublicAssets"], timeout=20
            )
            combined = stdout + "\n" + stderr

            self.assertEqual(
                rc, 0,
                f"verifyPublicAssets should pass on clean 220000-byte binary: {combined[-500:]}",
            )
        finally:
            if injected.exists():
                injected.unlink()
            self._clean_assets()


if __name__ == "__main__":
    unittest.main()
