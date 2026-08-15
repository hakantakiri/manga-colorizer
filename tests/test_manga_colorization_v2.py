from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from PIL import Image

from manga_colorist.colorizers.manga_colorization_v2 import MangaColorizationV2Colorizer
from manga_colorist.models import ColorizationRequest


def make_v2_layout(tmp_path: Path) -> Path:
    repo = tmp_path / "manga-colorization-v2"
    (repo / "networks").mkdir(parents=True)
    (repo / "denoising" / "models").mkdir(parents=True)
    (repo / "inference.py").write_text("# fake inference\n", encoding="utf-8")
    (repo / "networks" / "generator.zip").write_bytes(b"fake")
    (repo / "networks" / "extractor.pth").write_bytes(b"fake")
    (repo / "denoising" / "models" / "net_rgb.pth").write_bytes(b"fake")
    return repo


def test_manga_colorization_v2_passes_model_size(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    repo = make_v2_layout(tmp_path)
    monkeypatch.setenv("MANGA_COLORIZATION_V2_PATH", str(repo))
    monkeypatch.setenv("MANGA_COLORIZATION_V2_PYTHON", "python")
    captured: dict[str, object] = {}

    def fake_run(command, cwd, env, capture_output, text, check):
        captured["command"] = command
        tmp_input = Path(command[command.index("-p") + 1])
        Image.new("RGB", (6, 6), "red").save(tmp_input.with_name(f"{tmp_input.stem}_colorized.png"))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr("manga_colorist.colorizers.manga_colorization_v2.subprocess.run", fake_run)
    colorizer = MangaColorizationV2Colorizer(device="cpu")
    request = ColorizationRequest(
        input_path=tmp_path / "page.png",
        output_path=tmp_path / "out.png",
        device="cpu",
        settings={"model_size": 1024},
    )

    colorizer.colorize(Image.new("RGB", (6, 6), "white"), request)

    command = captured["command"]
    assert command[command.index("-s") + 1] == "1024"
