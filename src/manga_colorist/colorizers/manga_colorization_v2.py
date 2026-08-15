from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image

from manga_colorist.colorizers.base import BaseColorizer
from manga_colorist.models import ColorizationRequest


class MangaColorizationV2SetupError(RuntimeError):
    pass


class MangaColorizationV2Colorizer(BaseColorizer):
    name = "manga-colorization-v2"

    def __init__(self, device: str) -> None:
        self.device = device
        configured_path = os.environ.get("MANGA_COLORIZATION_V2_PATH", "").strip()
        self.repo_path = Path(configured_path).expanduser()
        self.python = os.environ.get("MANGA_COLORIZATION_V2_PYTHON", sys.executable)
        if not configured_path:
            raise MangaColorizationV2SetupError(
                "MANGA_COLORIZATION_V2_PATH is not set. Clone qweasdd/manga-colorization-v2, "
                "download its weights, then set MANGA_COLORIZATION_V2_PATH to that checkout."
            )
        if not self.repo_path.exists():
            raise MangaColorizationV2SetupError(f"Configured manga-colorization-v2 path does not exist: {self.repo_path}")
        if not (self.repo_path / "inference.py").exists():
            raise MangaColorizationV2SetupError(f"inference.py was not found in: {self.repo_path}")
        self._check_weight("networks/generator.zip")
        self._check_weight("networks/extractor.pth")
        self._check_weight("denoising/models/net_rgb.pth")
        if self.device == "mps":
            raise MangaColorizationV2SetupError(
                "manga-colorization-v2 is CUDA/CPU-oriented and is not enabled for MPS in this adapter. "
                "Use --device cpu, use --device cuda on a CUDA machine, or explicitly use --model debug-tint for pipeline tests."
            )

    def _check_weight(self, relative_path: str) -> None:
        if not (self.repo_path / relative_path).exists():
            raise MangaColorizationV2SetupError(
                f"Missing manga-colorization-v2 weight: {relative_path}. "
                "Download the generator/extractor weights and place them in the checkout as documented upstream."
            )

    def colorize(self, image: Image.Image, request: ColorizationRequest) -> Image.Image:
        with tempfile.TemporaryDirectory(prefix="manga-colorist-") as tmp:
            tmp_dir = Path(tmp)
            tmp_input = tmp_dir / request.input_path.name
            image.save(tmp_input)

            model_size = int(request.settings.get("model_size", 576))
            if model_size % 32 != 0:
                raise MangaColorizationV2SetupError("--model-size must be divisible by 32.")

            command = [self.python, "inference.py", "-p", str(tmp_input), "-s", str(model_size)]
            if self.device == "cuda":
                command.append("-g")

            env = os.environ.copy()
            env.setdefault("MPLCONFIGDIR", str(tmp_dir / "matplotlib"))
            completed = subprocess.run(
                command,
                cwd=self.repo_path,
                env=env,
                capture_output=True,
                text=True,
                check=False,
            )
            if completed.returncode != 0:
                raise MangaColorizationV2SetupError(
                    "manga-colorization-v2 inference failed.\n"
                    f"stdout:\n{completed.stdout}\n"
                    f"stderr:\n{completed.stderr}"
                )

            candidate = tmp_input.with_name(f"{tmp_input.stem}_colorized.png")
            if not candidate.exists():
                nested = tmp_dir / "colorization" / f"{tmp_input.stem}.png"
                candidate = nested if nested.exists() else candidate
            if not candidate.exists():
                raise MangaColorizationV2SetupError(
                    "manga-colorization-v2 completed but no colorized output was found."
                )

            stable_output = tmp_dir / "result.png"
            shutil.copyfile(candidate, stable_output)
            with Image.open(stable_output) as output:
                return output.convert("RGB")

    def metadata(self) -> dict[str, Any]:
        return {
            "model": self.name,
            "device": self.device,
            "repo_path": str(self.repo_path),
            "python": self.python,
        }
