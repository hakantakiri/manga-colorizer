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

## Cast Review Workspace

The cast review workflow is a separate helper for finding, grouping, naming, and reviewing character appearances. It does not change `manga-colorization-v2` colorization yet, but it saves useful cast metadata for future reference-guided workflows.

Run discovery:

```bash
PYTHONPATH=src .venv/bin/manga-colorist discover-cast --input ./pages --output ./cast-workspace
```

This creates:

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

`review.html` is still available as a read-only contact sheet if you only want to inspect the detections.

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
- Page names must match files in `./pages` exactly.

## Reserved Future Controls

`--reference-dir` and `--palette` are reserved for future reference-guided and manual-palette workflows. Passing either option in v1 exits with a clear message.
