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


if __name__ == "__main__":
    unittest.main()
