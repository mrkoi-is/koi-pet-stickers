#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["Pillow==12.3.0"]
# ///
# Copyright (c) 2026 Mr.Koi. All rights reserved.
# Personal and non-commercial use only; commercial use requires written authorization.
# See ../LICENSE.
"""Extract 16 transparent stickers by assigning full-sheet components to grid cells."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import unicodedata
from collections import deque
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFilter, UnidentifiedImageError


VERSION = "2.1.0"
DEFAULT_ROWS = 4
DEFAULT_COLUMNS = 4
DEFAULT_MIN_CELL_PX = 240
DEFAULT_HALO_PX = 2
DEFAULT_PADDING_PX = 22
DEFAULT_BACKGROUND_THRESHOLD = 248
DEFAULT_MIN_COMPONENT_AREA = 8
DEFAULT_MIN_ANCHOR_AREA_RATIO = 0.02
DEFAULT_BOUNDARY_WARNING_PX = 8
DEFAULT_SOURCE_SAFE_MARGIN_RATIO = 0.20
DEFAULT_MAX_RECTANGULAR_FILL_RATIO = 0.96
DEFAULT_MIN_PANEL_DIMENSION_RATIO = 0.7
DEFAULT_MIN_USABLE_DIMENSION_RATIO = 0.5
DEFAULT_MAX_RESIDUE_AREA_RATIO = 0.12


class ExtractGridError(Exception):
    """An expected failure with a stable process exit code."""

    def __init__(self, message: str, code: int) -> None:
        super().__init__(message)
        self.code = code


class JsonArgumentParser(argparse.ArgumentParser):
    """Keep command-line failures machine-readable on stdout."""

    def error(self, message: str) -> None:
        self.print_usage(sys.stderr)
        print(f"{self.prog}: error: {message}", file=sys.stderr)
        print_json({"error": message, "exit_code": 2, "ok": False})
        raise SystemExit(2)


def print_json(value: dict[str, Any]) -> None:
    print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def nonnegative_integer(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if value < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return value


def positive_integer(raw: str) -> int:
    value = nonnegative_integer(raw)
    if value < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return value


def threshold_0_255(raw: str) -> int:
    value = positive_integer(raw)
    if value > 255:
        raise argparse.ArgumentTypeError("must be <= 255")
    return value


def margin_ratio(raw: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a number") from exc
    if value < 0 or value >= 0.5:
        raise argparse.ArgumentTypeError("must be >= 0 and < 0.5")
    return value


def output_filenames(raw: str | None, count: int) -> list[str]:
    if raw is None:
        width = max(2, len(str(count)))
        return [f"tile-{index:0{width}d}.png" for index in range(1, count + 1)]

    names = [part.strip() for part in raw.split(",")]
    if len(names) != count or any(not name for name in names):
        raise ExtractGridError(
            f"--filenames must contain exactly {count} non-empty names", 2
        )
    seen: set[str] = set()
    for name in names:
        path = Path(name)
        if (
            name in {".", ".."}
            or path.name != name
            or "/" in name
            or "\\" in name
            or any(ord(character) < 32 for character in name)
            or path.suffix.lower() != ".png"
        ):
            raise ExtractGridError(
                f"unsafe output filename (use a PNG basename only): {name}", 2
            )
        folded = unicodedata.normalize("NFC", name).casefold()
        if folded in seen:
            raise ExtractGridError(f"duplicate output filename: {name}", 2)
        seen.add(folded)
    return names


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(description=__doc__)
    parser.add_argument("--input-sheet", "--input", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--preview", type=Path)
    parser.add_argument("--rows", type=positive_integer, default=DEFAULT_ROWS)
    parser.add_argument("--cols", type=positive_integer, default=DEFAULT_COLUMNS)
    parser.add_argument(
        "--filenames",
        "--output-files",
        help="Comma-separated PNG basenames in row-major order.",
    )
    parser.add_argument("--min-cell-px", type=positive_integer, default=DEFAULT_MIN_CELL_PX)
    parser.add_argument("--halo-px", type=nonnegative_integer, default=DEFAULT_HALO_PX)
    parser.add_argument("--padding-px", type=nonnegative_integer, default=DEFAULT_PADDING_PX)
    parser.add_argument(
        "--min-component-area",
        type=positive_integer,
        default=DEFAULT_MIN_COMPONENT_AREA,
    )
    parser.add_argument(
        "--boundary-warning-px",
        type=nonnegative_integer,
        default=DEFAULT_BOUNDARY_WARNING_PX,
    )
    parser.add_argument(
        "--source-safe-margin-ratio",
        type=margin_ratio,
        default=DEFAULT_SOURCE_SAFE_MARGIN_RATIO,
        help="Minimum pre-fit blank margin on every cell side as a fraction of cell size.",
    )
    parser.add_argument(
        "--background-threshold",
        type=threshold_0_255,
        default=DEFAULT_BACKGROUND_THRESHOLD,
    )
    parser.add_argument("--version", action="version", version=VERSION)
    return parser


def load_sheet(path: Path) -> Image.Image:
    try:
        with Image.open(path) as opened:
            opened.load()
            if getattr(opened, "n_frames", 1) != 1:
                raise ExtractGridError("input sheet must be a static image", 3)
            return opened.convert("RGBA")
    except ExtractGridError:
        raise
    except FileNotFoundError as exc:
        raise ExtractGridError(f"input sheet not found: {path}", 3) from exc
    except (OSError, UnidentifiedImageError, Image.DecompressionBombError) as exc:
        raise ExtractGridError(f"cannot open input sheet {path}: {exc}", 3) from exc


def pad_to_divisible(sheet: Image.Image, rows: int, columns: int) -> tuple[Image.Image, bool]:
    width, height = sheet.size
    padded_width = ((width + columns - 1) // columns) * columns
    padded_height = ((height + rows - 1) // rows) * rows
    if (padded_width, padded_height) == (width, height):
        return sheet, False
    canvas = Image.new("RGBA", (padded_width, padded_height), (255, 255, 255, 255))
    canvas.alpha_composite(sheet, (0, 0))
    return canvas, True


def near_white_mask(image: Image.Image, threshold: int) -> Image.Image:
    mask = Image.new("1", image.size, 0)
    pixels = image.load()
    output = mask.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 0 and red >= threshold and green >= threshold and blue >= threshold:
                output[x, y] = 1
    return mask


def border_connected_background(near_white: Image.Image) -> Image.Image:
    width, height = near_white.size
    source = near_white.load()
    visited = Image.new("1", near_white.size, 0)
    output = visited.load()
    queue: deque[tuple[int, int]] = deque()

    def enqueue(x: int, y: int) -> None:
        if source[x, y] and not output[x, y]:
            output[x, y] = 1
            queue.append((x, y))

    for x in range(width):
        enqueue(x, 0)
        enqueue(x, height - 1)
    for y in range(height):
        enqueue(0, y)
        enqueue(width - 1, y)
    while queue:
        x, y = queue.popleft()
        for next_x, next_y in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if 0 <= next_x < width and 0 <= next_y < height:
                enqueue(next_x, next_y)
    return visited.convert("L")


def visible_content_mask(image: Image.Image, threshold: int) -> Image.Image:
    mask = Image.new("L", image.size, 0)
    pixels = image.load()
    output = mask.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            red, green, blue, alpha = pixels[x, y]
            if alpha > 0 and not (red >= threshold and green >= threshold and blue >= threshold):
                output[x, y] = 255
    return mask


def transparentize_sheet(image: Image.Image, threshold: int, halo_px: int) -> Image.Image:
    background = border_connected_background(near_white_mask(image, threshold))
    content = visible_content_mask(image, threshold)
    if halo_px > 0:
        halo_size = halo_px * 2 + 1
        protected = content.filter(ImageFilter.MaxFilter(halo_size))
    else:
        protected = content

    source_alpha = image.getchannel("A")
    alpha = source_alpha.copy()
    alpha_pixels = alpha.load()
    background_pixels = background.load()
    protected_pixels = protected.load()
    width, height = image.size
    for y in range(height):
        for x in range(width):
            if background_pixels[x, y] and protected_pixels[x, y] == 0:
                alpha_pixels[x, y] = 0
    if halo_px > 0:
        blurred = alpha.filter(ImageFilter.GaussianBlur(0.25))
        source_pixels = source_alpha.load()
        blurred_pixels = blurred.load()
        for y in range(height):
            for x in range(width):
                blurred_pixels[x, y] = min(blurred_pixels[x, y], source_pixels[x, y])
        alpha = blurred
    result = image.copy()
    result.putalpha(alpha)
    result.info.clear()
    return result


def connected_components(alpha: Image.Image, min_area: int) -> list[dict[str, Any]]:
    width, height = alpha.size
    source = alpha.load()
    visited = Image.new("1", alpha.size, 0)
    visited_pixels = visited.load()
    components: list[dict[str, Any]] = []
    for y in range(height):
        for x in range(width):
            if visited_pixels[x, y] or source[x, y] == 0:
                continue
            queue: deque[tuple[int, int]] = deque([(x, y)])
            visited_pixels[x, y] = 1
            pixels: list[tuple[int, int]] = []
            min_x = max_x = x
            min_y = max_y = y
            sum_x = 0
            sum_y = 0
            while queue:
                current_x, current_y = queue.popleft()
                pixels.append((current_x, current_y))
                sum_x += current_x
                sum_y += current_y
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)
                for next_x, next_y in (
                    (current_x - 1, current_y),
                    (current_x + 1, current_y),
                    (current_x, current_y - 1),
                    (current_x, current_y + 1),
                ):
                    if (
                        0 <= next_x < width
                        and 0 <= next_y < height
                        and not visited_pixels[next_x, next_y]
                        and source[next_x, next_y] > 0
                    ):
                        visited_pixels[next_x, next_y] = 1
                        queue.append((next_x, next_y))
            area = len(pixels)
            if area < min_area:
                continue
            components.append(
                {
                    "area": area,
                    "bbox": (min_x, min_y, max_x + 1, max_y + 1),
                    "center": (sum_x / area, sum_y / area),
                    "pixels": pixels,
                }
            )
    return components


def component_crossings(
    component: dict[str, Any], width: int, height: int, rows: int, columns: int
) -> dict[str, list[int]]:
    left, top, right, bottom = component["bbox"]
    vertical = [
        round(width * index / columns)
        for index in range(1, columns)
        if left < round(width * index / columns) < right
    ]
    horizontal = [
        round(height * index / rows)
        for index in range(1, rows)
        if top < round(height * index / rows) < bottom
    ]
    return {"horizontal": horizontal, "vertical": vertical}


def group_image(sheet: Image.Image, components: list[dict[str, Any]]) -> Image.Image:
    left = min(component["bbox"][0] for component in components)
    top = min(component["bbox"][1] for component in components)
    right = max(component["bbox"][2] for component in components)
    bottom = max(component["bbox"][3] for component in components)
    grouped = sheet.crop((left, top, right, bottom))
    source_alpha = sheet.getchannel("A").load()
    mask = Image.new("L", grouped.size, 0)
    mask_pixels = mask.load()
    for component in components:
        for x, y in component["pixels"]:
            mask_pixels[x - left, y - top] = source_alpha[x, y]
    grouped.putalpha(mask)
    grouped.info.clear()
    return grouped


def fit_groups_uniformly(
    groups: list[Image.Image], output_size: tuple[int, int], padding_px: int
) -> tuple[list[Image.Image], float]:
    target_width = output_size[0] - 2 * padding_px
    target_height = output_size[1] - 2 * padding_px
    if target_width < 1 or target_height < 1:
        raise ExtractGridError("--padding-px leaves no visible output area", 2)
    if (
        target_width < output_size[0] * DEFAULT_MIN_USABLE_DIMENSION_RATIO
        or target_height < output_size[1] * DEFAULT_MIN_USABLE_DIMENSION_RATIO
    ):
        raise ExtractGridError(
            "--padding-px leaves too little usable sticker area; keep at least half of each output dimension",
            2,
        )
    max_width = max(group.width for group in groups)
    max_height = max(group.height for group in groups)
    scale = min(1.0, target_width / max_width, target_height / max_height)
    fitted_groups: list[Image.Image] = []
    for group in groups:
        if scale < 1.0:
            fitted = group.resize(
                (max(1, round(group.width * scale)), max(1, round(group.height * scale))),
                Image.Resampling.LANCZOS,
            )
        else:
            fitted = group
        canvas = Image.new("RGBA", output_size, (255, 255, 255, 0))
        x = (output_size[0] - fitted.width) // 2
        y = (output_size[1] - fitted.height) // 2
        canvas.alpha_composite(fitted, (x, y))
        canvas.info.clear()
        fitted_groups.append(canvas)
    return fitted_groups, scale


def save_png_atomic(image: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_raw = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=".tmp.png", dir=path.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_raw)
    try:
        image.save(temporary, format="PNG", compress_level=9, optimize=False)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def build_checkerboard(size: tuple[int, int], tile_size: int = 18) -> Image.Image:
    image = Image.new("RGBA", size, (255, 255, 255, 255))
    draw = ImageDraw.Draw(image)
    for y in range(0, size[1], tile_size):
        for x in range(0, size[0], tile_size):
            color = (
                (232, 232, 232, 255)
                if (x // tile_size + y // tile_size) % 2 == 0
                else (255, 255, 255, 255)
            )
            draw.rectangle(
                (x, y, min(x + tile_size - 1, size[0] - 1), min(y + tile_size - 1, size[1] - 1)),
                fill=color,
            )
    return image


def build_preview(paths: list[Path], rows: int, columns: int, preview_path: Path) -> None:
    with Image.open(paths[0]) as first:
        cell_width, cell_height = first.size
    sheet = build_checkerboard((cell_width * columns, cell_height * rows))
    for index, path in enumerate(paths):
        with Image.open(path) as opened:
            tile = opened.convert("RGBA")
        sheet.alpha_composite(
            tile,
            ((index % columns) * cell_width, (index // columns) * cell_height),
        )
    save_png_atomic(sheet, preview_path)


def normalized_path_key(path: Path) -> str:
    resolved = str(path.resolve(strict=False))
    return unicodedata.normalize("NFC", resolved).casefold()


def paths_collide(first: Path, second: Path) -> bool:
    if normalized_path_key(first) == normalized_path_key(second):
        return True
    try:
        return first.exists() and second.exists() and first.samefile(second)
    except OSError:
        return False


def file_paths_conflict(first: Path, second: Path) -> bool:
    """Treat equality, aliases, and file-as-parent layouts as collisions."""

    if paths_collide(first, second):
        return True
    first_resolved = first.resolve(strict=False)
    second_resolved = second.resolve(strict=False)
    return first_resolved in second_resolved.parents or second_resolved in first_resolved.parents


def validate_paths(
    input_path: Path, output_root: Path, filenames: list[str], preview: Path | None
) -> tuple[list[Path], Path | None]:
    input_resolved = input_path.resolve()
    output_resolved = output_root.resolve()
    targets = [(output_root / filename).resolve() for filename in filenames]
    preview_resolved = preview.resolve() if preview else None
    if paths_collide(input_resolved, output_resolved):
        raise ExtractGridError(
            "input sheet and output directory must use distinct paths", 2
        )
    if output_resolved.exists() and not output_resolved.is_dir():
        raise ExtractGridError("--output-dir must be a directory", 2)
    paths = [input_resolved, *targets]
    if preview_resolved:
        paths.append(preview_resolved)
    for index, first in enumerate(paths):
        for second in paths[index + 1 :]:
            if file_paths_conflict(first, second):
                raise ExtractGridError(
                    "input, output tiles, and preview must use distinct paths", 2
                )
    return targets, preview_resolved


def source_edge_record(
    index: int,
    components: list[dict[str, Any]],
    cell_width: int,
    cell_height: int,
    columns: int,
    warning_px: int,
) -> dict[str, Any] | None:
    """Describe pre-fit proximity to all four nominal cell boundaries."""

    row, column = divmod(index - 1, columns)
    cell_left = column * cell_width
    cell_top = row * cell_height
    cell_right = cell_left + cell_width
    cell_bottom = cell_top + cell_height
    source_left = min(item["bbox"][0] for item in components)
    source_top = min(item["bbox"][1] for item in components)
    source_right = max(item["bbox"][2] for item in components)
    source_bottom = max(item["bbox"][3] for item in components)
    margins = {
        "left": source_left - cell_left,
        "top": source_top - cell_top,
        "right": cell_right - source_right,
        "bottom": cell_bottom - source_bottom,
    }
    sides = [side for side, margin in margins.items() if margin <= warning_px]
    if not sides:
        return None
    return {
        "cell": index,
        "source_bbox": [source_left, source_top, source_right, source_bottom],
        "source_margins": [
            margins["left"],
            margins["top"],
            margins["right"],
            margins["bottom"],
        ],
        "sides": sides,
    }


def source_safe_margin_record(
    index: int,
    components: list[dict[str, Any]],
    cell_width: int,
    cell_height: int,
    columns: int,
    minimum_ratio: float,
) -> dict[str, Any] | None:
    """Report pre-fit content that violates the proportional cell safe area."""

    row, column = divmod(index - 1, columns)
    cell_left = column * cell_width
    cell_top = row * cell_height
    cell_right = cell_left + cell_width
    cell_bottom = cell_top + cell_height
    source_left = min(item["bbox"][0] for item in components)
    source_top = min(item["bbox"][1] for item in components)
    source_right = max(item["bbox"][2] for item in components)
    source_bottom = max(item["bbox"][3] for item in components)
    margins = [
        source_left - cell_left,
        source_top - cell_top,
        cell_right - source_right,
        cell_bottom - source_bottom,
    ]
    ratios = [
        margins[0] / cell_width,
        margins[1] / cell_height,
        margins[2] / cell_width,
        margins[3] / cell_height,
    ]
    sides = [
        side
        for side, ratio in zip(
            ("left", "top", "right", "bottom"), ratios, strict=True
        )
        if ratio < minimum_ratio
    ]
    if not sides:
        return None
    return {
        "cell": index,
        "minimum_ratio": minimum_ratio,
        "source_margins": margins,
        "source_margin_ratios": [round(value, 6) for value in ratios],
        "sides": sides,
    }


def extract_grid(args: argparse.Namespace) -> dict[str, Any]:
    count = args.rows * args.cols
    filenames = output_filenames(args.filenames, count)
    output_root = args.output_dir.resolve()
    output_paths, preview_path = validate_paths(
        args.input_sheet, output_root, filenames, args.preview
    )
    sheet = load_sheet(args.input_sheet)
    if sheet.width != sheet.height:
        raise ExtractGridError(
            f"input sheet must be square, got {sheet.width}x{sheet.height}", 3
        )
    sheet, padded = pad_to_divisible(sheet, args.rows, args.cols)
    width, height = sheet.size
    cell_width = width // args.cols
    cell_height = height // args.rows
    if cell_width != cell_height:
        raise ExtractGridError(
            f"grid cells must be square, got {cell_width}x{cell_height}", 3
        )
    if cell_width < args.min_cell_px:
        raise ExtractGridError(
            f"cell size {cell_width}x{cell_height} is below --min-cell-px {args.min_cell_px}",
            3,
        )

    transparent = transparentize_sheet(
        sheet, threshold=args.background_threshold, halo_px=args.halo_px
    )
    alpha_extrema = transparent.getchannel("A").getextrema()
    if alpha_extrema[0] > 0:
        raise ExtractGridError(
            "background is not removable; generate on pure neutral white or provide transparency",
            3,
        )
    if alpha_extrema[1] == 0:
        raise ExtractGridError("input sheet has no visible sticker content", 3)

    components = connected_components(
        transparent.getchannel("A"), min_area=args.min_component_area
    )
    if not components:
        raise ExtractGridError("input sheet has no extractable components", 3)
    touching_canvas = [
        component
        for component in components
        if component["bbox"][0] == 0
        or component["bbox"][1] == 0
        or component["bbox"][2] == width
        or component["bbox"][3] == height
    ]
    if touching_canvas:
        raise ExtractGridError(
            "sticker content touches the outer canvas edge; source may already be clipped",
            3,
        )

    grouped_components: list[list[dict[str, Any]]] = [[] for _ in range(count)]
    crossing_records: list[dict[str, Any]] = []
    ambiguous_records: list[dict[str, Any]] = []
    vertical_boundaries = [round(width * index / args.cols) for index in range(1, args.cols)]
    horizontal_boundaries = [round(height * index / args.rows) for index in range(1, args.rows)]
    for component in components:
        center_x, center_y = component["center"]
        column = min(args.cols - 1, int(center_x // cell_width))
        row = min(args.rows - 1, int(center_y // cell_height))
        owner = row * args.cols + column
        grouped_components[owner].append(component)
        crossings = component_crossings(
            component, width, height, args.rows, args.cols
        )
        if crossings["horizontal"] or crossings["vertical"]:
            crossing_records.append(
                {
                    "area": component["area"],
                    "bbox": list(component["bbox"]),
                    "horizontal": crossings["horizontal"],
                    "owner": owner + 1,
                    "vertical": crossings["vertical"],
                }
            )
        nearest_boundary = min(
            [abs(center_x - boundary) for boundary in vertical_boundaries]
            + [abs(center_y - boundary) for boundary in horizontal_boundaries]
            + [float("inf")]
        )
        if nearest_boundary <= args.boundary_warning_px:
            ambiguous_records.append(
                {
                    "area": component["area"],
                    "bbox": list(component["bbox"]),
                    "owner": owner + 1,
                }
            )

    minimum_anchor_area = max(
        args.min_component_area,
        round(cell_width * cell_height * DEFAULT_MIN_ANCHOR_AREA_RATIO),
    )
    for index, cell_components in enumerate(grouped_components, start=1):
        if not cell_components or max(item["area"] for item in cell_components) < minimum_anchor_area:
            raise ExtractGridError(
                f"cell {index} has no substantial sticker component", 3
            )
        for component in cell_components:
            left, top, right, bottom = component["bbox"]
            component_width = right - left
            component_height = bottom - top
            bbox_area = component_width * component_height
            fill_ratio = component["area"] / bbox_area
            if (
                fill_ratio >= DEFAULT_MAX_RECTANGULAR_FILL_RATIO
                and component_width >= cell_width * DEFAULT_MIN_PANEL_DIMENSION_RATIO
                and component_height >= cell_height * DEFAULT_MIN_PANEL_DIMENSION_RATIO
            ):
                raise ExtractGridError(
                    f"cell {index} contains a rectangular opaque panel instead of a sticker island",
                    3,
                )

    source_edge_records = [
        record
        for index, items in enumerate(grouped_components, start=1)
        if (
            record := source_edge_record(
                index,
                items,
                cell_width,
                cell_height,
                args.cols,
                args.boundary_warning_px,
            )
        )
        is not None
    ]
    source_safe_margin_records = [
        record
        for index, items in enumerate(grouped_components, start=1)
        if (
            record := source_safe_margin_record(
                index,
                items,
                cell_width,
                cell_height,
                args.cols,
                args.source_safe_margin_ratio,
            )
        )
        is not None
    ]
    possible_residue_records: list[dict[str, Any]] = []
    for index, items in enumerate(grouped_components, start=1):
        if len(items) < 2:
            continue
        anchor = max(items, key=lambda item: item["area"])
        row, column = divmod(index - 1, args.cols)
        cell_left = column * cell_width
        cell_top = row * cell_height
        cell_right = cell_left + cell_width
        cell_bottom = cell_top + cell_height
        for item in items:
            if item is anchor or item["area"] > anchor["area"] * DEFAULT_MAX_RESIDUE_AREA_RATIO:
                continue
            left, top, right, bottom = item["bbox"]
            side_margins = {
                "left": left - cell_left,
                "top": top - cell_top,
                "right": cell_right - right,
                "bottom": cell_bottom - bottom,
            }
            sides = [
                side
                for side, margin in side_margins.items()
                if margin <= args.boundary_warning_px
            ]
            if sides:
                possible_residue_records.append(
                    {
                        "area": item["area"],
                        "bbox": list(item["bbox"]),
                        "cell": index,
                        "sides": sides,
                    }
                )

    groups = [group_image(transparent, items) for items in grouped_components]
    final_images, scale = fit_groups_uniformly(
        groups, (cell_width, cell_height), args.padding_px
    )

    output_root.mkdir(parents=True, exist_ok=True)
    outputs: list[dict[str, Any]] = []
    for index, (target, final, cell_components) in enumerate(
        zip(output_paths, final_images, grouped_components, strict=True), start=1
    ):
        alpha = final.getchannel("A")
        if alpha.getextrema()[0] != 0 or alpha.getextrema()[1] == 0:
            raise ExtractGridError(
                f"cell {index} must contain transparent and visible pixels", 3
            )
        save_png_atomic(final, target)
        left, top, right, bottom = alpha.getbbox() or (0, 0, 0, 0)
        source_left = min(item["bbox"][0] for item in cell_components)
        source_top = min(item["bbox"][1] for item in cell_components)
        source_right = max(item["bbox"][2] for item in cell_components)
        source_bottom = max(item["bbox"][3] for item in cell_components)
        row, column = divmod(index - 1, args.cols)
        cell_left = column * cell_width
        cell_top = row * cell_height
        source_margins = [
            source_left - cell_left,
            source_top - cell_top,
            cell_left + cell_width - source_right,
            cell_top + cell_height - source_bottom,
        ]
        source_margin_ratios = [
            source_margins[0] / cell_width,
            source_margins[1] / cell_height,
            source_margins[2] / cell_width,
            source_margins[3] / cell_height,
        ]
        outputs.append(
            {
                "component_count": len(cell_components),
                "file": target.name,
                "index": index,
                "margins": [left, top, final.width - right, final.height - bottom],
                "source_bbox": [source_left, source_top, source_right, source_bottom],
                "source_margins": source_margins,
                "source_margin_ratios": [
                    round(value, 6) for value in source_margin_ratios
                ],
            }
        )

    if preview_path:
        build_preview(output_paths, args.rows, args.cols, preview_path)

    warnings: list[dict[str, Any]] = []
    if crossing_records:
        warnings.append(
            {
                "code": "source_components_cross_grid",
                "count": len(crossing_records),
                "details": crossing_records,
                "message": "full components crossed nominal grid lines and were assigned by centroid; inspect the transparent preview",
            }
        )
    if ambiguous_records:
        warnings.append(
            {
                "code": "component_owner_near_grid_line",
                "count": len(ambiguous_records),
                "details": ambiguous_records,
                "message": "component ownership is close to a grid line; inspect the transparent preview",
            }
        )
    if source_edge_records:
        warnings.append(
            {
                "code": "source_content_near_cell_edge",
                "count": len(source_edge_records),
                "details": source_edge_records,
                "message": "pre-fit source content touches or approaches a nominal cell edge; inspect for clipping even when centered output margins look safe",
            }
        )
    if source_safe_margin_records:
        warnings.append(
            {
                "code": "source_safe_margin_below_ratio",
                "count": len(source_safe_margin_records),
                "details": source_safe_margin_records,
                "message": "pre-fit source content violates the proportional cell safe area",
            }
        )
    multiple_component_records = [
        {
            "cell": index,
            "component_count": len(items),
            "components": [
                {"area": item["area"], "bbox": list(item["bbox"])} for item in items
            ],
        }
        for index, items in enumerate(grouped_components, start=1)
        if len(items) != 1
    ]
    if multiple_component_records:
        warnings.append(
            {
                "code": "multiple_components_in_cell",
                "count": len(multiple_component_records),
                "details": multiple_component_records,
                "message": "a cell contains disconnected components; inspect for detached captions, accents, or neighbor residue before delivery",
            }
        )
    if possible_residue_records:
        warnings.append(
            {
                "code": "possible_neighbor_residue",
                "count": len(possible_residue_records),
                "details": possible_residue_records,
                "message": "small detached components sit near a cell edge and may belong to a neighboring sticker",
            }
        )

    return {
        "cell_height": cell_height,
        "cell_width": cell_width,
        "columns": args.cols,
        "exit_code": 0,
        "input_sheet": str(args.input_sheet.resolve()),
        "ok": True,
        "output_dir": str(output_root),
        "outputs": outputs,
        "padded_to_divisible": padded,
        "preview": str(preview_path) if preview_path else None,
        "rows": args.rows,
        "source_safe_margin_ratio": args.source_safe_margin_ratio,
        "uniform_scale": round(scale, 6),
        "warnings": warnings,
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        result = extract_grid(args)
    except ExtractGridError as exc:
        print_json({"error": str(exc), "exit_code": exc.code, "ok": False})
        return exc.code
    except Exception as exc:  # pragma: no cover
        print_json(
            {
                "error": f"unexpected extract_grid failure: {exc}",
                "exit_code": 4,
                "ok": False,
            }
        )
        return 4
    print_json(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
