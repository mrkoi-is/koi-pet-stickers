#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
# Copyright (c) 2026 Mr.Koi. All rights reserved.
# Personal and non-commercial use only; commercial use requires written authorization.
# See ../LICENSE.
"""Normalize uploaded pet photos to deterministic RGB PNG references."""

from __future__ import annotations

import argparse
import json
import os
import sys
import unicodedata
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError


class ReferenceError(Exception):
    """A user-correctable reference preparation failure."""

    def __init__(self, message: str, exit_code: int = 3) -> None:
        super().__init__(message)
        self.exit_code = exit_code


def emit(payload: dict[str, object]) -> None:
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        emit({"error": message, "ok": False})
        raise SystemExit(2)


def normalized_path_key(path: Path) -> str:
    resolved = str(path.expanduser().resolve(strict=False))
    return unicodedata.normalize("NFC", resolved).casefold()


def paths_alias(first: Path, second: Path) -> bool:
    if normalized_path_key(first) == normalized_path_key(second):
        return True
    if first.exists() and second.exists():
        try:
            return os.path.samefile(first, second)
        except OSError:
            return False
    return False


def ensure_unique_paths(paths: list[Path], label: str) -> None:
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            if paths_alias(first, second):
                raise ReferenceError(f"{label} paths must be unique: {first} and {second}", 2)


def flatten_to_rgb(image: Image.Image) -> Image.Image:
    rgba = image.convert("RGBA")
    background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
    background.alpha_composite(rgba)
    return background.convert("RGB")


def limit_long_edge(image: Image.Image, max_side: int) -> Image.Image:
    longest = max(image.size)
    if longest <= max_side:
        return image
    scale = max_side / longest
    size = (
        max(1, round(image.width * scale)),
        max(1, round(image.height * scale)),
    )
    resized = image.resize(size, Image.Resampling.LANCZOS)
    image.close()
    return resized


def load_reference(path: Path) -> tuple[Image.Image, str, int]:
    if not path.is_file():
        raise ReferenceError(f"reference image does not exist: {path}", 2)
    try:
        with Image.open(path) as opened:
            source_format = opened.format or "unknown"
            frame_count = int(getattr(opened, "n_frames", 1))
            opened.seek(0)
            first_frame = ImageOps.exif_transpose(opened.copy())
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise ReferenceError(f"cannot decode reference image {path}: {exc}") from exc

    if first_frame.width < 32 or first_frame.height < 32:
        first_frame.close()
        raise ReferenceError(f"reference image is too small: {path}")
    normalized = flatten_to_rgb(first_frame)
    first_frame.close()
    return normalized, source_format, frame_count


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        description="Normalize one to three pet photos to ordinary RGB PNG files."
    )
    parser.add_argument(
        "--input",
        action="append",
        required=True,
        dest="inputs",
        help="Pet photo path; repeat for multiple photos.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory for RGB PNG references.")
    parser.add_argument(
        "--max-side",
        type=int,
        default=2048,
        help="Downscale the longest edge to this size; never upscale (default: 2048).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    inputs = [Path(value).expanduser() for value in args.inputs]
    if not 1 <= len(inputs) <= 3:
        emit({"error": "provide between one and three --input photos", "ok": False})
        return 2
    if not 512 <= args.max_side <= 4096:
        emit({"error": "--max-side must be between 512 and 4096", "ok": False})
        return 2

    output_dir = Path(args.output_dir).expanduser()
    outputs = [output_dir / f"reference-{index:02d}.png" for index in range(1, len(inputs) + 1)]

    prepared: list[tuple[Image.Image, str, int]] = []
    temporary_paths: list[Path] = []
    try:
        ensure_unique_paths(inputs, "input")
        ensure_unique_paths(outputs, "output")
        for source in inputs:
            for output in outputs:
                if paths_alias(source, output):
                    raise ReferenceError(
                        f"output path must not alias an input reference: {output}", 2
                    )
        prepared = []
        for path in inputs:
            image, source_format, frame_count = load_reference(path)
            prepared.append(
                (limit_long_edge(image, args.max_side), source_format, frame_count)
            )
        output_dir.mkdir(parents=True, exist_ok=True)

        items: list[dict[str, object]] = []
        for index, (source, output, loaded) in enumerate(
            zip(inputs, outputs, prepared, strict=True), start=1
        ):
            image, source_format, frame_count = loaded
            temporary = output.with_name(f".{output.name}.tmp")
            temporary_paths.append(temporary)
            image.save(
                temporary,
                format="PNG",
                compress_level=6,
                optimize=False,
                icc_profile=None,
                exif=b"",
            )
            os.replace(temporary, output)
            items.append(
                {
                    "frame_count": frame_count,
                    "height": image.height,
                    "index": index,
                    "output": str(output.resolve()),
                    "source_format": source_format,
                    "source_name": source.name,
                    "width": image.width,
                }
            )
        emit({"count": len(items), "items": items, "ok": True})
        return 0
    except ReferenceError as exc:
        emit({"error": str(exc), "ok": False})
        return exc.exit_code
    except (OSError, ValueError) as exc:
        emit({"error": f"failed to prepare references: {exc}", "ok": False})
        return 4
    finally:
        for image, _, _ in prepared:
            image.close()
        for temporary in temporary_paths:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass


if __name__ == "__main__":
    sys.exit(main())
