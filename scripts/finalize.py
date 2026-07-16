#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
# Copyright (c) 2026 Mr.Koi. All rights reserved.
# Personal and non-commercial use only; commercial use requires written authorization.
# See ../LICENSE.
"""Package optional-text pet sticker cells into a 16-image delivery tree."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, ImageDraw, ImageOps, UnidentifiedImageError

from style_presets import DEFAULT_STYLE_ID, get_style_preset


VERSION = "2.1.0"
CANVAS_SIZE = 1024
PREVIEW_TILE = 512
MIN_TRANSPARENT_RATIO = 0.10
MIN_VISIBLE_RATIO = 0.01
MAX_RECTANGULAR_FILL_RATIO = 0.96
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
ID_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
TEXT_POLICIES = {"style-native", "all", "none", "custom"}


class DeliveryError(Exception):
    """An expected failure with a stable process exit code."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def normalized_path_key(path: Path) -> str:
    return unicodedata.normalize("NFC", str(path.resolve(strict=False))).casefold()


def paths_collide(first: Path, second: Path) -> bool:
    if normalized_path_key(first) == normalized_path_key(second):
        return True
    try:
        return first.exists() and second.exists() and first.samefile(second)
    except OSError:
        return False


def require_distinct_paths(paths: list[tuple[str, Path]]) -> None:
    for index, (first_label, first_path) in enumerate(paths):
        for second_label, second_path in paths[index + 1 :]:
            if paths_collide(first_path, second_path):
                raise DeliveryError(
                    f"path collision between {first_label} and {second_label}", 2
                )


def write_json_atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    payload = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(path)


def save_png_atomic(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.stem}.tmp.png")
    image.save(temporary, format="PNG", compress_level=9, optimize=False)
    temporary.replace(path)


def require_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DeliveryError(f"{field} must be a non-empty string", 2)
    return value.strip()


def optional_rendered_text(value: Any, field: str) -> str | None:
    if value is None:
        return None
    return require_string(value, field)


def safe_relative_file(value: Any, field: str) -> str:
    raw = require_string(value, field)
    posix = PurePosixPath(raw)
    if posix.is_absolute() or ".." in posix.parts or raw.startswith(("/", "\\")):
        raise DeliveryError(f"{field} must stay inside --input-dir: {raw}", 2)
    if posix.suffix.lower() != ".png":
        raise DeliveryError(f"{field} must reference a PNG file: {raw}", 2)
    return posix.as_posix()


def load_job_manifest(path: Path) -> dict[str, Any]:
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise DeliveryError(f"job manifest not found: {path}", 2) from exc
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise DeliveryError(f"cannot read job manifest {path}: {exc}", 2) from exc

    if not isinstance(manifest, dict) or manifest.get("schema_version") not in {1, 2}:
        raise DeliveryError("job manifest schema_version must be 1 or 2", 2)

    input_schema_version = manifest["schema_version"]
    if input_schema_version == 1:
        text_policy = "all"
    else:
        text_policy = require_string(manifest.get("text_policy"), "text_policy")
        if text_policy not in TEXT_POLICIES:
            raise DeliveryError(
                "text_policy must be style-native, all, none, or custom", 2
            )

    pet_name = require_string(manifest.get("pet_name"), "pet_name")
    photo_grade = require_string(manifest.get("photo_grade"), "photo_grade").upper()
    if photo_grade not in {"A", "B"}:
        raise DeliveryError("photo_grade must be A or B; grade C is not ready", 2)

    style_id = require_string(manifest.get("style_id", DEFAULT_STYLE_ID), "style_id")
    try:
        get_style_preset(style_id)
    except KeyError as exc:
        raise DeliveryError(f"unsupported style_id: {style_id}", 2) from exc

    raw_stickers = manifest.get("stickers")
    if not isinstance(raw_stickers, list) or len(raw_stickers) != 16:
        raise DeliveryError("stickers must contain exactly 16 entries", 2)

    stickers: list[dict[str, Any]] = []
    seen_indices: set[int] = set()
    seen_ids: set[str] = set()
    seen_files: set[str] = set()
    for position, raw in enumerate(raw_stickers, start=1):
        if not isinstance(raw, dict):
            raise DeliveryError(f"stickers[{position}] must be an object", 2)
        index = raw.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or not 1 <= index <= 16:
            raise DeliveryError(f"stickers[{position}].index must be an integer 1..16", 2)
        stable_id = require_string(raw.get("id"), f"stickers[{position}].id")
        if not ID_PATTERN.fullmatch(stable_id):
            raise DeliveryError(f"invalid stable id: {stable_id}", 2)
        if input_schema_version == 1:
            semantic = require_string(raw.get("text"), f"stickers[{position}].text")
            rendered_text = semantic
        else:
            semantic_value = raw.get("semantic", raw.get("text"))
            semantic = require_string(
                semantic_value, f"stickers[{position}].semantic"
            )
            if "semantic" in raw and "text" in raw:
                legacy_semantic = require_string(
                    raw.get("text"), f"stickers[{position}].text"
                )
                if legacy_semantic != semantic:
                    raise DeliveryError(
                        f"stickers[{position}].text must equal semantic when both are present",
                        2,
                    )
            if "rendered_text" not in raw:
                raise DeliveryError(
                    f"stickers[{position}].rendered_text must be a string or null", 2
                )
            rendered_text = optional_rendered_text(
                raw.get("rendered_text"), f"stickers[{position}].rendered_text"
            )
        source_file = safe_relative_file(raw.get("file"), f"stickers[{position}].file")
        if index in seen_indices:
            raise DeliveryError(f"duplicate sticker index: {index}", 2)
        if stable_id in seen_ids:
            raise DeliveryError(f"duplicate sticker id: {stable_id}", 2)
        if source_file in seen_files:
            raise DeliveryError(f"duplicate source file: {source_file}", 2)
        seen_indices.add(index)
        seen_ids.add(stable_id)
        seen_files.add(source_file)
        stickers.append(
            {
                "index": index,
                "id": stable_id,
                "semantic": semantic,
                "rendered_text": rendered_text,
                "file": source_file,
            }
        )

    stickers.sort(key=lambda item: item["index"])
    if [item["index"] for item in stickers] != list(range(1, 17)):
        raise DeliveryError("sticker indices must cover 1..16 exactly", 2)
    if tuple(item["id"] for item in stickers) != EXPECTED_IDS:
        raise DeliveryError("stable ids must match the output contract in index order", 2)
    if tuple(item["semantic"] for item in stickers) != EXPECTED_TEXT:
        raise DeliveryError(
            "sticker semantic must match the output contract in index order", 2
        )
    if text_policy == "all" and any(
        item["rendered_text"] != item["semantic"] for item in stickers
    ):
        raise DeliveryError(
            "text_policy all requires rendered_text to equal semantic for all stickers",
            2,
        )
    if text_policy == "none" and any(
        item["rendered_text"] is not None for item in stickers
    ):
        raise DeliveryError(
            "text_policy none requires rendered_text to be null for all stickers", 2
        )

    return {
        "schema_version": 2,
        "input_schema_version": input_schema_version,
        "pet_name": pet_name,
        "photo_grade": photo_grade,
        "style_id": style_id,
        "text_policy": text_policy,
        "stickers": stickers,
    }


def resolve_source(input_dir: Path, relative: str) -> Path:
    root = input_dir.resolve()
    candidate = (root / Path(PurePosixPath(relative))).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise DeliveryError(f"source escapes --input-dir: {relative}", 3) from exc
    return candidate


def transparent_sticker_problem(image: Image.Image) -> str | None:
    alpha = image.getchannel("A")
    alpha_minimum, alpha_maximum = alpha.getextrema()
    if alpha_minimum != 0 or alpha_maximum == 0:
        return "must contain transparent and visible pixels"
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
        return "has no visible sticker content"
    left, top, right, bottom = bbox
    if left == 0 or top == 0 or right == image.width or bottom == image.height:
        return "visible content must not touch the canvas edge"
    bbox_area = (right - left) * (bottom - top)
    if visible_pixels / bbox_area >= MAX_RECTANGULAR_FILL_RATIO:
        return "opaque rectangular background panel is not allowed"
    return None


def load_source(path: Path) -> Image.Image:
    try:
        with Image.open(path) as opened:
            if opened.format != "PNG":
                raise DeliveryError(f"source must be PNG: {path}", 3)
            image = opened.convert("RGBA")
    except FileNotFoundError as exc:
        raise DeliveryError(f"source image not found: {path}", 3) from exc
    except DeliveryError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise DeliveryError(f"cannot open source image {path}: {exc}", 3) from exc

    if image.width < 128 or image.height < 128:
        raise DeliveryError(f"source image is too small: {path}", 3)
    problem = transparent_sticker_problem(image)
    if problem:
        raise DeliveryError(f"invalid transparent source {path}: {problem}", 3)
    return image


def normalize_cell(source: Image.Image) -> Image.Image:
    fitted = ImageOps.contain(
        source.convert("RGBA"),
        (CANVAS_SIZE, CANVAS_SIZE),
        method=Image.Resampling.LANCZOS,
    )
    canvas = Image.new("RGBA", (CANVAS_SIZE, CANVAS_SIZE), (255, 255, 255, 0))
    x = (CANVAS_SIZE - fitted.width) // 2
    y = (CANVAS_SIZE - fitted.height) // 2
    canvas.alpha_composite(fitted, (x, y))
    canvas.info.clear()
    return canvas


def build_checkerboard(size: tuple[int, int], tile_size: int = 32) -> Image.Image:
    sheet = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(sheet)
    for y in range(0, size[1], tile_size):
        for x in range(0, size[0], tile_size):
            color = (
                (230, 230, 230, 255)
                if (x // tile_size + y // tile_size) % 2 == 0
                else (255, 255, 255, 255)
            )
            draw.rectangle(
                (
                    x,
                    y,
                    min(x + tile_size - 1, size[0] - 1),
                    min(y + tile_size - 1, size[1] - 1),
                ),
                fill=color,
            )
    return sheet


def build_contact_sheet(master_paths: list[Path]) -> Image.Image:
    sheet = build_checkerboard((PREVIEW_TILE * 4, PREVIEW_TILE * 4))
    for index, path in enumerate(master_paths):
        with Image.open(path) as opened:
            tile = ImageOps.contain(
                opened.convert("RGBA"),
                (PREVIEW_TILE, PREVIEW_TILE),
                method=Image.Resampling.LANCZOS,
            )
        row, column = divmod(index, 4)
        x = column * PREVIEW_TILE + (PREVIEW_TILE - tile.width) // 2
        y = row * PREVIEW_TILE + (PREVIEW_TILE - tile.height) // 2
        sheet.alpha_composite(tile, (x, y))
    return sheet.convert("RGB")


def finalize(input_dir: Path, manifest_path: Path, output_dir: Path) -> dict[str, Any]:
    job = load_job_manifest(manifest_path)
    style = get_style_preset(job["style_id"])

    master_dir = output_dir / "master"
    preview_dir = output_dir / "preview"
    source_paths = [
        resolve_source(input_dir, item["file"]) for item in job["stickers"]
    ]
    planned_master_paths = [
        master_dir / f"sticker-{item['index']:02d}.png" for item in job["stickers"]
    ]
    require_distinct_paths(
        [("job manifest", manifest_path)]
        + [
            (f"source {item['index']}", source_path)
            for item, source_path in zip(job["stickers"], source_paths, strict=True)
        ]
        + [
            (f"master {item['index']}", output_path)
            for item, output_path in zip(
                job["stickers"], planned_master_paths, strict=True
            )
        ]
        + [
            ("delivery manifest", output_dir / "manifest.json"),
            ("contact sheet", preview_dir / "contact-sheet.png"),
        ]
    )
    master_dir.mkdir(parents=True, exist_ok=True)
    preview_dir.mkdir(parents=True, exist_ok=True)

    stickers: list[dict[str, Any]] = []
    master_paths: list[Path] = []
    for item, source_path in zip(job["stickers"], source_paths, strict=True):
        source = load_source(source_path)
        source_hash = sha256_file(source_path)
        master = normalize_cell(source)
        output_name = f"sticker-{item['index']:02d}.png"
        output_path = master_dir / output_name
        save_png_atomic(master, output_path)
        master_paths.append(output_path)
        stickers.append(
            {
                "file": f"master/{output_name}",
                "id": item["id"],
                "index": item["index"],
                "output_sha256": sha256_file(output_path),
                "source_file": item["file"],
                "source_sha256": source_hash,
                "semantic": item["semantic"],
                "semantic_sha256": sha256_bytes(
                    item["semantic"].encode("utf-8")
                ),
                "rendered_text": item["rendered_text"],
                "rendered_text_sha256": (
                    sha256_bytes(item["rendered_text"].encode("utf-8"))
                    if item["rendered_text"] is not None
                    else None
                ),
            }
        )

    contact_sheet = build_contact_sheet(master_paths)
    contact_path = preview_dir / "contact-sheet.png"
    save_png_atomic(contact_sheet, contact_path)

    delivery_manifest = {
        "canvas": {
            "background": "transparent",
            "height": CANVAS_SIZE,
            "width": CANVAS_SIZE,
        },
        "generator_text_mode": {
            "all": "native-image-text",
            "none": "no-rendered-text",
            "style-native": "native-image-text-optional",
            "custom": "native-image-text-optional",
        }[job["text_policy"]],
        "manifest_version": VERSION,
        "pet_name": job["pet_name"],
        "photo_grade": job["photo_grade"],
        "preview": {
            "contact_sheet": "preview/contact-sheet.png",
            "contact_sheet_sha256": sha256_file(contact_path),
        },
        "schema_version": 2,
        "stickers": stickers,
        "style_id": job["style_id"],
        "style_name": style["display_name"],
        "text_policy": job["text_policy"],
    }
    write_json_atomic(output_dir / "manifest.json", delivery_manifest)
    return {
        "exit_code": 0,
        "manifest": str(output_dir / "manifest.json"),
        "ok": True,
        "output_dir": str(output_dir),
        "sticker_count": len(stickers),
    }


def parse_arguments() -> argparse.Namespace:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_arguments()
    try:
        result = finalize(args.input_dir, args.manifest, args.output_dir)
    except DeliveryError as exc:
        print(str(exc), file=sys.stderr)
        print(
            json.dumps(
                {"error": str(exc), "exit_code": exc.code, "ok": False},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return exc.code
    except Exception as exc:  # pragma: no cover
        print(f"unexpected packaging failure: {exc}", file=sys.stderr)
        print(
            json.dumps(
                {"error": str(exc), "exit_code": 4, "ok": False},
                ensure_ascii=False,
                separators=(",", ":"),
            )
        )
        return 4

    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
