#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
"""Regression tests for pet reference normalization."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image


SKILL_DIR = Path(__file__).resolve().parents[1]
PREPARE = SKILL_DIR / "scripts" / "prepare_references.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PrepareReferencesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.output = self.root / "prepared"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_prepare(self, *inputs: Path) -> subprocess.CompletedProcess[str]:
        command = [sys.executable, str(PREPARE)]
        for path in inputs:
            command.extend(["--input", str(path)])
        command.extend(["--output-dir", str(self.output)])
        return subprocess.run(command, check=False, capture_output=True, text=True)

    def test_help_and_argument_errors_are_machine_readable(self) -> None:
        help_result = subprocess.run(
            [sys.executable, str(PREPARE), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("usage:", help_result.stdout)

        missing = subprocess.run(
            [sys.executable, str(PREPARE)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(missing.returncode, 2)
        self.assertFalse(json.loads(missing.stdout)["ok"])

    def test_normalizes_cmyk_jpeg_without_modifying_source(self) -> None:
        source = self.root / "pet.jpg"
        Image.new("CMYK", (180, 120), (10, 30, 50, 0)).save(source, format="JPEG")
        before = sha256(source)

        result = self.run_prepare(source)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["items"][0]["source_format"], "JPEG")
        self.assertEqual(before, sha256(source))

        prepared = self.output / "reference-01.png"
        with Image.open(prepared) as image:
            self.assertEqual(image.format, "PNG")
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.size, (180, 120))
            self.assertEqual(image.info, {})

    def test_uses_first_frame_and_supports_multiple_inputs(self) -> None:
        animated = self.root / "pet-animation.gif"
        first = Image.new("RGB", (96, 80), (240, 30, 20))
        second = Image.new("RGB", (96, 80), (20, 30, 240))
        first.save(animated, save_all=True, append_images=[second], duration=100, loop=0)
        still = self.root / "pet.png"
        Image.new("RGBA", (110, 90), (50, 100, 150, 128)).save(still)

        result = self.run_prepare(animated, still)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["count"], 2)
        self.assertEqual(payload["items"][0]["frame_count"], 2)
        with Image.open(self.output / "reference-01.png") as image:
            self.assertGreater(image.getpixel((20, 20))[0], image.getpixel((20, 20))[2])
        with Image.open(self.output / "reference-02.png") as image:
            self.assertEqual(image.mode, "RGB")
            self.assertEqual(image.getpixel((20, 20)), (152, 177, 202))

    def test_downscales_large_reference_without_upscaling_small_reference(self) -> None:
        large = self.root / "large.jpg"
        Image.new("RGB", (3000, 2000), (80, 120, 160)).save(large, quality=90)
        small = self.root / "small.jpg"
        Image.new("RGB", (640, 480), (40, 60, 80)).save(small, quality=90)

        result = self.run_prepare(large, small)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        with Image.open(self.output / "reference-01.png") as image:
            self.assertEqual(image.size, (2048, 1365))
        with Image.open(self.output / "reference-02.png") as image:
            self.assertEqual(image.size, (640, 480))

    def test_rejects_too_many_duplicate_and_colliding_inputs(self) -> None:
        sources = []
        for index in range(4):
            source = self.root / f"pet-{index}.png"
            Image.new("RGB", (64, 64), (index * 20, 40, 60)).save(source)
            sources.append(source)
        result = self.run_prepare(*sources)
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["ok"])

        result = self.run_prepare(sources[0], sources[0])
        self.assertEqual(result.returncode, 2)
        self.assertIn("unique", json.loads(result.stdout)["error"])

        self.output.mkdir()
        collision = self.output / "reference-01.png"
        Image.new("RGB", (64, 64), "red").save(collision)
        before = sha256(collision)
        result = self.run_prepare(collision)
        self.assertEqual(result.returncode, 2)
        self.assertIn("must not alias", json.loads(result.stdout)["error"])
        self.assertEqual(before, sha256(collision))


if __name__ == "__main__":
    unittest.main(verbosity=2)
