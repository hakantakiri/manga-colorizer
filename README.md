# Manga Auto Colorist

Local-first CLI for coloring folders of manga page images.

## Install

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev,ml]"
```

`torch` is optional for the explicit `debug-tint` adapter, but required for real model adapters and device detection.

## Usage

```bash
manga-colorist colorize --input ./pages --output ./colored --device auto
```

The command writes colorized RGB images to the output folder and a `run-report.json` with settings, timings, skipped pages, failures, and model metadata.

V1 uses `manga-colorization-v2` by default. Set up a local checkout and weights first:

```bash
export MANGA_COLORIZATION_V2_PATH=/path/to/manga-colorization-v2
export MANGA_COLORIZATION_V2_PYTHON=/path/to/manga-colorization-v2/venv/bin/python
manga-colorist colorize --input ./pages --output ./colored --model manga-colorization-v2
```

This workspace is already configured with an ignored local checkout under `.external/`, so you can run:

```bash
MANGA_COLORIZATION_V2_PATH="$PWD/.external/manga-colorization-v2" MANGA_COLORIZATION_V2_PYTHON="$PWD/.external/manga-colorization-v2/.venv/bin/python" PYTHONPATH=src .venv/bin/manga-colorist colorize --input ./pages --output ./colored --device cpu --overwrite
```

The checkout must contain `inference.py`, `networks/generator.zip`, `networks/extractor.pth`, and `denoising/models/net_rgb.pth`.

For pipeline tests only, there is an explicit debug adapter:

```bash
manga-colorist colorize --input ./pages --output ./colored --model debug-tint
```

`debug-tint` is not real manga colorization.

## Reserved Future Controls

`--reference-dir` and `--palette` are reserved for future reference-guided and manual-palette workflows. Passing either option in v1 exits with a clear message.
