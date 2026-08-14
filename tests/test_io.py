from __future__ import annotations

from pathlib import Path

from PIL import Image

from manga_colorist.io import discover_images, output_path_for


def test_discover_images_uses_natural_sort_and_supported_extensions(tmp_path: Path) -> None:
    for name in ["page10.png", "page2.jpg", "notes.txt", "page1.webp"]:
        path = tmp_path / name
        if path.suffix == ".txt":
            path.write_text("ignore", encoding="utf-8")
        else:
            Image.new("RGB", (2, 2), "white").save(path)

    assert [path.name for path in discover_images(tmp_path)] == ["page1.webp", "page2.jpg", "page10.png"]


def test_output_path_mirrors_relative_structure_as_png(tmp_path: Path) -> None:
    input_root = tmp_path / "input"
    output_root = tmp_path / "output"
    input_path = input_root / "chapter-1" / "page01.jpg"

    assert output_path_for(input_path, input_root, output_root) == output_root / "chapter-1" / "page01.png"

