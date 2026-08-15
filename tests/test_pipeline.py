from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from PIL import Image, ImageOps

from manga_colorist.colorizers.base import BaseColorizer
from manga_colorist.models import ColorizationRequest
from manga_colorist.pipeline import colorize_folder


class FakeColorizer(BaseColorizer):
    name = "fake"

    def colorize(self, image: Image.Image, request: ColorizationRequest) -> Image.Image:
        return ImageOps.colorize(image.convert("L"), black="#111111", white="#ffeeaa").convert("RGB")

    def metadata(self) -> dict[str, Any]:
        return {"model": self.name}


class LowResColorizer(BaseColorizer):
    name = "low-res"

    def colorize(self, image: Image.Image, request: ColorizationRequest) -> Image.Image:
        return Image.new("RGB", (50, 40), "red")

    def metadata(self) -> dict[str, Any]:
        return {"model": self.name}


def make_image(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("L", (4, 4), 230).save(path)


def test_colorize_folder_writes_outputs_and_report(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    make_image(input_dir / "page1.png")
    make_image(input_dir / "nested" / "page2.jpg")

    report = colorize_folder(input_dir, output_dir, FakeColorizer(), device="cpu", settings={"model": "fake"})

    assert report.totals == {"success": 2, "skipped": 0, "failed": 0, "total": 2}
    assert (output_dir / "page1.png").exists()
    assert (output_dir / "nested" / "page2.png").exists()

    payload = json.loads((output_dir / "run-report.json").read_text(encoding="utf-8"))
    assert payload["settings"]["model"] == "fake"
    assert payload["totals"]["success"] == 2
    assert payload["results"][0]["status"] == "success"


def test_colorize_folder_skips_existing_outputs_without_overwrite(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    make_image(input_dir / "page1.png")
    make_image(output_dir / "page1.png")

    report = colorize_folder(input_dir, output_dir, FakeColorizer(), device="cpu", overwrite=False)

    assert report.totals == {"success": 0, "skipped": 1, "failed": 0, "total": 1}
    assert report.results[0].status == "skipped"


def test_colorize_folder_records_invalid_image_failure(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    input_dir.mkdir()
    (input_dir / "broken.png").write_text("not really an image", encoding="utf-8")

    report = colorize_folder(input_dir, output_dir, FakeColorizer(), device="cpu")

    assert report.totals == {"success": 0, "skipped": 0, "failed": 1, "total": 1}
    assert report.results[0].error


def test_colorize_folder_preserves_original_resolution_by_default(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    input_dir.mkdir()
    Image.new("RGB", (100, 80), "white").save(input_dir / "page1.png")

    report = colorize_folder(input_dir, output_dir, LowResColorizer(), device="cpu")

    with Image.open(output_dir / "page1.png") as output:
        assert output.size == (100, 80)
    assert report.results[0].details["original_size"] == [100, 80]
    assert report.results[0].details["model_output_size"] == [50, 40]
    assert report.results[0].details["final_size"] == [100, 80]
    assert report.results[0].details["preserve_resolution"] is True


def test_colorize_folder_can_keep_legacy_low_resolution_output(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    input_dir.mkdir()
    Image.new("RGB", (100, 80), "white").save(input_dir / "page1.png")

    report = colorize_folder(
        input_dir,
        output_dir,
        LowResColorizer(),
        device="cpu",
        settings={"preserve_resolution": False, "model_size": 576},
    )

    with Image.open(output_dir / "page1.png") as output:
        assert output.size == (50, 40)
    assert report.results[0].details["final_size"] == [50, 40]
    assert report.results[0].details["preserve_resolution"] is False
