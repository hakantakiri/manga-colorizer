from __future__ import annotations

import time
from pathlib import Path

from manga_colorist.colorizers.base import BaseColorizer
from manga_colorist.io import discover_images, load_normalized_rgb, output_path_for
from manga_colorist.models import ColorizationRequest, ColorizationResult
from manga_colorist.postprocess import preserve_resolution_color
from manga_colorist.report import RunReport


def colorize_folder(
    input_dir: Path,
    output_dir: Path,
    colorizer: BaseColorizer,
    device: str,
    overwrite: bool = False,
    settings: dict | None = None,
) -> RunReport:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    settings = settings or {}
    images = discover_images(input_dir)
    report = RunReport.start(settings=settings, model_metadata=colorizer.metadata() | {"device": device})

    for input_path in images:
        output_path = output_path_for(input_path, input_dir, output_dir)
        start = time.perf_counter()

        if output_path.exists() and not overwrite:
            report.results.append(
                ColorizationResult(
                    input_path=input_path,
                    output_path=output_path,
                    status="skipped",
                    elapsed_seconds=0.0,
                    warnings=["Output already exists; pass --overwrite to regenerate."],
                    model_metadata=report.model_metadata,
                )
            )
            continue

        request = ColorizationRequest(
            input_path=input_path,
            output_path=output_path,
            device=device,
            settings=settings,
        )
        details: dict = {}

        try:
            image = load_normalized_rgb(input_path)
            preserve_resolution = bool(settings.get("preserve_resolution", True))
            details = {
                "original_size": list(image.size),
                "preserve_resolution": preserve_resolution,
                "model_size": settings.get("model_size", 576),
            }
            model_output = colorizer.colorize(image, request).convert("RGB")
            details["model_output_size"] = list(model_output.size)
            colorized = preserve_resolution_color(image, model_output) if preserve_resolution else model_output
            details["final_size"] = list(colorized.size)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            colorized.save(output_path)
            status = "success"
            error = None
            warnings: list[str] = []
        except Exception as exc:
            status = "failed"
            error = str(exc)
            warnings = []

        report.results.append(
            ColorizationResult(
                input_path=input_path,
                output_path=output_path,
                status=status,
                elapsed_seconds=round(time.perf_counter() - start, 4),
                warnings=warnings,
                error=error,
                model_metadata=report.model_metadata,
                details=details,
            )
        )

    report.finish()
    report.write(output_dir / "run-report.json")
    return report
