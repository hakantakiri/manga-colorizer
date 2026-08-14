from __future__ import annotations

import math
from typing import Any

import cv2
import numpy as np
from PIL import Image

from manga_colorist.colorizers.base import BaseColorizer
from manga_colorist.models import ColorizationRequest


class SimpleAutoColorizer(BaseColorizer):
    """Deterministic debug tint that exercises the pipeline without model weights."""

    name = "debug-tint"

    def colorize(self, image: Image.Image, request: ColorizationRequest) -> Image.Image:
        rgb = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
        height, width = gray.shape

        x = np.linspace(0.0, 1.0, width, dtype=np.float32)
        y = np.linspace(0.0, 1.0, height, dtype=np.float32)
        xx, yy = np.meshgrid(x, y)

        hue = ((xx * 42.0 + yy * 18.0 + math.sin(width + height) * 8.0) % 180).astype(np.uint8)
        saturation = np.full_like(hue, 72, dtype=np.uint8)
        value = np.clip(gray.astype(np.float32) * 1.04, 0, 255).astype(np.uint8)
        hsv = cv2.merge([hue, saturation, value])
        color = cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

        line_mask = gray < 72
        paper_mask = gray > 244
        color[line_mask] = rgb[line_mask]
        color[paper_mask] = np.clip(color[paper_mask] * 0.78 + rgb[paper_mask] * 0.22, 0, 255)

        return Image.fromarray(color.astype(np.uint8))

    def metadata(self) -> dict[str, Any]:
        return {
            "model": self.name,
            "type": "debug-only-tint",
            "notes": "Not real manga colorization. Use manga-colorization-v2 for neural colorization.",
        }
