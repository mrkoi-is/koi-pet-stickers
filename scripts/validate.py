#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
# Copyright (c) 2026 Mr.Koi. All rights reserved.
# Personal and non-commercial use only; commercial use requires written authorization.
# See ../LICENSE.
"""Validate an optional-text pet sticker package and write qa-report.json."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, UnidentifiedImageError

from style_presets import get_style_preset


VERSION = "2.1.0"
CANVAS_SIZE = 1024
MIN_TRANSPARENT_RATIO = 0.10
MIN_VISIBLE_RATIO = 0.01
MAX_RECTANGULAR_FILL_RATIO = 0.96
EXPECTED_MASTER_NAMES = tuple(f"sticker-{index:02d}.png" for index in range(1, 17))
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
SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
TEXT_POLICIES = {"style-native", "all", "none", "custom"}


class ValidationSetupError(Exception):
    """An unreadable manifest or invocation problem."""


class JsonArgumentParser(argparse.ArgumentParser):
    """Keep argparse failures machine-readable on stdout."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        print(
            json.dumps(
                {"error": message, "exit_code": 2, "ok": False},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        raise SystemExit(2)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def normalized_path_key(path: Path) -> str:
    return unicodedata.normalize("NFC", str(path.resolve(strict=False))).casefold()


def paths_collide(first: Path, second: Path) -> bool:
    if normalized_path_key(first) == normalized_path_key(second):
        return True
    try:
        return first.exists() and second.exists() and first.samefile(second)
    except OSError:
        return False


def require_distinct_control_paths(
    root: Path, manifest_path: Path, report_path: Path
) -> None:
    paths = [
        ("manifest", manifest_path),
        ("report", report_path),
        ("contact sheet", root / "preview" / "contact-sheet.png"),
        *(
            (f"master {index}", root / "master" / f"sticker-{index:02d}.png")
            for index in range(1, 17)
        ),
    ]
    for index, (first_label, first_path) in enumerate(paths):
        for second_label, second_path in paths[index + 1 :]:
            if paths_collide(first_path, second_path):
                raise ValidationSetupError(
                    f"path collision between {first_label} and {second_label}"
                )


def load_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationSetupError(f"manifest not found: {path}") from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValidationSetupError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict) or value.get("schema_version") not in {1, 2}:
        raise ValidationSetupError("manifest schema_version must be 1 or 2")
    return value


def relative_output(root: Path, raw: Any) -> Path | None:
    if not isinstance(raw, str) or not raw:
        return None
    posix = PurePosixPath(raw)
    if posix.is_absolute() or ".." in posix.parts:
        return None
    candidate = (root / Path(posix)).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return None
    return candidate


def add_issue(
    issues: list[dict[str, str]],
    code: str,
    file: str,
    message: str,
    fix: str,
) -> None:
    issues.append({"code": code, "file": file, "fix": fix, "message": message})


def is_sha256(value: Any) -> bool:
    return isinstance(value, str) and SHA256_PATTERN.fullmatch(value) is not None


def transparent_sticker_problem(image: Image.Image) -> str | None:
    if image.mode != "RGBA":
        return f"master must be RGBA, got {image.mode}"
    alpha = image.getchannel("A")
    alpha_minimum, alpha_maximum = alpha.getextrema()
    if alpha_minimum != 0 or alpha_maximum == 0:
        return "master must contain transparent and visible pixels"
    histogram = alpha.histogram()
    total_pixels = image.width * image.height
    transparent_ratio = histogram[0] / total_pixels
    visible_pixels = total_pixels - histogram[0]
    visible_ratio = visible_pixels / total_pixels
    if transparent_ratio < MIN_TRANSPARENT_RATIO:
        return f"transparent area must cover at least {MIN_TRANSPARENT_RATIO:.0%} of the canvas"
    if visible_ratio < MIN_VISIBLE_RATIO:
        return f"visible sticker area must cover at least {MIN_VISIBLE_RATIO:.0%} of the canvas"
    bbox = alpha.getbbox()
    if bbox is None:
        return "master has no visible sticker content"
    left, top, right, bottom = bbox
    if left == 0 or top == 0 or right == image.width or bottom == image.height:
        return "visible content must not touch the canvas edge"
    bbox_area = (right - left) * (bottom - top)
    if visible_pixels / bbox_area >= MAX_RECTANGULAR_FILL_RATIO:
        return "opaque rectangular background panel is not allowed"
    return None


def validate_package(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    issues: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    schema_version = manifest.get("schema_version")
    if schema_version == 1:
        text_policy = "all"
    else:
        text_policy = manifest.get("text_policy")
        if text_policy not in TEXT_POLICIES:
            add_issue(
                issues,
                "invalid_text_policy",
                "manifest.json",
                f"unsupported text_policy: {text_policy}",
                "rerun scripts/finalize.py with style-native, all, none, or custom",
            )
            text_policy = "custom"

    style_id = manifest.get("style_id")
    try:
        style = get_style_preset(style_id)
    except Exception:
        add_issue(
            issues,
            "unsupported_style_id",
            "manifest.json",
            f"unsupported style_id: {style_id}",
            "repackage with a supported style_id",
        )
        style = {"display_name": None}
    if manifest.get("style_name") != style.get("display_name"):
        add_issue(
            issues,
            "style_name_mismatch",
            "manifest.json",
            "style_name does not match style_id",
            "rerun scripts/finalize.py",
        )
    expected_text_mode = (
        "native-image-text"
        if schema_version == 1 or text_policy == "all"
        else "no-rendered-text"
        if text_policy == "none"
        else "native-image-text-optional"
    )
    if manifest.get("generator_text_mode") != expected_text_mode:
        add_issue(
            issues,
            "invalid_text_mode",
            "manifest.json",
            f"generator_text_mode must be {expected_text_mode}",
            "rerun scripts/finalize.py from the planned cropped cells",
        )

    canvas = manifest.get("canvas", {})
    if not isinstance(canvas, dict) or canvas.get("width") != 1024 or canvas.get("height") != 1024:
        add_issue(
            issues,
            "invalid_canvas",
            "manifest.json",
            "canvas must be 1024×1024",
            "rerun scripts/finalize.py",
        )
    elif canvas.get("background") != "transparent":
        add_issue(
            issues,
            "invalid_canvas_background",
            "manifest.json",
            "canvas background must be transparent",
            "rerun scripts/finalize.py from transparent source cells",
        )

    stickers = manifest.get("stickers")
    if not isinstance(stickers, list) or len(stickers) != 16:
        add_issue(
            issues,
            "invalid_sticker_count",
            "manifest.json",
            "manifest must contain exactly 16 stickers",
            "rerun scripts/finalize.py with a complete job manifest",
        )
        stickers = []

    master_dir = root / "master"
    allowed_files = {
        "manifest.json",
        "qa-report.json",
        "preview/contact-sheet.png",
        *(f"master/{name}" for name in EXPECTED_MASTER_NAMES),
    }
    actual_files = {
        path.relative_to(root).as_posix()
        for path in root.rglob("*")
        if path.is_file()
    }
    unexpected_files = sorted(actual_files - allowed_files)
    if unexpected_files:
        add_issue(
            issues,
            "unexpected_output_files",
            ", ".join(unexpected_files),
            "output tree contains files outside the delivery contract",
            "remove unrelated files and rerun validation",
        )
    actual_master_names = sorted(path.name for path in master_dir.glob("*.png"))
    if tuple(actual_master_names) != EXPECTED_MASTER_NAMES:
        add_issue(
            issues,
            "master_file_set_mismatch",
            "master",
            "master files must be sticker-01.png through sticker-16.png",
            "rerun scripts/finalize.py",
        )

    seen_indices: set[int] = set()
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    expected_pairs = dict(enumerate(zip(EXPECTED_IDS, EXPECTED_TEXT, strict=True), start=1))
    for item in stickers:
        if not isinstance(item, dict):
            add_issue(issues, "invalid_sticker_entry", "manifest.json", "sticker entry must be an object", "rerun scripts/finalize.py")
            continue
        index = item.get("index")
        stable_id = item.get("id")
        output_file = item.get("file")
        if not isinstance(index, int) or index not in range(1, 17):
            add_issue(issues, "invalid_index", "manifest.json", f"invalid sticker index: {index}", "rerun scripts/finalize.py")
            continue
        if index in seen_indices:
            add_issue(issues, "duplicate_index", "manifest.json", f"duplicate sticker index: {index}", "rerun scripts/finalize.py")
        seen_indices.add(index)
        if stable_id in seen_ids:
            add_issue(issues, "duplicate_id", "manifest.json", f"duplicate sticker id: {stable_id}", "rerun scripts/finalize.py")
        seen_ids.add(str(stable_id))
        if output_file in seen_files:
            add_issue(issues, "duplicate_file", "manifest.json", f"duplicate sticker file: {output_file}", "rerun scripts/finalize.py")
        seen_files.add(str(output_file))

        if schema_version == 1:
            semantic = item.get("text")
            rendered_text = semantic
        else:
            semantic = item.get("semantic", item.get("text"))
            rendered_text = item.get("rendered_text")
            if "semantic" in item and "text" in item and item["text"] != semantic:
                add_issue(
                    issues,
                    "semantic_alias_mismatch",
                    "manifest.json",
                    f"index {index} text must equal semantic when both are present",
                    "rerun scripts/finalize.py",
                )
            if "rendered_text" not in item or not (
                rendered_text is None
                or (isinstance(rendered_text, str) and bool(rendered_text.strip()))
            ):
                add_issue(
                    issues,
                    "invalid_rendered_text",
                    "manifest.json",
                    f"index {index} rendered_text must be a non-empty string or null",
                    "rerun scripts/finalize.py",
                )

        expected_id, expected_semantic = expected_pairs[index]
        if stable_id != expected_id or semantic != expected_semantic:
            add_issue(
                issues,
                "sticker_contract_mismatch",
                "manifest.json",
                f"index {index} must be {expected_id}/{expected_semantic}",
                "restore the output contract order and rerun scripts/finalize.py",
            )
        if text_policy == "all" and rendered_text != expected_semantic:
            add_issue(
                issues,
                "text_policy_mismatch",
                "manifest.json",
                f"index {index} must render its semantic under text_policy all",
                "rerun scripts/finalize.py with exact rendered_text",
            )
        if text_policy == "none" and rendered_text is not None:
            add_issue(
                issues,
                "text_policy_mismatch",
                "manifest.json",
                f"index {index} must not render text under text_policy none",
                "rerun scripts/finalize.py with rendered_text null",
            )
        if isinstance(rendered_text, str) and rendered_text.strip():
            warnings.append(
                {
                    "code": "native_text_requires_visual_qa",
                    "file": f"master/sticker-{index:02d}.png",
                    "message": (
                        "machine validation cannot prove the planned rendered text "
                        f"is visually accurate: {rendered_text}"
                    ),
                    "fix": "perform visual QA against rendered_text",
                }
            )

        output_path = relative_output(root, output_file)
        if output_path is None:
            add_issue(issues, "invalid_output_path", "manifest.json", f"invalid output path: {output_file}", "rerun scripts/finalize.py")
            continue
        try:
            output_hash = item.get("output_sha256")
            source_hash = item.get("source_sha256")
            if not is_sha256(output_hash):
                add_issue(issues, "invalid_output_hash", output_file, "output_sha256 must be 64 lowercase hexadecimal characters", "rerun scripts/finalize.py")
            elif sha256_file(output_path) != output_hash:
                add_issue(issues, "output_hash_mismatch", output_file, "output hash does not match manifest", "rerun scripts/finalize.py")
            if not is_sha256(source_hash):
                add_issue(issues, "invalid_source_hash", output_file, "source_sha256 must be 64 lowercase hexadecimal characters", "rerun scripts/finalize.py")
            semantic_hash = (
                item.get("text_sha256")
                if schema_version == 1
                else item.get("semantic_sha256")
            )
            if not is_sha256(semantic_hash):
                add_issue(
                    issues,
                    "invalid_semantic_hash",
                    output_file,
                    "semantic hash must be 64 lowercase hexadecimal characters",
                    "rerun scripts/finalize.py",
                )
            elif isinstance(semantic, str) and hashlib.sha256(
                semantic.encode("utf-8")
            ).hexdigest() != semantic_hash:
                add_issue(
                    issues,
                    "semantic_hash_mismatch",
                    output_file,
                    "semantic hash does not match manifest",
                    "rerun scripts/finalize.py",
                )
            if schema_version == 2:
                rendered_text_hash = item.get("rendered_text_sha256")
                if rendered_text is None:
                    if rendered_text_hash is not None:
                        add_issue(
                            issues,
                            "invalid_rendered_text_hash",
                            output_file,
                            "rendered_text_sha256 must be null when rendered_text is null",
                            "rerun scripts/finalize.py",
                        )
                elif not is_sha256(rendered_text_hash):
                    add_issue(
                        issues,
                        "invalid_rendered_text_hash",
                        output_file,
                        "rendered_text_sha256 must hash non-null rendered_text",
                        "rerun scripts/finalize.py",
                    )
                elif hashlib.sha256(rendered_text.encode("utf-8")).hexdigest() != rendered_text_hash:
                    add_issue(
                        issues,
                        "rendered_text_hash_mismatch",
                        output_file,
                        "rendered text hash does not match manifest",
                        "rerun scripts/finalize.py",
                    )
            with Image.open(output_path) as image:
                if image.format != "PNG":
                    add_issue(issues, "not_png", output_file, "master must be PNG", "rerun scripts/finalize.py")
                if image.size != (CANVAS_SIZE, CANVAS_SIZE):
                    add_issue(issues, "invalid_dimensions", output_file, "master must be 1024×1024", "rerun scripts/finalize.py")
                transparency_problem = transparent_sticker_problem(image)
                if transparency_problem:
                    add_issue(issues, "invalid_transparency", output_file, transparency_problem, "rerun scripts/finalize.py from transparent source cells")
                if image.info:
                    add_issue(issues, "metadata_present", output_file, "master PNG metadata must be stripped", "rerun scripts/finalize.py")
        except FileNotFoundError:
            add_issue(issues, "missing_master", output_file, "master file is missing", "rerun scripts/finalize.py")
        except (OSError, UnidentifiedImageError) as exc:
            add_issue(issues, "unreadable_master", output_file, f"cannot open master: {exc}", "rerun scripts/finalize.py")

    preview = manifest.get("preview", {})
    contact_rel = preview.get("contact_sheet") if isinstance(preview, dict) else None
    contact_path = relative_output(root, contact_rel)
    if contact_path is None or not contact_path.is_file():
        add_issue(
            issues,
            "missing_contact_sheet",
            "preview/contact-sheet.png",
            "contact sheet preview is missing",
            "rerun scripts/finalize.py",
        )
    else:
        if sha256_file(contact_path) != preview.get("contact_sheet_sha256"):
            add_issue(issues, "preview_hash_mismatch", str(contact_rel), "preview hash does not match manifest", "rerun scripts/finalize.py")
        try:
            with Image.open(contact_path) as image:
                if image.format != "PNG" or image.size != (2048, 2048):
                    add_issue(issues, "invalid_contact_sheet", str(contact_rel), "contact sheet must be a 2048×2048 PNG", "rerun scripts/finalize.py")
                if image.mode != "RGB":
                    add_issue(issues, "invalid_contact_sheet_mode", str(contact_rel), "contact sheet must be RGB with a visible checkerboard", "rerun scripts/finalize.py")
                if image.info:
                    add_issue(issues, "preview_metadata_present", str(contact_rel), "preview metadata must be stripped", "rerun scripts/finalize.py")
        except (OSError, UnidentifiedImageError) as exc:
            add_issue(issues, "unreadable_preview", str(contact_rel), f"cannot open preview: {exc}", "rerun scripts/finalize.py")

    return {
        "errors": issues,
        "ok": not issues,
        "schema_version": 2,
        "validator_version": VERSION,
        "warnings": warnings,
    }


def parse_arguments() -> argparse.Namespace:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    root = args.input_dir
    manifest_path = args.manifest or root / "manifest.json"
    report_path = args.report or root / "qa-report.json"
    try:
        require_distinct_control_paths(root, manifest_path, report_path)
        manifest = load_manifest(manifest_path)
        report = validate_package(root, manifest)
        write_json_atomic(report_path, report)
    except ValidationSetupError as exc:
        print(str(exc), file=sys.stderr)
        print(
            json.dumps(
                {"error": str(exc), "exit_code": 2, "ok": False},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 2
    except Exception as exc:  # pragma: no cover
        print(f"unexpected validation failure: {exc}", file=sys.stderr)
        print(
            json.dumps(
                {"error": str(exc), "exit_code": 4, "ok": False},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 4

    exit_code = 0 if report["ok"] else 5
    print(
        json.dumps(
            {
                "error_count": len(report["errors"]),
                "exit_code": exit_code,
                "ok": report["ok"],
                "report": str(report_path),
                "warning_count": len(report["warnings"]),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
