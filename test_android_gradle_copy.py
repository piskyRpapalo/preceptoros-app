"""Negative and positive Gradle copyPanels integration tests.

Verifies that the Gradle asset staging pipeline:
1. Removes stale synthetic files before copying (P0 bypass fix).
2. Copies only allowlisted licenses, not the entire legal/ folder.
3. Rejects symlinked or escaped assets directory.
4. Produces output that matches the allowlist (parity check).
5. BuildConfig field for distribution profile is present.

Run:
    python3 -m unittest test_android_gradle_copy
"""
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MVP_ANDROID = ROOT / "mvp-android"
APP_BUILD_GRADLE = MVP_ANDROID / "app" / "build.gradle"
ALLOWLIST = MVP_ANDROID / "asset_allowlist_v1.txt"
GRADLEW = MVP_ANDROID / "gradlew"


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


class TestPrepareAssetsRemovesStale(unittest.TestCase):
    """Stale synthetic files in generated output MUST be removed before copy."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_stale_synthetic_file_removed(self):
        """A synthetic file placed in src/main/assets must NOT survive copyPanels."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        marker = assets_dir / "UNAPPROVED_P0_MARKER.txt"

        # Ensure assets dir exists
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Place a synthetic stale file
        marker.write_text("STALE_MARKER_SHOULD_BE_REMOVED")
        self.assertTrue(marker.exists(), "Marker should exist before copyPanels")

        # Run copyPanels
        rc, stdout, stderr = _run_gradle(["copyPanels"])
        combined = stdout + "\n" + stderr

        if rc != 0:
            self.fail(f"copyPanels failed (rc={rc}): {combined[-2000:]}")

        # The stale marker MUST be gone
        if marker.exists():
            marker_content = marker.read_text()
            marker.delete()  # cleanup
            self.fail(
                f"P0 BYPASS: Stale synthetic file survived copyPanels! "
                f"Path: {marker} Content: {marker_content[:200]}"
            )

        # Cleanup: remove any copied assets to leave dir clean
        if assets_dir.exists():
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)


class TestLicensesAllowlist(unittest.TestCase):
    """Only allowlisted license files may be copied, never the whole folder."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_unlisted_license_not_copied(self):
        """A file placed in legal/ but NOT in allowlist must NOT be copied."""
        legal_dir = MVP_ANDROID / "legal"
        legal_dir.mkdir(parents=True, exist_ok=True)

        # Create a decoy license file NOT in the allowlist
        decoy = legal_dir / "UNLISTED_FAKE_LICENSE.txt"
        decoy.write_text("This should never appear in assets/licenses/")

        # Clean assets first
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Run copyPanels
        rc, stdout, stderr = _run_gradle(["copyPanels"])
        combined = stdout + "\n" + stderr

        if rc != 0:
            # Clean up decoy on failure
            decoy.unlink(missing_ok=True)
            self.fail(f"copyPanels failed (rc={rc}): {combined[-2000:]}")

        # Check that decoy was NOT copied
        copied_decoy = assets_dir / "licenses" / "UNLISTED_FAKE_LICENSE.txt"
        if copied_decoy.exists():
            copied_decoy.unlink(missing_ok=True)
            decoy.unlink(missing_ok=True)
            self.fail("Unlisted license file was copied into assets/licenses/")

        # Verify the three allowlisted licenses ARE present
        allowlist = _read_allowlist()
        legal_files = [p for p in allowlist if p.startswith("mvp-android/legal/")]
        for lf in legal_files:
            basename = lf.split("/")[-1]
            expected = assets_dir / "licenses" / basename
            if not expected.exists():
                decoy.unlink(missing_ok=True)
                self.fail(f"Allowlisted license missing from output: {basename}")

        # Cleanup
        decoy.unlink(missing_ok=True)
        if assets_dir.exists():
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)


class TestSymlinkRejection(unittest.TestCase):
    """Gradle must reject a symlinked assets directory."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_symlinked_assets_dir_rejected(self):
        """If src/main/assets is a symlink, prepareAssets must fail."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        real_dir = MVP_ANDROID / "app" / "src" / "main" / "assets_real_backup"

        # Move real assets dir aside
        if assets_dir.exists():
            # Backup contents
            if real_dir.exists():
                shutil.rmtree(real_dir)
            shutil.move(str(assets_dir), str(real_dir))

        # Create a symlink pointing to the backup
        try:
            target = tempfile.mkdtemp(prefix="fake_assets_")
            fake_dir = Path(target)
            assets_dir.symlink_to(fake_dir)

            # Run copyPanels — should fail
            rc, stdout, stderr = _run_gradle(["copyPanels"])
            combined = stdout + "\n" + stderr

            if rc == 0:
                self.fail("copyPanels should have rejected symlinked assets dir")

            # Check error message mentions symlink
            if "symlink" not in combined.lower():
                self.fail(
                    f"Expected symlink rejection message, got: {combined[-500:]}"
                )
        finally:
            # Restore original assets dir
            if assets_dir.exists() or assets_dir.is_symlink():
                assets_dir.unlink()
            if real_dir.exists():
                shutil.move(str(real_dir), str(assets_dir))


class TestOutputParity(unittest.TestCase):
    """Output assets must match allowlist — no extra, no missing files."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_owner_output_matches_allowlist(self):
        """After copyPanels with OWNER profile, output must contain exactly the allowlisted files."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        allowlist = _read_allowlist()
        if allowlist is None:
            self.skipTest("Allowlist not found")

        # Clean first
        if assets_dir.exists():
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)

        # Run copyPanels with OWNER profile (full allowlist)
        rc, stdout, stderr = _run_gradle(["-PappProfile=OWNER", "copyPanels"])
        combined = stdout + "\n" + stderr

        if rc != 0:
            self.fail(f"copyPanels OWNER failed (rc={rc}): {combined[-2000:]}")

        # Collect all output files
        output_files = set()
        if assets_dir.exists():
            for f in assets_dir.rglob("*"):
                if f.is_file():
                    rel = f.relative_to(assets_dir)
                    output_files.add(str(rel))

        # Build expected set from allowlist
        expected = set()
        for p in allowlist:
            if p.startswith("interface/"):
                expected.add(p.removeprefix("interface/"))
            elif p.startswith("assets/"):
                # WebViewAssetLoader.AssetsPathHandler maps /assets/X -> src/main/assets/assets/X
                # so the assets/ prefix is preserved in staging (copyPanelsAssets -> into assets/)
                expected.add(p)
            elif p.startswith("mvp-android/") and not p.startswith("mvp-android/legal/"):
                # Bridge files go directly into assets/
                expected.add(p.split("/")[-1])
            elif p.startswith("mvp-android/legal/"):
                # Licenses go into assets/licenses/
                expected.add("licenses/" + p.split("/")[-1])

        # Check for extra files (not in allowlist)
        extra = output_files - expected
        if extra:
            self.fail(f"Extra files in output not in allowlist: {sorted(extra)}")

        # Check for missing files
        missing = expected - output_files
        if missing:
            self.fail(f"Missing files in output: {sorted(missing)}")

        # Assert all 4 owner asset URL paths exist in staging
        owner_asset_urls = [
            "assets/icono-192.png",
            "assets/icono-512.png",
            "assets/icono-512-maskable.png",
            "assets/compass.svg",
        ]
        for url_path in owner_asset_urls:
            self.assertIn(
                url_path,
                output_files,
                f"OWNER staging must contain asset URL path: {url_path}",
            )

        # Cleanup
        if assets_dir.exists():
            for item in assets_dir.iterdir():
                if item.is_file():
                    item.unlink()
                elif item.is_dir():
                    shutil.rmtree(item, ignore_errors=True)


class TestBuildConfigProfile(unittest.TestCase):
    """BuildConfig must contain APP_DISTRIBUTION_PROFILE field."""

    def test_buildconfig_profile_field_present(self):
        """build.gradle must define APP_DISTRIBUTION_PROFILE buildConfigField."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        self.assertIn(
            "APP_DISTRIBUTION_PROFILE",
            text,
            "build.gradle must define BuildConfig.APP_DISTRIBUTION_PROFILE",
        )
        # Must use buildConfigField
        m = re.search(
            r"buildConfigField\s+['\"]String['\"]\s*,\s*['\"]APP_DISTRIBUTION_PROFILE['\"]",
            text,
        )
        self.assertIsNotNone(
            m, "APP_DISTRIBUTION_PROFILE must be a String buildConfigField"
        )

    def test_profile_default_is_public(self):
        """Default profile value must be PUBLIC."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        # Check that default falls back to PUBLIC
        m = re.search(r"appProfile\ ?: \? \: ['\"]PUBLIC['\"]", text)
        if not m:
            # Alternative pattern check
            self.assertIn("'PUBLIC'", text, "Default profile must be PUBLIC")

    def test_unknown_profile_rejected(self):
        """An unknown profile value must cause Gradle configuration failure."""
        if not _gradle_available():
            self.skipTest("Gradle wrapper not available")
        rc, stdout, stderr = _run_gradle(["-PappProfile=UNKNOWN", "tasks"])
        combined = stdout + "\n" + stderr
        self.assertNotEqual(
            rc,
            0,
            "Gradle should reject unknown profile value",
        )
        self.assertIn(
            "Invalid appProfile",
            combined,
            "Error message should mention invalid appProfile",
        )


class TestGradleTaskOrder(unittest.TestCase):
    """Verify task dependencies are correctly ordered."""

    def test_prepare_assets_task_exists(self):
        """build.gradle must register prepareAssets task."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        self.assertIn("prepareAssets", text, "prepareAssets task must exist")

    def test_copy_tasks_depend_on_prepare(self):
        """All copy sub-tasks must depend on prepareAssets."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        for task in [
            "copyPanelsInterface",
            "copyPanelsAssets",
            "copyPanelsBridges",
            "copyPanelsLicenses",
        ]:
            # Find the task registration block
            pattern = rf"tasks\.register\(['\"]{task}['\"].*?\n\}}\s*\n"
            m = re.search(pattern, text, re.DOTALL)
            if m:
                block = m.group(0)
                self.assertIn(
                    "prepareAssets",
                    block,
                    f"{task} must depend on prepareAssets",
                )
            else:
                self.fail(f"Could not find {task} task definition")

    def test_copypanels_depends_on_subtasks(self):
        """copyPanels must depend on all four copy sub-tasks."""
        if not APP_BUILD_GRADLE.is_file():
            self.skipTest("build.gradle not found")
        text = APP_BUILD_GRADLE.read_text()
        for sub in [
            "copyPanelsInterface",
            "copyPanelsAssets",
            "copyPanelsBridges",
            "copyPanelsLicenses",
        ]:
            self.assertIn(sub, text, f"copyPanels must depend on {sub}")


class TestSymlinkInOutputRejection(unittest.TestCase):
    """A symlink placed in the generated output must be rejected or removed."""

    @unittest.skipUnless(_gradle_available(), "Gradle wrapper not available")
    def test_symlink_file_in_assets_removed(self):
        """A symlink file placed in assets/ must not survive copyPanels."""
        assets_dir = MVP_ANDROID / "app" / "src" / "main" / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        # Create a real target file and a symlink in assets
        target = MVP_ANDROID / "app" / "src" / "main" / "assets" / "real_target.txt"
        target.write_text("real content")
        symlink = assets_dir / "suspicious_link.txt"
        symlink.symlink_to(target)

        try:
            # Run copyPanels
            rc, stdout, stderr = _run_gradle(["copyPanels"])
            combined = stdout + "\n" + stderr

            if rc != 0:
                self.fail(f"copyPanels failed (rc={rc}): {combined[-2000:]}")

            # The symlink should be gone (removed by prepareAssets)
            if symlink.exists() or symlink.is_symlink():
                self.fail(
                    "Symlink in generated output survived copyPanels — should be removed"
                )
        finally:
            # Cleanup
            if symlink.exists() or symlink.is_symlink():
                symlink.unlink()
            if target.exists():
                target.unlink()
            if assets_dir.exists():
                for item in assets_dir.iterdir():
                    if item.is_file():
                        item.unlink()
                    elif item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
