# Copyright (c) 2026 Mr.Koi. All rights reserved.
# Personal and non-commercial use only; commercial use requires written authorization.
# See ../LICENSE.
"""Supported visual presets for the pet sticker skill."""

from __future__ import annotations

from typing import Any


DEFAULT_STYLE_ID = "q-cute-handdrawn"

STYLE_PRESETS: dict[str, dict[str, Any]] = {
    "q-cute-handdrawn": {
        "display_name": "Q萌手绘贴纸",
        "composition_profile": "balanced",
        "default_text_policy": "mixed",
    },
    "flat-emoji": {
        "display_name": "极简扁平 Emoji",
        "composition_profile": "face-first",
        "default_text_policy": "none",
    },
    "bold-comic": {
        "display_name": "粗线漫画大字",
        "composition_profile": "action-first",
        "default_text_policy": "all",
    },
    "crayon-journal": {
        "display_name": "蜡笔手帐涂鸦",
        "composition_profile": "balanced",
        "default_text_policy": "mixed",
    },
    "naive-ink-watercolor": {
        "display_name": "稚拙墨线水彩",
        "composition_profile": "face-first",
        "default_text_policy": "sparse",
    },
    "bold-ink-caricature": {
        "display_name": "粗墨怪萌水彩",
        "composition_profile": "face-first",
        "default_text_policy": "sparse-or-none",
    },
}


def get_style_preset(style_id: str) -> dict[str, Any]:
    """Return a supported preset or raise KeyError for an unknown stable ID."""

    return STYLE_PRESETS[style_id]
