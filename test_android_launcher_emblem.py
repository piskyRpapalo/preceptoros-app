"""Source-only gate: Android launcher reuses the canonical generated ASCII emblem.

Does not assert a device launcher screenshot or a signed APK has been measured.
"""
from pathlib import Path
import re
import struct
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "mvp-android/app/src/main/AndroidManifest.xml"
GRADLE = ROOT / "mvp-android/app/build.gradle"
SOURCE = ROOT / "assets/icono-192.png"
GENERATOR = ROOT / "icons_from_emblem.py"
EMBLEM = ROOT / "assets/emblem/preceptor_face.txt"
ANDROID = "{http://schemas.android.com/apk/res/android}"


class AndroidNativeLauncher(unittest.TestCase):
    def test_existing_emblem_is_authoritative(self):
        self.assertTrue(EMBLEM.is_file())
        self.assertIn("preceptor_face.txt", GENERATOR.read_text(encoding="utf-8"))
        self.assertIn('"icono-192.png": png(g, 192, 192, 0.86)', GENERATOR.read_text())

    def test_png_source_is_valid_and_192_square(self):
        self.assertTrue(SOURCE.is_file(), "NO_DATA(canonical_icon_file_missing)")
        data = SOURCE.read_bytes()
        self.assertGreater(len(data), 32)
        self.assertLessEqual(len(data), 512 * 1024)
        self.assertEqual(data[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(data[12:16], b"IHDR")
        self.assertEqual(struct.unpack(">II", data[16:24]), (192, 192))

    def test_native_manifest_has_exact_icon(self):
        root = ET.parse(MANIFEST).getroot()
        app = root.find("application")
        self.assertIsNotNone(app)
        self.assertEqual(app.attrib.get(ANDROID + "icon"),
                         "@drawable/preceptor_launcher")
        self.assertNotIn(ANDROID + "roundIcon", app.attrib)

    def test_resource_is_generated_from_canonical_source_not_new_artwork(self):
        text = GRADLE.read_text(encoding="utf-8")
        self.assertRegex(text, r"launcherIcon\s*=\s*new File\(appRoot,\s*'assets/icono-192.png'\)")
        self.assertIn("tasks.register('copyLauncherEmblem', Copy)", text)
        self.assertIn("generated/preceptor-launcher/drawable-nodpi", text)
        self.assertIn("rename { 'preceptor_launcher.png' }", text)
        self.assertIn("res.srcDir file(\"$buildDir/generated/preceptor-launcher\")", text)
        self.assertIn("dependsOn 'copyPanels', 'copyLauncherEmblem'", text)
        self.assertIn("java.nio.file.Files.isSymbolicLink(launcherIcon.toPath())", text)
        self.assertFalse(
            (ROOT / "mvp-android/app/src/main/res/drawable-nodpi/preceptor_launcher.png").exists(),
            "Do not commit a second launcher PNG; it must be generated from source",
        )

    def test_launcher_task_is_not_owner_or_public_conditional(self):
        text = GRADLE.read_text(encoding="utf-8")
        task = text.index("tasks.register('copyLauncherEmblem', Copy)")
        android = text.index("\nandroid {\n", task)
        between = text[task:android]
        self.assertNotIn("onlyIf", between)
        self.assertNotIn("if (isOwnerProfile)", between)
        self.assertNotIn("if (!isOwnerProfile)", between)

    def test_manifest_retains_private_and_upgrade_safety(self):
        root = ET.parse(MANIFEST).getroot()
        app = root.find("application")
        self.assertEqual(app.attrib.get(ANDROID + "allowBackup"), "false")
        self.assertEqual(app.attrib.get(ANDROID + "usesCleartextTraffic"), "false")
        text = GRADLE.read_text(encoding="utf-8")
        self.assertIn("mvpVersionCode < 8", text)
        self.assertIn("org.preceptoros.app", text)
        self.assertIn("org.preceptoros.mvp", text)


if __name__ == "__main__":
    unittest.main()
