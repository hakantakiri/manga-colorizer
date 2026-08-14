from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageOps

SUPPORTED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".tif", ".tiff"}


def natural_key(path: Path) -> list[int | str]:
    parts = re.split(r"(\d+)", path.as_posix().lower())
    return [int(part) if part.isdigit() else part for part in parts]


def discover_images(input_dir: Path) -> list[Path]:
    if not input_dir.exists():
        raise FileNotFoundError(f"Input folder does not exist: {input_dir}")
    if not input_dir.is_dir():
        raise NotADirectoryError(f"Input path is not a folder: {input_dir}")
    return sorted(
        (
            path
            for path in input_dir.rglob("*")
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
        ),
        key=natural_key,
    )


def output_path_for(input_path: Path, input_root: Path, output_root: Path) -> Path:
    relative = input_path.relative_to(input_root)
    return output_root / relative.with_suffix(".png")


def load_normalized_rgb(path: Path) -> Image.Image:
    with Image.open(path) as image:
        normalized = ImageOps.exif_transpose(image)
        return normalized.convert("RGB")

