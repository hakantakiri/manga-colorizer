from __future__ import annotations

from PIL import Image

from manga_colorist.postprocess import preserve_resolution_color


def test_preserve_resolution_color_returns_original_size() -> None:
    original = Image.new("RGB", (100, 80), "white")
    colorized = Image.new("RGB", (50, 40), "red")

    result = preserve_resolution_color(original, colorized)

    assert result.size == original.size


def test_preserve_resolution_color_keeps_dark_ink_neutral() -> None:
    original = Image.new("RGB", (2, 1), "white")
    original.putpixel((0, 0), (0, 0, 0))
    colorized = Image.new("RGB", (2, 1), "red")

    result = preserve_resolution_color(original, colorized)

    ink_pixel = result.getpixel((0, 0))
    assert max(ink_pixel) <= 5
    assert max(ink_pixel) - min(ink_pixel) <= 2


def test_preserve_resolution_color_keeps_model_chroma_on_midtones() -> None:
    original = Image.new("RGB", (1, 1), (128, 128, 128))
    colorized = Image.new("RGB", (1, 1), "blue")

    result = preserve_resolution_color(original, colorized)

    pixel = result.getpixel((0, 0))
    assert max(pixel) - min(pixel) > 40
