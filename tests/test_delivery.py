#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
"""Synthetic regression tests for optional-text packaging scripts."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from PIL import Image, ImageDraw, PngImagePlugin


SKILL_DIR = Path(__file__).resolve().parents[1]
FINALIZE = SKILL_DIR / "scripts" / "finalize.py"
VALIDATE = SKILL_DIR / "scripts" / "validate.py"
EXPECTED_IDS = (
    "happy",
    "received",
    "angry",
    "wronged",
    "good-morning",
    "good-night",
    "thanks",
    "hug",
    "cheer-up",
    "okay",
    "no",
    "question",
    "eating",
    "miss-you",
    "rush",
    "bye",
)
EXPECTED_TEXT = (
    "开心",
    "收到",
    "生气",
    "委屈",
    "早安",
    "晚安",
    "谢谢",
    "抱抱",
    "加油",
    "好的",
    "不行",
    "怎么啦",
    "吃饭啦",
    "想你啦",
    "冲鸭",
    "拜拜",
)
STYLE_NAMES = {
    "q-cute-handdrawn": "Q萌手绘贴纸",
    "flat-emoji": "极简扁平 Emoji",
    "bold-comic": "粗线漫画大字",
    "crayon-journal": "蜡笔手帐涂鸦",
    "naive-ink-watercolor": "稚拙墨线水彩",
    "bold-ink-caricature": "粗墨怪萌水彩",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class DeliveryScriptsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sources = self.root / "sources"
        self.output = self.root / "output"
        self.job_manifest = self.root / "job-manifest.json"
        self.sources.mkdir()
        stickers = []
        for index, (stable_id, text) in enumerate(
            zip(EXPECTED_IDS, EXPECTED_TEXT, strict=True), start=1
        ):
            filename = f"{index:02d}-{stable_id}.png"
            image = Image.new("RGBA", (640, 640), (255, 255, 255, 0))
            draw = ImageDraw.Draw(image)
            hue = 70 + (index * 9) % 140
            draw.ellipse((170, 160, 470, 520), fill=(hue, 126, 92, 255))
            draw.ellipse((220, 95, 310, 230), fill=(hue, 126, 92, 255))
            draw.ellipse((330, 95, 420, 230), fill=(hue, 126, 92, 255))
            draw.ellipse((260, 300, 295, 335), fill=(20, 25, 35, 255))
            draw.ellipse((345, 300, 380, 335), fill=(20, 25, 35, 255))
            draw.text((250, 40), text, fill=(24, 35, 58, 255))
            metadata = PngImagePlugin.PngInfo()
            metadata.add_text("synthetic-test-metadata", f"source-{index}")
            image.save(self.sources / filename, pnginfo=metadata)
            stickers.append(
                {"file": filename, "id": stable_id, "index": index, "text": text}
            )
        self.job_manifest.write_text(
            json.dumps(
                {
                    "pet_name": "团子",
                    "photo_grade": "A",
                    "schema_version": 1,
                    "stickers": stickers,
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def run_finalize(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(FINALIZE),
                "--input-dir",
                str(self.sources),
                "--manifest",
                str(self.job_manifest),
                "--output-dir",
                str(self.output),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def run_validate(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VALIDATE), "--input-dir", str(self.output)],
            check=False,
            capture_output=True,
            text=True,
        )

    def finalize_successfully(self) -> None:
        result = self.run_finalize()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def report_codes(self) -> set[str]:
        report = json.loads((self.output / "qa-report.json").read_text(encoding="utf-8"))
        return {issue["code"] for issue in report["errors"]}

    def test_happy_path_help_tree_dimensions_metadata_and_warning(self) -> None:
        for script in (FINALIZE, VALIDATE):
            result = subprocess.run(
                [sys.executable, str(script), "--help"],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("usage:", result.stdout)
        for script in (FINALIZE, VALIDATE):
            result = subprocess.run(
                [sys.executable, str(script)],
                check=False,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertFalse(json.loads(result.stdout)["ok"])

        self.finalize_successfully()
        result = self.run_validate()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertTrue(json.loads(result.stdout)["ok"])

        masters = sorted((self.output / "master").glob("*.png"))
        previews = sorted((self.output / "preview").glob("*.png"))
        self.assertEqual(len(masters), 16)
        self.assertEqual([path.name for path in previews], ["contact-sheet.png"])
        self.assertTrue((self.output / "manifest.json").is_file())
        self.assertTrue((self.output / "qa-report.json").is_file())
        manifest = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["style_id"], "q-cute-handdrawn")
        self.assertEqual(manifest["style_name"], "Q萌手绘贴纸")
        self.assertEqual(manifest["schema_version"], 2)
        self.assertEqual(manifest["text_policy"], "all")
        self.assertEqual(manifest["generator_text_mode"], "native-image-text")
        self.assertEqual(manifest["stickers"][0]["semantic"], "开心")
        self.assertEqual(manifest["stickers"][0]["rendered_text"], "开心")
        self.assertEqual(
            manifest["canvas"],
            {"background": "transparent", "height": 1024, "width": 1024},
        )
        with Image.open(masters[0]) as image:
            self.assertEqual(image.mode, "RGBA")
            self.assertEqual(image.size, (1024, 1024))
            self.assertEqual(image.getchannel("A").getextrema(), (0, 255))
            self.assertEqual(image.info, {})
        with Image.open(previews[0]) as image:
            self.assertEqual(image.size, (2048, 2048))
            self.assertEqual(image.mode, "RGB")
            self.assertNotEqual(image.getpixel((0, 0)), image.getpixel((32, 0)))
        report = json.loads((self.output / "qa-report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["warnings"]), 16)
        self.assertEqual(
            {warning["code"] for warning in report["warnings"]},
            {"native_text_requires_visual_qa"},
        )

    def test_schema_v2_none_policy_packages_without_text_warnings(self) -> None:
        manifest = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        manifest["schema_version"] = 2
        manifest["text_policy"] = "none"
        for sticker in manifest["stickers"]:
            sticker["semantic"] = sticker.pop("text")
            sticker["rendered_text"] = None
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        self.finalize_successfully()
        result = self.run_validate()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        delivery = json.loads(
            (self.output / "manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(delivery["schema_version"], 2)
        self.assertEqual(delivery["text_policy"], "none")
        self.assertEqual(delivery["generator_text_mode"], "no-rendered-text")
        self.assertTrue(
            all(item["rendered_text"] is None for item in delivery["stickers"])
        )
        report = json.loads((self.output / "qa-report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["warnings"], [])

    def test_schema_v2_mixed_policies_allow_style_native_text(self) -> None:
        base = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        for policy in ("style-native", "custom"):
            with self.subTest(policy=policy):
                manifest = json.loads(json.dumps(base, ensure_ascii=False))
                manifest["schema_version"] = 2
                manifest["text_policy"] = policy
                for index, sticker in enumerate(manifest["stickers"]):
                    semantic = sticker.pop("text")
                    if index == 0:
                        # schema v2 accepts legacy `text` as the stable semantic alias.
                        sticker["text"] = semantic
                    else:
                        sticker["semantic"] = semantic
                    sticker["rendered_text"] = "Hi!" if index % 2 == 0 else None
                self.job_manifest.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                self.output = self.root / f"output-{policy}"

                self.finalize_successfully()
                result = self.run_validate()
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                delivery = json.loads(
                    (self.output / "manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(delivery["text_policy"], policy)
                self.assertEqual(
                    delivery["generator_text_mode"], "native-image-text-optional"
                )
                self.assertEqual(delivery["stickers"][0]["semantic"], "开心")
                self.assertEqual(delivery["stickers"][0]["rendered_text"], "Hi!")
                report = json.loads(
                    (self.output / "qa-report.json").read_text(encoding="utf-8")
                )
                self.assertEqual(len(report["warnings"]), 8)
                self.assertEqual(
                    {warning["file"] for warning in report["warnings"]},
                    {f"master/sticker-{index:02d}.png" for index in range(1, 17, 2)},
                )

    def test_schema_v2_rejects_policy_conflicts_and_semantic_drift(self) -> None:
        base = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        base["schema_version"] = 2
        for sticker in base["stickers"]:
            sticker["semantic"] = sticker.pop("text")
            sticker["rendered_text"] = sticker["semantic"]

        invalid_cases = []
        invalid_policy = json.loads(json.dumps(base, ensure_ascii=False))
        invalid_policy["text_policy"] = "sometimes"
        invalid_cases.append((invalid_policy, "text_policy"))

        missing_all = json.loads(json.dumps(base, ensure_ascii=False))
        missing_all["text_policy"] = "all"
        missing_all["stickers"][0]["rendered_text"] = None
        invalid_cases.append((missing_all, "text_policy all"))

        unexpected_none = json.loads(json.dumps(base, ensure_ascii=False))
        unexpected_none["text_policy"] = "none"
        invalid_cases.append((unexpected_none, "text_policy none"))

        semantic_drift = json.loads(json.dumps(base, ensure_ascii=False))
        semantic_drift["text_policy"] = "custom"
        semantic_drift["stickers"][0]["semantic"] = "惊讶"
        invalid_cases.append((semantic_drift, "sticker semantic must match"))

        for position, (manifest, message) in enumerate(invalid_cases):
            with self.subTest(message=message):
                self.job_manifest.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                self.output = self.root / f"invalid-v2-{position}"
                result = self.run_finalize()
                self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
                self.assertIn(message, result.stderr)

    def test_validator_accepts_legacy_schema_v1_delivery_manifest(self) -> None:
        self.finalize_successfully()
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["schema_version"] = 1
        manifest.pop("text_policy")
        manifest["generator_text_mode"] = "native-image-text"
        for sticker in manifest["stickers"]:
            semantic = sticker.pop("semantic")
            sticker["text"] = semantic
            sticker["text_sha256"] = sticker.pop("semantic_sha256")
            sticker.pop("rendered_text")
            sticker.pop("rendered_text_sha256")
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

        result = self.run_validate()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        report = json.loads((self.output / "qa-report.json").read_text(encoding="utf-8"))
        self.assertEqual(len(report["warnings"]), 16)

    def test_idempotent_and_sources_unchanged(self) -> None:
        source_hashes = {path.name: sha256(path) for path in self.sources.glob("*.png")}
        self.finalize_successfully()
        delivered = sorted(
            list((self.output / "master").glob("*.png"))
            + list((self.output / "preview").glob("*.png"))
            + [self.output / "manifest.json"]
        )
        first_hashes = {path.relative_to(self.output).as_posix(): sha256(path) for path in delivered}

        self.finalize_successfully()
        second_hashes = {path.relative_to(self.output).as_posix(): sha256(path) for path in delivered}
        self.assertEqual(first_hashes, second_hashes)
        self.assertEqual(
            source_hashes,
            {path.name: sha256(path) for path in self.sources.glob("*.png")},
        )

    def test_all_style_presets_package_and_validate(self) -> None:
        manifest = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        for style_id, style_name in STYLE_NAMES.items():
            with self.subTest(style_id=style_id):
                manifest["style_id"] = style_id
                self.job_manifest.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8",
                )
                self.output = self.root / f"output-{style_id}"
                self.finalize_successfully()
                result = self.run_validate()
                self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
                delivery = json.loads(
                    (self.output / "manifest.json").read_text(encoding="utf-8")
                )
                self.assertEqual(delivery["style_id"], style_id)
                self.assertEqual(delivery["style_name"], style_name)

    def test_rejects_opaque_sources(self) -> None:
        opaque = Image.new("RGB", (640, 640), "white")
        ImageDraw.Draw(opaque).ellipse((170, 160, 470, 520), fill=(120, 80, 60))
        opaque.save(self.sources / "01-happy.png")
        result = self.run_finalize()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("transparent and visible pixels", json.loads(result.stdout)["error"])

    def test_rejects_nearly_opaque_sources_and_rectangular_panels(self) -> None:
        nearly_opaque = Image.new("RGBA", (640, 640), (245, 243, 235, 255))
        nearly_opaque.putpixel((0, 0), (245, 243, 235, 0))
        nearly_opaque.save(self.sources / "01-happy.png")
        result = self.run_finalize()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("at least 10%", json.loads(result.stdout)["error"])

        panel = Image.new("RGBA", (640, 640), (255, 255, 255, 0))
        ImageDraw.Draw(panel).rectangle(
            (20, 20, 619, 619), fill=(245, 243, 235, 255)
        )
        panel.save(self.sources / "01-happy.png")
        result = self.run_finalize()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("rectangular background panel", json.loads(result.stdout)["error"])

    def test_manifest_contract_failures(self) -> None:
        manifest = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        manifest["stickers"][0]["text"] = "错字"
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_finalize()
        self.assertEqual(result.returncode, 2)
        self.assertFalse(json.loads(result.stdout)["ok"])
        self.assertIn("sticker semantic must match", result.stderr)

    def test_rejects_missing_blank_and_duplicate_sources(self) -> None:
        manifest = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        manifest["stickers"][0]["file"] = "missing.png"
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_finalize()
        self.assertEqual(result.returncode, 3)

        manifest["stickers"][0]["file"] = "01-happy.png"
        manifest["stickers"][1]["file"] = "01-happy.png"
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_finalize()
        self.assertEqual(result.returncode, 2)

        manifest["stickers"][1]["file"] = "02-received.png"
        blank = self.sources / "01-happy.png"
        Image.new("RGBA", (640, 640), (255, 255, 255, 0)).save(blank)
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_finalize()
        self.assertEqual(result.returncode, 3)

    def test_validation_reports_tampering(self) -> None:
        self.finalize_successfully()
        manifest_path = self.output / "manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        manifest["stickers"][0]["output_sha256"] = "0" * 64
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        result = self.run_validate()
        self.assertEqual(result.returncode, 5)
        self.assertIn("output_hash_mismatch", self.report_codes())

    def test_validation_reports_invalid_dimensions(self) -> None:
        self.finalize_successfully()
        invalid = Image.new("RGBA", (512, 512), (255, 255, 255, 0))
        ImageDraw.Draw(invalid).ellipse((120, 120, 390, 410), fill=(120, 80, 60, 255))
        invalid.save(self.output / "master" / "sticker-01.png")
        result = self.run_validate()
        self.assertEqual(result.returncode, 5)
        self.assertIn("invalid_dimensions", self.report_codes())

    def test_validation_reports_invalid_transparency_and_extra_assets(self) -> None:
        self.finalize_successfully()
        opaque = Image.new("RGBA", (1024, 1024), (255, 255, 255, 255))
        ImageDraw.Draw(opaque).ellipse((240, 220, 780, 820), fill=(120, 80, 60, 255))
        opaque.save(self.output / "master" / "sticker-01.png")
        (self.output / "notes.txt").write_text("unrelated", encoding="utf-8")
        result = self.run_validate()
        self.assertEqual(result.returncode, 5)
        codes = self.report_codes()
        self.assertIn("invalid_transparency", codes)
        self.assertIn("unexpected_output_files", codes)

    def test_rejects_finalize_and_validator_path_collisions_without_overwrite(self) -> None:
        manifest = json.loads(self.job_manifest.read_text(encoding="utf-8"))
        collision_input = self.output / "master"
        collision_input.mkdir(parents=True)
        collision_source = collision_input / "sticker-01.png"
        collision_source.write_bytes((self.sources / "01-happy.png").read_bytes())
        manifest["stickers"][0]["file"] = "sticker-01.png"
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.sources = collision_input
        original_hash = sha256(collision_source)
        result = self.run_finalize()
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("path collision", json.loads(result.stdout)["error"])
        self.assertEqual(sha256(collision_source), original_hash)

        self.sources = self.root / "sources"
        self.output = self.root / "safe-output"
        manifest["stickers"][0]["file"] = "01-happy.png"
        self.job_manifest.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.finalize_successfully()
        master = self.output / "master" / "sticker-01.png"
        master_hash = sha256(master)
        result = subprocess.run(
            [
                sys.executable,
                str(VALIDATE),
                "--input-dir",
                str(self.output),
                "--report",
                str(master),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("path collision", json.loads(result.stdout)["error"])
        self.assertEqual(sha256(master), master_hash)


if __name__ == "__main__":
    unittest.main()
