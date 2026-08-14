from __future__ import annotations

from manga_colorist.colorizers.base import BaseColorizer
from manga_colorist.colorizers.manga_colorization_v2 import MangaColorizationV2Colorizer
from manga_colorist.colorizers.simple import SimpleAutoColorizer


def create_colorizer(model: str, device: str) -> BaseColorizer:
    if model == "debug-tint":
        return SimpleAutoColorizer()
    if model == "manga-colorization-v2":
        return MangaColorizationV2Colorizer(device=device)
    raise ValueError(f"Unknown model: {model}")
