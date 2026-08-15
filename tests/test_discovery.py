from __future__ import annotations

import json
from pathlib import Path

import yaml
from PIL import Image, ImageDraw
from typer.testing import CliRunner

from manga_colorist.cli import app
from manga_colorist.discovery import (
    clusters_to_character_bible,
    detect_character_candidates,
    discover_cast,
    export_reviewed_clusters,
)


def make_character_page(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGB", (220, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.ellipse((70, 30, 150, 110), outline="black", width=5)
    draw.rectangle((82, 112, 138, 190), outline="black", width=5)
    draw.line((95, 58, 105, 58), fill="black", width=4)
    draw.line((125, 58, 135, 58), fill="black", width=4)
    image.save(path)


def test_detect_character_candidates_finds_large_ink_region(tmp_path: Path) -> None:
    image_path = tmp_path / "page1.png"
    make_character_page(image_path)

    boxes = detect_character_candidates(Image.open(image_path), max_candidates=3, min_area_ratio=0.005)

    assert boxes
    xywh, confidence = boxes[0]
    assert xywh[2] > 40
    assert xywh[3] > 40
    assert confidence > 0


def test_discover_cast_writes_workspace_files(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "cast"
    make_character_page(input_dir / "page1.png")
    make_character_page(input_dir / "page2.png")

    result = discover_cast(input_dir, output_dir, min_area_ratio=0.005)

    assert result.detections
    assert (output_dir / "detections.json").exists()
    assert (output_dir / "clusters.yaml").exists()
    assert (output_dir / "characters.yaml").exists()
    assert (output_dir / "review.html").exists()
    detections = json.loads((output_dir / "detections.json").read_text(encoding="utf-8"))
    assert detections["detections"][0]["crop_path"].startswith("crops/")
    assert "<h1>Manga Cast Review</h1>" in (output_dir / "review.html").read_text(encoding="utf-8")


def test_clusters_to_character_bible_uses_only_approved_appearances() -> None:
    bible = clusters_to_character_bible(
        {
            "clusters": {
                "cluster_001": {
                    "name": "zoro",
                    "swatches": {"hair": "#8fb86a"},
                    "anchors": [{"part": "hair", "color": "hair", "relative_xy": [0.5, 0.2], "radius": 4}],
                    "appearances": [
                        {"id": "app_1", "page": "01.png", "xywh": [1, 2, 3, 4], "approved": True},
                        {"id": "app_2", "page": "02.png", "xywh": [5, 6, 7, 8], "approved": False},
                    ],
                }
            }
        }
    )

    assert list(bible["characters"]) == ["zoro"]
    assert list(bible["pages"]) == ["01.png"]
    assert bible["pages"]["01.png"]["characters"]["zoro"]["boxes"][0]["xywh"] == [1, 2, 3, 4]


def test_export_reviewed_clusters_writes_characters_yaml(tmp_path: Path) -> None:
    clusters_path = tmp_path / "clusters.yaml"
    output_path = tmp_path / "characters.yaml"
    clusters_path.write_text(
        yaml.safe_dump(
            {
                "clusters": {
                    "cluster_001": {
                        "name": "zoro",
                        "swatches": {"hair": "#8fb86a"},
                        "anchors": [{"part": "hair", "color": "hair", "relative_xy": [0.5, 0.2], "radius": 4}],
                        "appearances": [{"id": "app_1", "page": "01.png", "xywh": [1, 2, 3, 4], "approved": True}],
                    }
                }
            }
        ),
        encoding="utf-8",
    )

    export_reviewed_clusters(clusters_path, output_path)

    payload = yaml.safe_load(output_path.read_text(encoding="utf-8"))
    assert payload["pages"]["01.png"]["characters"]["zoro"]["boxes"][0]["xywh"] == [1, 2, 3, 4]


def test_discover_cast_cli_command(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "cast"
    make_character_page(input_dir / "page1.png")

    result = CliRunner().invoke(
        app,
        [
            "discover-cast",
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--min-area-ratio",
            "0.005",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "detections" in result.output
    assert (output_dir / "review.html").exists()


def test_export_cast_cli_command(tmp_path: Path) -> None:
    clusters_path = tmp_path / "clusters.yaml"
    output_path = tmp_path / "characters.yaml"
    clusters_path.write_text(
        """
clusters:
  cluster_001:
    name: zoro
    swatches:
      hair: "#8fb86a"
    anchors:
      - part: hair
        color: hair
        relative_xy: [0.5, 0.2]
        radius: 4
    appearances:
      - id: app_1
        page: "01.png"
        xywh: [1, 2, 3, 4]
        approved: true
""".strip(),
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        app,
        ["export-cast", "--clusters", str(clusters_path), "--output", str(output_path)],
    )

    assert result.exit_code == 0, result.output
    assert "1 characters" in result.output
    assert output_path.exists()
