from __future__ import annotations

import time
from pathlib import Path

from manga_colorist.colorizers.base import BaseColorizer
from manga_colorist.io import discover_images, load_normalized_rgb, output_path_for
from manga_colorist.models import ColorizationRequest, ColorizationResult
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

        try:
            image = load_normalized_rgb(input_path)
            colorized = colorizer.colorize(image, request).convert("RGB")
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
            )
        )

    report.finish()
    report.write(output_dir / "run-report.json")
    return report

