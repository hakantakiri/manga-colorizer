from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from manga_colorist.colorizers.factory import create_colorizer
from manga_colorist.device import DeviceSelectionError, select_device
from manga_colorist.discovery import discover_cast, export_reviewed_clusters
from manga_colorist.pipeline import colorize_folder
from manga_colorist.review_server import serve_review

app = typer.Typer(no_args_is_help=True, help="Batch colorize manga page images.")


class DeviceOption(str, Enum):
    auto = "auto"
    mps = "mps"
    cuda = "cuda"
    cpu = "cpu"


class ModelOption(str, Enum):
    debug_tint = "debug-tint"
    manga_colorization_v2 = "manga-colorization-v2"


@app.callback()
def main() -> None:
    """Batch colorize manga page images."""


@app.command()
def colorize(
    input: Annotated[Path, typer.Option("--input", "-i", exists=True, file_okay=False, help="Folder of manga page images.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Folder where colored pages and report are written.")],
    device: Annotated[DeviceOption, typer.Option("--device", help="Compute device.")] = DeviceOption.auto,
    model: Annotated[ModelOption, typer.Option("--model", help="Colorizer adapter to use.")] = ModelOption.manga_colorization_v2,
    overwrite: Annotated[bool, typer.Option("--overwrite", help="Regenerate pages even when outputs already exist.")] = False,
    preserve_resolution: Annotated[
        bool,
        typer.Option(
            "--preserve-resolution/--no-preserve-resolution",
            help="Preserve original page dimensions and high-resolution line art.",
        ),
    ] = True,
    model_size: Annotated[int, typer.Option("--model-size", help="Inference size for manga-colorization-v2; must be divisible by 32.")] = 576,
    reference_dir: Annotated[Path | None, typer.Option("--reference-dir", help="Reserved for future reference-guided coloring.")] = None,
    palette: Annotated[Path | None, typer.Option("--palette", help="Reserved for future manual palette coloring.")] = None,
) -> None:
    if reference_dir is not None:
        raise typer.BadParameter("--reference-dir is reserved for a future reference-guided mode and is not implemented in v1.")
    if palette is not None:
        raise typer.BadParameter("--palette is reserved for a future manual-palette mode and is not implemented in v1.")
    if model_size <= 0 or model_size % 32 != 0:
        raise typer.BadParameter("--model-size must be a positive integer divisible by 32.")

    try:
        selected_device = select_device(device.value)
        colorizer = create_colorizer(model=model.value, device=selected_device)
    except (DeviceSelectionError, RuntimeError, ValueError) as exc:
        typer.echo(f"Setup error: {exc}", err=True)
        raise typer.Exit(code=2) from exc

    settings = {
        "input": str(input.resolve()),
        "output": str(output.resolve()),
        "requested_device": device.value,
        "selected_device": selected_device,
        "model": model.value,
        "overwrite": overwrite,
        "preserve_resolution": preserve_resolution,
        "model_size": model_size,
    }
    report = colorize_folder(
        input_dir=input,
        output_dir=output,
        colorizer=colorizer,
        device=selected_device,
        overwrite=overwrite,
        settings=settings,
    )
    typer.echo(
        "Done: "
        f"{report.totals.get('success', 0)} colored, "
        f"{report.totals.get('skipped', 0)} skipped, "
        f"{report.totals.get('failed', 0)} failed. "
        f"Report: {output.resolve() / 'run-report.json'}"
    )


@app.command("discover-cast")
def discover_cast_command(
    input: Annotated[Path, typer.Option("--input", "-i", exists=True, file_okay=False, help="Folder of manga page images.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="Workspace folder for detections, crops, clusters, and review HTML.")],
    max_candidates_per_page: Annotated[int, typer.Option("--max-candidates-per-page", help="Maximum proposed regions per page.")] = 8,
    min_area_ratio: Annotated[float, typer.Option("--min-area-ratio", help="Minimum candidate area as a fraction of the page.")] = 0.015,
    max_area_ratio: Annotated[float, typer.Option("--max-area-ratio", help="Maximum candidate area as a fraction of the page.")] = 0.45,
    cluster_threshold: Annotated[float, typer.Option("--cluster-threshold", help="Cosine similarity threshold for grouping crops.")] = 0.88,
) -> None:
    result = discover_cast(
        input_dir=input,
        output_dir=output,
        max_candidates_per_page=max_candidates_per_page,
        min_area_ratio=min_area_ratio,
        max_area_ratio=max_area_ratio,
        cluster_threshold=cluster_threshold,
    )
    typer.echo(
        "Done: "
        f"{len(result.detections)} detections, "
        f"{len(result.clusters)} clusters. "
        f"Review: {output.resolve() / 'review.html'}"
    )


@app.command("export-cast")
def export_cast_command(
    clusters: Annotated[Path, typer.Option("--clusters", exists=True, dir_okay=False, help="Reviewed clusters.yaml file.")],
    output: Annotated[Path, typer.Option("--output", "-o", help="characters.yaml path to write.")],
) -> None:
    character_bible = export_reviewed_clusters(clusters, output)
    typer.echo(
        "Done: "
        f"{len(character_bible.get('characters', {}))} characters, "
        f"{len(character_bible.get('pages', {}))} pages. "
        f"Wrote: {output.resolve()}"
    )


@app.command("review-cast")
def review_cast_command(
    workspace: Annotated[Path, typer.Option("--workspace", "-w", exists=True, file_okay=False, help="Cast workspace created by discover-cast.")],
    host: Annotated[str, typer.Option("--host", help="Host address for the local review server.")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port", help="Port for the local review server.")] = 8765,
) -> None:
    serve_review(workspace=workspace, host=host, port=port)


if __name__ == "__main__":
    app()
