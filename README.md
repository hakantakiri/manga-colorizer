# Manga Auto Colorist

Local-first CLI for coloring folders of manga page images.

The default backend is [`manga-colorization-v2`](https://github.com/qweasdd/manga-colorization-v2). This repo wraps that model with batch processing, reports, resumable output, and high-resolution recomposition so the final pages keep the original dimensions and sharper line art.

## Quick Colorize Command

After completing the fresh clone setup below, this is the main command to run. Replace `./pages` with your input image folder and `./colored` with your desired output folder.

```bash
MANGA_COLORIZATION_V2_PATH="$PWD/.external/manga-colorization-v2" MANGA_COLORIZATION_V2_PYTHON="$PWD/.external/manga-colorization-v2/.venv/bin/python" PYTHONPATH=src .venv/bin/manga-colorist colorize --input ./pages --output ./colored --device cpu --overwrite --preserve-resolution
```

The command writes colorized RGB images to the output folder and a `run-report.json` with settings, timings, skipped pages, failures, and model metadata.

## Fresh Clone Setup

This project uses two Python environments:

- The project venv runs the `manga-colorist` CLI.
- The external model venv runs `manga-colorization-v2/inference.py`.

### 1. Install The CLI

From the root of this repo, using Python 3.10 or newer:

```bash
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -e ".[dev]"
```

The root project does not need PyTorch for the validated CPU command above. If you want local PyTorch device probing or future ML adapters in this wrapper, install the optional ML extra instead:

```bash
.venv/bin/pip install -e ".[dev,ml]"
```

### 2. Install The External Colorizer

The external checkout is intentionally kept under ignored `.external/` so third-party code and large weights are not committed into this repo.

```bash
mkdir -p .external
git clone https://github.com/qweasdd/manga-colorization-v2 .external/manga-colorization-v2
python3 -m venv .external/manga-colorization-v2/.venv
.external/manga-colorization-v2/.venv/bin/pip install --upgrade pip
.external/manga-colorization-v2/.venv/bin/pip install -r .external/manga-colorization-v2/requirements.txt
```

`manga-colorization-v2` owns its own dependencies, including `torch`, `torchvision`, `opencv-python`, and `matplotlib`.

### 3. Download Model Weights

Follow the weight links in the upstream [`manga-colorization-v2` README](https://github.com/qweasdd/manga-colorization-v2). The upstream notes refer to generator/extractor weights and denoiser weights. This wrapper expects these files to exist:

```text
.external/manga-colorization-v2/networks/generator.zip
.external/manga-colorization-v2/networks/extractor.pth
.external/manga-colorization-v2/denoising/models/net_rgb.pth
```

Verify the setup before running colorization:

```bash
test -f .external/manga-colorization-v2/inference.py
test -f .external/manga-colorization-v2/networks/generator.zip
test -f .external/manga-colorization-v2/networks/extractor.pth
test -f .external/manga-colorization-v2/denoising/models/net_rgb.pth
```

You can export the model paths once per terminal session:

```bash
export MANGA_COLORIZATION_V2_PATH="$PWD/.external/manga-colorization-v2"
export MANGA_COLORIZATION_V2_PYTHON="$PWD/.external/manga-colorization-v2/.venv/bin/python"
```

Then the shorter command is:

```bash
PYTHONPATH=src .venv/bin/manga-colorist colorize --input ./pages --output ./colored --device cpu --overwrite --preserve-resolution
```

## Usage

Basic colorization after exporting `MANGA_COLORIZATION_V2_PATH` and `MANGA_COLORIZATION_V2_PYTHON`:

```bash
PYTHONPATH=src .venv/bin/manga-colorist colorize --input ./pages --output ./colored --device cpu
```

Supported input image extensions:

```text
.png .jpg .jpeg .webp .tif .tiff
```

Outputs are naturally sorted by filename and use the same base filenames in the output folder. Re-running skips already successful outputs unless `--overwrite` is passed.

For pipeline tests only, there is an explicit debug adapter:

```bash
PYTHONPATH=src .venv/bin/manga-colorist colorize --input ./pages --output ./colored --model debug-tint
```

`debug-tint` is not real manga colorization.

## Preserve Resolution

`--preserve-resolution` is enabled by default. It keeps the original page dimensions and high-resolution line art while transferring the model's generated color. Use `--no-preserve-resolution` only when you want the legacy lower-resolution model output.

You can tune upstream inference size with `--model-size 576`; the value must be divisible by 32. `--model-size` is passed to `manga-colorization-v2` as its `-s` argument. `--preserve-resolution` is handled by this wrapper after the model finishes.

For the detailed engineering explanation, see [`docs/preserve-resolution.md`](docs/preserve-resolution.md).

## Cast Review Workspace

The cast review workflow is a separate helper for finding, grouping, naming, and reviewing character appearances. It does not change `manga-colorization-v2` colorization yet, but it saves useful cast metadata for future reference-guided workflows.

Run discovery:

```bash
PYTHONPATH=src .venv/bin/manga-colorist discover-cast --input ./pages --output ./cast-workspace
```

`discover-cast` generates the whole review workspace:

- `cast-workspace/crops/`: proposed character appearance crops.
- `cast-workspace/detections.json`: machine-readable detections with page names, boxes, confidence, crop paths, and cluster IDs.
- `cast-workspace/clusters.yaml`: editable review file.
- `cast-workspace/characters.yaml`: exported cast metadata for future reference-guided adapters.
- `cast-workspace/review.html`: static read-only contact sheet grouped by cluster.

For interactive review, run:

```bash
PYTHONPATH=src .venv/bin/manga-colorist review-cast --workspace ./cast-workspace
```

Open the printed local URL, usually:

```text
http://127.0.0.1:8765/
```

In the review UI you can:

- Drag appearance cards between clusters.
- Move a card with its `Move` button; the target list uses the clusters' current names.
- Delete a card with confirmation; Return/Enter confirms the dialog.
- Add new empty clusters for sorting messy detections.
- Click a crop to inspect it in a full-page zoom popup.
- Draw a rectangle in the zoom popup and apply it to crop away unnecessary portions.
- Rename clusters, such as `zoro`.
- Edit swatch colors for `hair`, `skin`, and `clothes`.
- Edit anchors as JSON.
- Uncheck `approved` for false positives.
- Press Save to update `clusters.yaml` and regenerate `characters.yaml`.

`review.html` is generated by `discover-cast` and remains available as a read-only contact sheet if you only want to inspect the detections.

### Reviewing `clusters.yaml` Manually

Discovery starts with unnamed clusters:

```yaml
clusters:
  cluster_001:
    name: ""
    swatches:
      hair: "#888888"
      skin: "#d2a47a"
      clothes: "#666666"
    anchors:
      - part: hair
        color: hair
        relative_xy: [0.50, 0.18]
        radius: 18
    appearances:
      - id: app_0001_01
        page: "01-2.png"
        xywh: [210, 430, 180, 260]
        crop: "crops/app_0001_01_01-2.png"
        confidence: 0.74
        approved: true
```

The interactive review UI edits this structure for you. If you edit manually:

- Set `name` to a character key, such as `zoro`.
- Change `swatches` to that character's colors.
- Adjust `anchors` for the character's usual box-relative hint positions.
- Set `approved: false` for wrong detections or appearances that belong to another character.
- To merge two clusters, give them the same `name`; exported page boxes will be grouped under that character.

After manual review, export clean cast metadata. The interactive Save button does this automatically. Clusters with an empty `name` are exported using their cluster ID, such as `cluster_001`; set a real name before export when you know the character.

```bash
PYTHONPATH=src .venv/bin/manga-colorist export-cast --clusters ./cast-workspace/clusters.yaml --output ./cast-workspace/characters.yaml
```

The current discovery pass uses local image heuristics and simple visual clustering. It is meant to propose useful review candidates, not to perfectly recognize every character automatically. The discovery files are intentionally model-agnostic so better detection, embedding, or reference-guided backends can be added later without changing the review workspace.

### Validation Rules

- Hex colors must look like `"#rrggbb"`.
- `relative_xy` values must be between `0.0` and `1.0`.
- `radius` must be a positive integer.
- Boxes must use positive width and height.
- Page names must match files in the folder you are processing exactly.

## Reusable Batch Task

For coloring a full manga parent folder, copying excluded pages unchanged, and creating flat `.cbz` archives per chapter, see [`tasks/color-by-manga-folder.md`](tasks/color-by-manga-folder.md).

## Generated Files And Git Ignore

These folders are local/generated and intentionally should not be committed:

- `.external/`: third-party model checkout and weights.
- `.cache/` and `.pytest_cache/`: local caches.
- `cast-workspace/`: generated cast review data.
- `colored*/`: local colorized outputs.
- Local input folders such as `pages/`, unless you intentionally add your own sample images.

It is safe to delete `cast-workspace/` if you do not need the current review progress. Regenerate it later with `discover-cast`.

## Troubleshooting

`Setup error: MANGA_COLORIZATION_V2_PATH is not set`

Set `MANGA_COLORIZATION_V2_PATH` and `MANGA_COLORIZATION_V2_PYTHON`, or use the full quick command at the top of this README.

`Missing manga-colorization-v2 weight`

Check that the three required weight files exist at the exact paths listed in the setup section.

`--device auto` fails on Apple Silicon/MPS

The current `manga-colorization-v2` adapter is validated for CPU and CUDA, not MPS. On Apple Silicon, use `--device cpu`.

Output looks lower-resolution than the source

Use the default `--preserve-resolution` mode. If you passed `--no-preserve-resolution`, the output is the external model's lower-resolution result.

No images were processed

Check that the input folder contains supported image files directly inside that folder. This CLI does not process PDFs, CBZ files, or nested folders in v1.

## Reserved Future Controls

`--reference-dir` and `--palette` are reserved for future reference-guided and manual-palette workflows. Passing either option in v1 exits with a clear message.
