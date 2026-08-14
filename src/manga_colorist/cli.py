from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Annotated

import typer

from manga_colorist.colorizers.factory import create_colorizer
from manga_colorist.device import DeviceSelectionError, select_device
from manga_colorist.pipeline import colorize_folder

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
    reference_dir: Annotated[Path | None, typer.Option("--reference-dir", help="Reserved for future reference-guided coloring.")] = None,
    palette: Annotated[Path | None, typer.Option("--palette", help="Reserved for future manual palette coloring.")] = None,
) -> None:
    if reference_dir is not None:
        raise typer.BadParameter("--reference-dir is reserved for a future reference-guided mode and is not implemented in v1.")
    if palette is not None:
        raise typer.BadParameter("--palette is reserved for a future manual-palette mode and is not implemented in v1.")

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


if __name__ == "__main__":
    app()
