from __future__ import annotations

from pathlib import Path

from PIL import Image

from manga_colorist.colorizers.simple import SimpleAutoColorizer
from manga_colorist.models import ColorizationRequest


def test_simple_colorizer_returns_rgb_image_with_same_size(tmp_path: Path) -> None:
    image = Image.new("L", (8, 6), 220)
    request = ColorizationRequest(
        input_path=tmp_path / "in.png",
        output_path=tmp_path / "out.png",
        device="cpu",
    )

    result = SimpleAutoColorizer().colorize(image, request)

    assert result.mode == "RGB"
    assert result.size == (8, 6)

