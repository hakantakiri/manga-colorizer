from __future__ import annotations

import numpy as np
from PIL import Image


def preserve_resolution_color(
    original: Image.Image,
    colorized: Image.Image,
    *,
    ink_threshold: int = 40,
    paper_threshold: int = 244,
    paper_chroma_strength: float = 0.35,
) -> Image.Image:
    """Transfer model chroma onto the original high-resolution luminance."""
    original_rgb = original.convert("RGB")
    color_rgb = colorized.convert("RGB")
    if color_rgb.size != original_rgb.size:
        color_rgb = color_rgb.resize(original_rgb.size, Image.Resampling.LANCZOS)

    original_y, _, _ = original_rgb.convert("YCbCr").split()
    _, color_cb, color_cr = color_rgb.convert("YCbCr").split()

    y_array = np.asarray(original_y, dtype=np.uint8)
    cb_array = np.asarray(color_cb, dtype=np.float32)
    cr_array = np.asarray(color_cr, dtype=np.float32)

    dark_mask = y_array <= ink_threshold
    cb_array[dark_mask] = 128.0
    cr_array[dark_mask] = 128.0

    paper_mask = y_array >= paper_threshold
    if paper_mask.any():
        paper_weight = ((y_array.astype(np.float32) - paper_threshold) / (255 - paper_threshold)).clip(0.0, 1.0)
        paper_weight *= 1.0 - paper_chroma_strength
        cb_array[paper_mask] = cb_array[paper_mask] * (1.0 - paper_weight[paper_mask]) + 128.0 * paper_weight[paper_mask]
        cr_array[paper_mask] = cr_array[paper_mask] * (1.0 - paper_weight[paper_mask]) + 128.0 * paper_weight[paper_mask]

    cb_image = Image.fromarray(np.clip(cb_array, 0, 255).astype(np.uint8))
    cr_image = Image.fromarray(np.clip(cr_array, 0, 255).astype(np.uint8))
    return Image.merge("YCbCr", (original_y, cb_image, cr_image)).convert("RGB")
