#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
"""Regression tests for component-owned transparent grid extraction."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Callable

from PIL import Image, ImageDraw


SKILL_DIR = Path(__file__).resolve().parents[1]
EXTRACT_GRID = SKILL_DIR / "scripts" / "extract_grid.py"
FILENAMES = [f"{index:02d}.png" for index in range(1, 17)]


class ExtractGridTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.sheet = self.root / "sheet.png"
        self.output = self.root / "output"
        self.preview = self.root / "preview.png"

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def create_valid_sheet(
        self,
        *,
        mode: str = "RGB",
        background: tuple[int, ...] | str = "white",
        crossing: bool = False,
        first_alpha: int = 255,
        size: tuple[int, int] = (960, 960),
    ) -> None:
        image = Image.new(mode, size, background)
        draw = ImageDraw.Draw(image)
        for index in range(16):
            row, column = divmod(index, 4)
            left = column * 240
            top = row * 240
            if mode == "RGBA":
                alpha = first_alpha if index == 0 else 255
                fill: tuple[int, ...] = (45, 115, 190, alpha)
            else:
                fill = (45, 115, 190)

            if crossing and index == 12:
                fill = (220, 40, 40, 255) if mode == "RGBA" else (220, 40, 40)
                # One connected sticker island crosses the nominal row boundary.
                # Ownership should follow the full component, not a hard crop.
                draw.rectangle((left + 80, top - 12, left + 160, top + 95), fill=fill)
                draw.rectangle((left + 55, top + 75, left + 185, top + 190), fill=fill)
            else:
                draw.rounded_rectangle(
                    (left + 55, top + 45, left + 185, top + 190),
                    radius=24,
                    fill=fill,
                )
        image.save(self.sheet)

    def run_extract(
        self,
        *extra: str,
        output: Path | None = None,
        preview: Path | None = None,
        filenames: list[str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        command = [
            sys.executable,
            str(EXTRACT_GRID),
            "--input-sheet",
            str(self.sheet),
            "--output-dir",
            str(output or self.output),
            "--preview",
            str(preview or self.preview),
            "--rows",
            "4",
            "--cols",
            "4",
            "--min-cell-px",
            "240",
            "--halo-px",
            "2",
            "--padding-px",
            "20",
            "--filenames",
            ",".join(filenames or FILENAMES),
            *extra,
        ]
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_help_and_argument_errors_are_machine_readable(self) -> None:
        help_result = subprocess.run(
            [sys.executable, str(EXTRACT_GRID), "--help"],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(help_result.returncode, 0, help_result.stderr)
        self.assertIn("usage:", help_result.stdout)
        self.assertIn("--source-safe-margin-ratio", help_result.stdout)
        self.assertNotIn("--bleed-px", help_result.stdout)

        missing = subprocess.run(
            [sys.executable, str(EXTRACT_GRID)],
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertEqual(missing.returncode, 2)
        self.assertFalse(json.loads(missing.stdout)["ok"])

    def test_full_crossing_component_belongs_to_one_cell_without_neighbor_residue(self) -> None:
        self.create_valid_sheet(crossing=True)
        result = self.run_extract()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["outputs"]), 16)
        self.assertGreater(payload["uniform_scale"], 0)
        self.assertLessEqual(payload["uniform_scale"], 1.0)
        self.assertIn(
            "source_components_cross_grid",
            {warning["code"] for warning in payload["warnings"]},
        )
        self.assertTrue(self.preview.is_file())

        with Image.open(self.output / "13.png") as owner:
            owner_rgba = owner.convert("RGBA")
            red_pixels = sum(
                1
                for red, green, blue, alpha in owner_rgba.get_flattened_data()
                if alpha > 0 and red > 180 and green < 100 and blue < 100
            )
            self.assertGreater(red_pixels, 1_000)
        with Image.open(self.output / "09.png") as neighbor:
            neighbor_rgba = neighbor.convert("RGBA")
            red_pixels = sum(
                1
                for red, green, blue, alpha in neighbor_rgba.get_flattened_data()
                if alpha > 0 and red > 180 and green < 100 and blue < 100
            )
            self.assertEqual(red_pixels, 0)

        for path in sorted(self.output.glob("*.png")):
            with Image.open(path) as image:
                self.assertEqual(image.mode, "RGBA")
                self.assertEqual(image.size, (240, 240))
                self.assertEqual(image.getchannel("A").getextrema(), (0, 255))

    def test_existing_transparency_and_semitransparency_are_preserved(self) -> None:
        self.create_valid_sheet(
            mode="RGBA",
            background=(255, 255, 255, 0),
            first_alpha=128,
        )
        result = self.run_extract()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        with Image.open(self.output / "01.png") as image:
            self.assertEqual(image.getchannel("A").getextrema(), (0, 128))

    def test_closed_sparse_watercolor_preserves_internal_white_paper(self) -> None:
        sheet = Image.new("RGB", (960, 960), "white")
        draw = ImageDraw.Draw(sheet)
        for index in range(16):
            row, column = divmod(index, 4)
            left = column * 240
            top = row * 240
            draw.ellipse((left + 50, top + 40, left + 190, top + 195), fill=(20, 20, 20))
            draw.ellipse((left + 58, top + 48, left + 182, top + 187), fill="white")
            draw.rounded_rectangle(
                (left + 56, top + 72, left + 102, top + 158),
                radius=12,
                fill=(205, 135, 70),
            )
            draw.ellipse((left + 82, top + 82, left + 96, top + 96), fill=(20, 20, 20))
            draw.ellipse((left + 144, top + 82, left + 158, top + 96), fill=(20, 20, 20))
        sheet.save(self.sheet)

        result = self.run_extract()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        with Image.open(self.output / "01.png") as image:
            rgba = image.convert("RGBA")
            red, green, blue, alpha = rgba.getpixel((120, 120))
            self.assertEqual(alpha, 255)
            self.assertGreaterEqual(min(red, green, blue), 248)
            self.assertEqual(rgba.getchannel("A").getextrema(), (0, 255))

    def test_warns_when_a_cell_contains_disconnected_components(self) -> None:
        self.create_valid_sheet()
        with Image.open(self.sheet) as opened:
            fragmented = opened.convert("RGB")
        ImageDraw.Draw(fragmented).rectangle((250, 205, 262, 217), fill=(220, 40, 40))
        fragmented.save(self.sheet)
        result = self.run_extract()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        self.assertIn(
            "multiple_components_in_cell",
            {warning["code"] for warning in payload["warnings"]},
        )
        self.assertEqual(payload["outputs"][1]["component_count"], 2)

    def test_warns_from_pre_fit_source_edges_and_possible_neighbor_residue(self) -> None:
        self.create_valid_sheet()
        with Image.open(self.sheet) as opened:
            edged = opened.convert("RGB")
        draw = ImageDraw.Draw(edged)
        # Keep the main sticker connected while bringing it to cell 1's right edge.
        draw.rectangle((180, 105, 239, 125), fill=(45, 115, 190))
        # A tiny detached island at cell 2's right edge is suspicious residue.
        draw.rectangle((466, 105, 477, 116), fill=(220, 40, 40))
        edged.save(self.sheet)

        result = self.run_extract("--halo-px", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        warnings = {warning["code"]: warning for warning in payload["warnings"]}
        self.assertIn("source_content_near_cell_edge", warnings)
        self.assertIn("possible_neighbor_residue", warnings)
        cell_one = next(
            detail
            for detail in warnings["source_content_near_cell_edge"]["details"]
            if detail["cell"] == 1
        )
        self.assertIn("right", cell_one["sides"])
        self.assertEqual(cell_one["source_margins"][2], 0)
        self.assertEqual(payload["outputs"][0]["source_margins"][2], 0)
        # Post-fit centering must not erase the evidence of the source-edge risk.
        self.assertGreater(payload["outputs"][0]["margins"][2], 0)

    def test_reports_proportional_source_safe_margin_violations(self) -> None:
        self.create_valid_sheet()
        with Image.open(self.sheet) as opened:
            narrow_margin = opened.convert("RGB")
        draw = ImageDraw.Draw(narrow_margin)
        # Connect to cell 1's main sticker but stay outside the 8 px edge warning.
        draw.rectangle((20, 105, 60, 125), fill=(45, 115, 190))
        narrow_margin.save(self.sheet)

        result = self.run_extract("--halo-px", "0")
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        payload = json.loads(result.stdout)
        warnings = {warning["code"]: warning for warning in payload["warnings"]}
        self.assertIn("source_safe_margin_below_ratio", warnings)
        self.assertEqual(payload["source_safe_margin_ratio"], 0.2)
        cell_one = next(
            detail
            for detail in warnings["source_safe_margin_below_ratio"]["details"]
            if detail["cell"] == 1
        )
        self.assertIn("left", cell_one["sides"])
        self.assertLess(cell_one["source_margin_ratios"][0], 0.2)
        self.assertEqual(
            payload["outputs"][0]["source_margin_ratios"][0],
            cell_one["source_margin_ratios"][0],
        )

    def test_rejects_non_square_tinted_blank_and_missing_cell_inputs(self) -> None:
        cases: list[tuple[str, Callable[[], None]]] = [
            (
                "non-square",
                lambda: self.create_valid_sheet(size=(960, 1200)),
            ),
            (
                "tinted-background",
                lambda: self.create_valid_sheet(background=(245, 243, 235)),
            ),
            (
                "blank",
                lambda: Image.new("RGB", (960, 960), "white").save(self.sheet),
            ),
        ]
        for label, create in cases:
            with self.subTest(label=label):
                create()
                result = self.run_extract()
                self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
                self.assertFalse(json.loads(result.stdout)["ok"])

        self.create_valid_sheet()
        with Image.open(self.sheet) as opened:
            missing_cell = opened.convert("RGB")
        ImageDraw.Draw(missing_cell).rectangle((0, 0, 239, 239), fill="white")
        missing_cell.save(self.sheet)
        result = self.run_extract()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("cell 1", json.loads(result.stdout)["error"])

    def test_rejects_outer_edge_clipping_and_impossible_padding(self) -> None:
        self.create_valid_sheet()
        with Image.open(self.sheet) as opened:
            clipped = opened.convert("RGB")
        draw = ImageDraw.Draw(clipped)
        draw.rectangle((0, 45, 185, 190), fill=(45, 115, 190))
        clipped.save(self.sheet)
        result = self.run_extract()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("outer canvas edge", json.loads(result.stdout)["error"])

        self.create_valid_sheet()
        result = self.run_extract("--padding-px", "120")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("no visible output area", json.loads(result.stdout)["error"])

        self.create_valid_sheet()
        result = self.run_extract("--padding-px", "100")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("too little usable sticker area", json.loads(result.stdout)["error"])

    def test_rejects_tiny_noise_and_per_cell_opaque_panels(self) -> None:
        tiny = Image.new("RGB", (960, 960), "white")
        draw = ImageDraw.Draw(tiny)
        for index in range(16):
            row, column = divmod(index, 4)
            left = column * 240 + 118
            top = row * 240 + 118
            draw.rectangle((left, top, left + 3, top + 3), fill=(30, 30, 30))
        tiny.save(self.sheet)
        result = self.run_extract()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("no substantial sticker", json.loads(result.stdout)["error"])

        panels = Image.new("RGB", (960, 960), "white")
        draw = ImageDraw.Draw(panels)
        for index in range(16):
            row, column = divmod(index, 4)
            left = column * 240 + 20
            top = row * 240 + 20
            draw.rectangle(
                (left, top, left + 199, top + 199),
                fill=(245, 243, 235),
            )
        panels.save(self.sheet)
        result = self.run_extract()
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("rectangular opaque panel", json.loads(result.stdout)["error"])

    def test_rejects_input_tile_and_preview_path_collisions(self) -> None:
        self.create_valid_sheet()
        names = FILENAMES.copy()
        names[0] = self.sheet.name
        result = self.run_extract(output=self.root, filenames=names)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("distinct paths", json.loads(result.stdout)["error"])

        result = self.run_extract(preview=self.output / FILENAMES[0])
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("distinct paths", json.loads(result.stdout)["error"])

        result = self.run_extract(preview=self.output / FILENAMES[0] / "nested.png")
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("distinct paths", json.loads(result.stdout)["error"])

        result = self.run_extract(output=self.sheet)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("output directory", json.loads(result.stdout)["error"])

        self.sheet = self.root / "é.png"
        self.create_valid_sheet()
        unicode_aliases = FILENAMES.copy()
        unicode_aliases[0] = "e\u0301.png"
        result = self.run_extract(output=self.root, filenames=unicode_aliases)
        self.assertEqual(result.returncode, 2, result.stderr + result.stdout)
        self.assertIn("distinct paths", json.loads(result.stdout)["error"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
