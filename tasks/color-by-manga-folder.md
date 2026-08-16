# Reusable Manga Folder Colorization Task

## Goal

Color a manga folder with the current preserve-resolution implementation, mirror the original chapter folders, copy non-target pages unchanged, and create one flat `.cbz` file per chapter.

Run this from the Manga Colorist repo on a branch that supports preserve-resolution, such as:

```bash
git switch codex/preserve-resolution
```

Do not touch unrelated repo artifacts such as `cast-workspace/`, `colored-new/`, or `colored-new copy/`.

## Inputs

Set `SOURCE_ROOT` before running. `OUTPUT_ROOT` and `PAGE_PATTERN` have safe defaults:

```bash
SOURCE_ROOT="/path/to/manga-folder"
OUTPUT_ROOT="${SOURCE_ROOT%/}-ia-colored"
PAGE_PATTERN="[0-9][0-9]-2.png"
```

For another manga, change only `SOURCE_ROOT` unless you want a custom output path.

Output naming convention:

```text
<source-folder-name>-ia-colored
```

## Rules

- Process only immediate child folders under `SOURCE_ROOT`; each child folder is treated as one chapter.
- Do not recurse into nested folders.
- Ignore source folders whose name already ends in `-ia-colored`.
- Color only pages whose filename matches exactly `NN-2.png`, such as `01-2.png` or `14-2.png`.
- Exclude pages like `14.png`, `00-01-2.png`, `00-00-2.png`, and `00-08.png` from colorization.
- Copy excluded image files unchanged into the corresponding mirrored chapter folder.
- Preserve final output resolution with `--preserve-resolution`.
- Keep the mirrored chapter folders after creating `.cbz` files.
- Each `.cbz` must contain the chapter PNG files at archive root, not a nested chapter folder.

Supported copied image extensions:

```text
.png .jpg .jpeg .webp .tif .tiff
```

## Preflight

Preview chapter folders and counts:

```bash
: "${SOURCE_ROOT:?Set SOURCE_ROOT first}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${SOURCE_ROOT%/}-ia-colored}"
PAGE_PATTERN="${PAGE_PATTERN:-[0-9][0-9]-2.png}"

find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '*-ia-colored' -print | sort | while IFS= read -r dir; do
  total=$(find "$dir" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' \) | wc -l | tr -d ' ')
  strict=$(find "$dir" -maxdepth 1 -type f -name "$PAGE_PATTERN" | wc -l | tr -d ' ')
  printf '%s total=%s strict_to_color=%s excluded_to_copy=%s\n' "$(basename "$dir")" "$total" "$strict" "$((total-strict))"
done
```

## Execute

This is the proven workflow. It stages only strict pages with symlinks, colorizes those pages, copies excluded pages unchanged, then creates a flat `.cbz` per chapter.

```bash
. .venv/bin/activate
set -u

: "${SOURCE_ROOT:?Set SOURCE_ROOT first}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${SOURCE_ROOT%/}-ia-colored}"
PAGE_PATTERN="${PAGE_PATTERN:-[0-9][0-9]-2.png}"

work_root=$(mktemp -d /private/tmp/manga-color-task.XXXXXX)
cleanup() { rm -rf "$work_root"; }
trap cleanup EXIT

mkdir -p "$OUTPUT_ROOT"

find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '*-ia-colored' -print | sort | while IFS= read -r src_dir; do
  chapter=$(basename "$src_dir")
  chapter_out="$OUTPUT_ROOT/$chapter"
  temp_input="$work_root/$chapter"

  mkdir -p "$temp_input" "$chapter_out"

  strict_count=0
  while IFS= read -r file; do
    ln -sf "$file" "$temp_input/$(basename "$file")"
    strict_count=$((strict_count + 1))
  done < <(find "$src_dir" -maxdepth 1 -type f -name "$PAGE_PATTERN" -print | sort)

  echo "==> Colorizing $chapter ($strict_count strict pages) -> $chapter_out"
  if [ "$strict_count" -gt 0 ]; then
    MANGA_COLORIZATION_V2_PATH="$PWD/.external/manga-colorization-v2" \
    MANGA_COLORIZATION_V2_PYTHON="$PWD/.external/manga-colorization-v2/.venv/bin/python" \
    PYTHONPATH=src \
    manga-colorist colorize \
      --input "$temp_input" \
      --output "$chapter_out" \
      --device cpu \
      --overwrite \
      --preserve-resolution
  fi

  copied_count=0
  while IFS= read -r file; do
    cp -f "$file" "$chapter_out/$(basename "$file")"
    copied_count=$((copied_count + 1))
  done < <(find "$src_dir" -maxdepth 1 -type f \( -iname '*.png' -o -iname '*.jpg' -o -iname '*.jpeg' -o -iname '*.webp' -o -iname '*.tif' -o -iname '*.tiff' \) ! -name "$PAGE_PATTERN" -print | sort)

  echo "==> Copied $copied_count excluded pages for $chapter"

  png_count=$(find "$chapter_out" -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')
  if [ "$png_count" -gt 0 ]; then
    tmp_zip="$work_root/$chapter.zip"
    (cd "$chapter_out" && zip -q -X "$tmp_zip" ./*.png)
    mv -f "$tmp_zip" "$OUTPUT_ROOT/$chapter.cbz"
    echo "==> Packed $OUTPUT_ROOT/$chapter.cbz"
  else
    echo "==> Skipped CBZ for $chapter because no PNG files were found"
  fi
done
```

## Verify

Per-folder mirror counts:

```bash
: "${SOURCE_ROOT:?Set SOURCE_ROOT first}"
OUTPUT_ROOT="${OUTPUT_ROOT:-${SOURCE_ROOT%/}-ia-colored}"

find "$SOURCE_ROOT" -mindepth 1 -maxdepth 1 -type d ! -name '*-ia-colored' -print | sort | while IFS= read -r src; do
  chapter=$(basename "$src")
  out="$OUTPUT_ROOT/$chapter"
  src_count=$(find "$src" -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')
  out_count=$(find "$out" -maxdepth 1 -type f -name '*.png' | wc -l | tr -d ' ')
  printf '%s source=%s output=%s %s\n' "$chapter" "$src_count" "$out_count" "$([ "$src_count" = "$out_count" ] && echo OK || echo MISMATCH)"
done
```

Total PNGs, strict colored pages, copied excluded pages, and CBZ count:

```bash
PAGE_PATTERN="${PAGE_PATTERN:-[0-9][0-9]-2.png}"

find "$OUTPUT_ROOT" -mindepth 2 -maxdepth 2 -type f -name '*.png' | wc -l
find "$OUTPUT_ROOT" -mindepth 2 -maxdepth 2 -type f -name "$PAGE_PATTERN" | wc -l
find "$OUTPUT_ROOT" -mindepth 2 -maxdepth 2 -type f -name '*.png' ! -name "$PAGE_PATTERN" | wc -l
find "$OUTPUT_ROOT" -maxdepth 1 -type f -name '*.cbz' | wc -l
```

Report totals must show zero failures:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
import json
import os

base = Path(os.environ["OUTPUT_ROOT"])
for report in sorted(base.glob("*/run-report.json")):
    data = json.loads(report.read_text())
    totals = data["totals"]
    print(f"{report.parent.name}: success={totals['success']} skipped={totals['skipped']} failed={totals['failed']} total={totals['total']}")
PY
```

CBZ files must be flat, with no nested folders:

```bash
for cbz in "$OUTPUT_ROOT"/*.cbz; do
  nested=$(zipinfo -1 "$cbz" | grep '/' | wc -l | tr -d ' ')
  entries=$(zipinfo -1 "$cbz" | wc -l | tr -d ' ')
  printf '%s entries=%s nested=%s\n' "$(basename "$cbz")" "$entries" "$nested"
done
```

Spot-check resolution preservation for a few strict pages:

```bash
.venv/bin/python - <<'PY'
from pathlib import Path
from PIL import Image
import os

source = Path(os.environ["SOURCE_ROOT"])
output = Path(os.environ["OUTPUT_ROOT"])
for src in sorted(source.glob("*/[0-9][0-9]-2.png"))[:3]:
    out = output / src.parent.name / src.name
    with Image.open(src) as a, Image.open(out) as b:
        print(f"{src.parent.name}/{src.name}: source={a.size} output={b.size} match={a.size == b.size}")
PY
```

## Successful One Piece Example

The successful run used:

```bash
SOURCE_ROOT="/Users/hackan/Manga/one-piece"
OUTPUT_ROOT="/Users/hackan/Manga/one-piece-ia-colored"
PAGE_PATTERN="[0-9][0-9]-2.png"
```

Expected One Piece verification totals:

```text
strict colored pages: 143
copied excluded pages: 41
total PNGs: 184
CBZ files: 11
```

These totals are an example only. Other manga folders will have different counts.
