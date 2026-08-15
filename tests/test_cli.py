from __future__ import annotations

from pathlib import Path

from PIL import Image
from typer.testing import CliRunner

from manga_colorist.cli import app


def test_cli_colorize_command_generates_and_then_skips(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    input_dir.mkdir()
    Image.new("L", (8, 8), 240).save(input_dir / "page1.png")

    runner = CliRunner()

    first = runner.invoke(
        app,
        [
            "colorize",
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--device",
            "cpu",
            "--model",
            "debug-tint",
        ],
    )
    assert first.exit_code == 0, first.output
    assert "1 colored, 0 skipped, 0 failed" in first.output
    assert (output_dir / "page1.png").exists()

    second = runner.invoke(
        app,
        [
            "colorize",
            "--input",
            str(input_dir),
            "--output",
            str(output_dir),
            "--device",
            "cpu",
            "--model",
            "debug-tint",
        ],
    )
    assert second.exit_code == 0, second.output
    assert "0 colored, 1 skipped, 0 failed" in second.output


def test_cli_default_model_requires_real_model_setup(tmp_path: Path) -> None:
    input_dir = tmp_path / "pages"
    output_dir = tmp_path / "colored"
    input_dir.mkdir()
    Image.new("L", (8, 8), 240).save(input_dir / "page1.png")

    runner = CliRunner()
    result = runner.invoke(
        app,
        ["colorize", "--input", str(input_dir), "--output", str(output_dir), "--device", "cpu"],
        env={"MANGA_COLORIZATION_V2_PATH": ""},
    )

    assert result.exit_code == 2
    assert "MANGA_COLORIZATION_V2_PATH is not set" in result.output


def test_cli_includes_cast_review_commands() -> None:
    result = CliRunner().invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "discover-cast" in result.output
    assert "review-cast" in result.output
    assert "export-cast" in result.output
