"""One canonical Android APP on every device; legacy ID is migration-only.

Static guard complements physical ADB witness in the LAB. It does not install APKs.
"""
import re
import unittest
from pathlib import Path

BUILD = Path(__file__).resolve().parent / "mvp-android/app/build.gradle"
CANONICAL = "org.preceptoros.app"
LEGACY = "org.preceptoros.mvp"


def policy_defects(source):
    defects = []
    default = re.search(
        r"^def\s+mvpAppId\s*=\s*project\.hasProperty\('mvpAppId'\)"
        r"\s*\?\s*project\.property\('mvpAppId'\)\s*:\s*'([^']+)'",
        source, re.MULTILINE,
    )
    if not default or default.group(1) != CANONICAL:
        defects.append("default_must_be_canonical")
    code_default = re.search(
        r"^def\s+mvpVersionCode\s*=\s*\(project\.hasProperty\('mvpVersionCode'\)"
        r"\s*\?\s*project\.property\('mvpVersionCode'\)\s*:\s*'(\d+)'\) as Integer",
        source, re.MULTILINE,
    )
    if not code_default or int(code_default.group(1)) < 8:
        defects.append("version_code_downgrade_default")
    if not re.search(
        r"if\s*\(mvpAppId\s*==\s*'org\.preceptoros\.app'\s*&&\s*mvpVersionCode\s*<\s*8\)",
        source,
    ):
        defects.append("canonical_minimum_version_guard_missing")
    if "def legacyMigrationOnly = project.findProperty('legacyMigrationOnly')" not in source:
        defects.append("migration_flag_missing")
    if not re.search(
        r"if\s*\(mvpAppId\s*==\s*'org\.preceptoros\.mvp'\s*&&\s*!legacyMigrationOnly\)",
        source,
    ):
        defects.append("legacy_package_not_guarded")
    if not re.search(
        r"if\s*\(legacyMigrationOnly\s*&&\s*mvpAppId\s*!=\s*'org\.preceptoros\.mvp'\)",
        source,
    ):
        defects.append("migration_flag_too_broad")
    if 'applicationId mvpAppId' not in source:
        defects.append("application_id_not_bound")
    if 'namespace "org.preceptoros.mvp"' not in source:
        defects.append("java_namespace_migration_break")
    return defects


class OneAndroidAppPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = BUILD.read_text(encoding="utf-8")

    def test_normal_build_is_canonical_and_migration_is_explicit(self):
        self.assertEqual(policy_defects(self.source), [])

    def test_mutant_old_default_goes_red(self):
        changed = self.source.replace(
            "project.property('mvpAppId') : 'org.preceptoros.app'",
            "project.property('mvpAppId') : 'org.preceptoros.mvp'",
        )
        self.assertNotEqual(changed, self.source)
        self.assertIn("default_must_be_canonical", policy_defects(changed))

    def test_mutant_unguarded_legacy_goes_red(self):
        changed = self.source.replace(
            "mvpAppId == 'org.preceptoros.mvp' && !legacyMigrationOnly",
            "mvpAppId == 'org.preceptoros.mvp' && false",
        )
        self.assertNotEqual(changed, self.source)
        self.assertIn("legacy_package_not_guarded", policy_defects(changed))

    def test_mutant_allow_migration_flag_for_any_id_goes_red(self):
        changed = self.source.replace(
            "legacyMigrationOnly && mvpAppId != 'org.preceptoros.mvp'",
            "legacyMigrationOnly && false",
        )
        self.assertNotEqual(changed, self.source)
        self.assertIn("migration_flag_too_broad", policy_defects(changed))

    def test_mutant_old_version_code_default_goes_red(self):
        changed = self.source.replace(
            "project.property('mvpVersionCode') : '8'",
            "project.property('mvpVersionCode') : '1'",
        )
        self.assertNotEqual(changed, self.source)
        self.assertIn("version_code_downgrade_default", policy_defects(changed))

    def test_mutant_missing_canonical_minimum_goes_red(self):
        changed = self.source.replace(
            "mvpAppId == 'org.preceptoros.app' && mvpVersionCode < 8",
            "mvpAppId == 'org.preceptoros.app' && false",
        )
        self.assertNotEqual(changed, self.source)
        self.assertIn("canonical_minimum_version_guard_missing", policy_defects(changed))

    def test_safeguard_does_not_change_java_class_namespace(self):
        self.assertIn('namespace "org.preceptoros.mvp"', self.source)
        self.assertIn("applicationId mvpAppId", self.source)
        self.assertIn("org.preceptoros.app", self.source)


if __name__ == "__main__":
    unittest.main()
