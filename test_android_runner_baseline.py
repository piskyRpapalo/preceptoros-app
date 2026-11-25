"""The on-phone Talk runner must run on every arm64 phone we ship to (2026-11-25).

Measured: runner sha 18f14e79… carried 260 i8mm instructions (smmla) and died with SIGILL on the
Doogee S110 (MT6789, ARMv8.2 + dotprod, no i8mm) as soon as Talk sent a message. The rebuilt runner
(armv8.2-a+dotprod+fp16) answered on the same phone at ~62 tokens/s.

This test pins the recipe and the Gradle guard; it needs no NDK and no runner binary.
Run: python3 -m unittest test_android_runner_baseline
"""
import re
import struct
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent
GRADLE = (ROOT / "mvp-android/app/build.gradle").read_text(encoding="utf-8")
RECIPE = (ROOT / "mvp-android/native-mini/build-runner-android.sh").read_text(encoding="utf-8")


def i8mm_in_exec(blob: bytes) -> int:
    """Python twin of build.gradle's i8mmInstructions: SMMLA/UMMLA/USMMLA words in SHF_EXECINSTR sections."""
    shoff = struct.unpack_from("<Q", blob, 0x28)[0]
    shentsize, shnum = struct.unpack_from("<HH", blob, 0x3A)
    count = 0
    for i in range(shnum):
        o = shoff + i * shentsize
        if struct.unpack_from("<I", blob, o + 4)[0] != 1 or not struct.unpack_from("<Q", blob, o + 8)[0] & 4:
            continue
        off, size = struct.unpack_from("<QQ", blob, o + 0x18)
        for j in range(off, off + size - 3, 4):
            if struct.unpack_from("<I", blob, j)[0] & 0xFFE0FC00 in (0x4E80A400, 0x6E80A400, 0x4E80AC00):
                count += 1
    return count


def tiny_elf(words, exec_section=True) -> bytes:
    """A minimal ELF64 with one PROGBITS section holding `words` (executable or data) and a null section."""
    text = b"".join(struct.pack("<I", w) for w in words)
    head = bytearray(0x40)
    head[0:4] = b"\x7fELF"
    shoff = 0x40 + len(text)
    struct.pack_into("<Q", head, 0x28, shoff)
    struct.pack_into("<HHH", head, 0x3A, 0x40, 2, 0)
    null = bytes(0x40)
    sec = bytearray(0x40)
    struct.pack_into("<I", sec, 4, 1)
    struct.pack_into("<Q", sec, 8, 6 if exec_section else 2)
    struct.pack_into("<QQ", sec, 0x18, 0x40, len(text))
    return bytes(head) + text + null + bytes(sec)


class RunnerBaseline(unittest.TestCase):
    def test_recipe_pins_the_portable_baseline(self):
        self.assertIn("-DGGML_NATIVE=OFF", RECIPE)
        self.assertIn("-DGGML_CPU_ARM_ARCH=armv8.2-a+dotprod+fp16", RECIPE)
        arch = re.search(r"-DGGML_CPU_ARM_ARCH=(\S+)", RECIPE).group(1)
        self.assertNotIn("i8mm", arch)
        self.assertNotIn("sve", arch)
        self.assertIn("f2cc7282ce0042641df55e0e563b75e824e2b647", RECIPE)

    def test_gradle_refuses_a_runner_with_i8mm(self):
        self.assertIn("def i8mmInstructions", GRADLE)
        self.assertRegex(GRADLE, r"if \(i8mm > 0\) throw new GradleException")
        for op in ("0x4e80a400", "0x6e80a400", "0x4e80ac00"):
            self.assertIn(op, GRADLE)

    def test_scan_counts_code_not_data(self):
        smmla = 0x4E93A641  # the exact instruction that faulted on the S110
        self.assertEqual(i8mm_in_exec(tiny_elf([0xD503201F, smmla])), 1)
        self.assertEqual(i8mm_in_exec(tiny_elf([smmla], exec_section=False)), 0)
        self.assertEqual(i8mm_in_exec(tiny_elf([0x4E8094A0])), 0)  # sdot (dotprod) stays allowed


if __name__ == "__main__":
    unittest.main()
