from __future__ import annotations

import hashlib
import html
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import yaml
from PIL import Image

from manga_colorist.io import discover_images, load_normalized_rgb


@dataclass(frozen=True)
class Detection:
    id: str
    page: str
    page_path: Path
    xywh: tuple[int, int, int, int]
    confidence: float
    crop_path: Path
    cluster_id: str | None = None

    def to_json(self, output_dir: Path) -> dict[str, Any]:
        payload = asdict(self)
        payload["page_path"] = str(self.page_path)
        payload["crop_path"] = str(self.crop_path.relative_to(output_dir))
        payload["xywh"] = list(self.xywh)
        return payload


@dataclass(frozen=True)
class DiscoveryResult:
    detections: tuple[Detection, ...]
    clusters: dict[str, tuple[Detection, ...]]
    output_dir: Path


def discover_cast(
    input_dir: Path,
    output_dir: Path,
    max_candidates_per_page: int = 8,
    min_area_ratio: float = 0.015,
    max_area_ratio: float = 0.45,
    cluster_threshold: float = 0.88,
) -> DiscoveryResult:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    crops_dir = output_dir / "crops"
    crops_dir.mkdir(parents=True, exist_ok=True)

    detections: list[Detection] = []
    for page_index, page_path in enumerate(discover_images(input_dir), start=1):
        image = load_normalized_rgb(page_path)
        boxes = detect_character_candidates(image, max_candidates_per_page, min_area_ratio, max_area_ratio)
        for box_index, (xywh, confidence) in enumerate(boxes, start=1):
            detection_id = f"app_{page_index:04d}_{box_index:02d}"
            crop_path = crops_dir / f"{detection_id}_{page_path.stem}.png"
            crop_image(image, xywh).save(crop_path)
            detections.append(
                Detection(
                    id=detection_id,
                    page=page_path.name,
                    page_path=page_path,
                    xywh=xywh,
                    confidence=round(confidence, 4),
                    crop_path=crop_path,
                )
            )

    clustered = assign_clusters(detections, cluster_threshold)
    clusters = group_by_cluster(clustered)
    output_dir.mkdir(parents=True, exist_ok=True)
    write_detections(output_dir / "detections.json", clustered, output_dir)
    write_clusters_yaml(output_dir / "clusters.yaml", clusters, output_dir)
    write_characters_yaml(output_dir / "characters.yaml", clusters)
    write_review_html(output_dir / "review.html", clusters, output_dir)
    return DiscoveryResult(detections=tuple(clustered), clusters=clusters, output_dir=output_dir)


def detect_character_candidates(
    image: Image.Image,
    max_candidates: int = 8,
    min_area_ratio: float = 0.015,
    max_area_ratio: float = 0.45,
) -> list[tuple[tuple[int, int, int, int], float]]:
    rgb = np.array(image.convert("RGB"))
    height, width = rgb.shape[:2]
    gray = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    binary = cv2.threshold(gray, 210, 255, cv2.THRESH_BINARY_INV)[1]
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (11, 11))
    closed = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel, iterations=2)
    contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    page_area = width * height
    boxes: list[tuple[tuple[int, int, int, int], float]] = []
    for contour in contours:
        x, y, box_width, box_height = cv2.boundingRect(contour)
        area = box_width * box_height
        if area < page_area * min_area_ratio:
            continue
        if area > page_area * max_area_ratio:
            continue
        if box_width < 40 or box_height < 40:
            continue
        touches_page_border = x <= 2 or y <= 2 or x + box_width >= width - 2 or y + box_height >= height - 2
        if touches_page_border and area > page_area * 0.18:
            continue
        aspect = box_width / box_height
        if aspect < 0.18 or aspect > 2.8:
            continue
        fill_ratio = cv2.contourArea(contour) / max(1, area)
        confidence = min(0.99, 0.45 + min(area / page_area, 0.25) + min(fill_ratio, 0.35))
        boxes.append(((x, y, box_width, box_height), confidence))

    boxes.extend(sliding_window_candidates(gray, min_area_ratio, max_area_ratio))
    boxes.sort(key=lambda item: (item[1], item[0][2] * item[0][3]), reverse=True)
    return suppress_overlaps(boxes, max_candidates)


def sliding_window_candidates(
    gray: np.ndarray,
    min_area_ratio: float,
    max_area_ratio: float,
) -> list[tuple[tuple[int, int, int, int], float]]:
    height, width = gray.shape
    page_area = width * height
    ink = (gray < 190).astype("float32")
    edges = cv2.Canny(gray, 80, 180).astype("float32") / 255.0
    candidates: list[tuple[tuple[int, int, int, int], float]] = []

    short_side = min(width, height)
    for scale in (0.18, 0.24, 0.32):
        box_width = int(short_side * scale)
        box_height = int(box_width * 1.35)
        if box_width < 48 or box_height < 64:
            continue
        area = box_width * box_height
        if area < page_area * min_area_ratio or area > page_area * max_area_ratio:
            continue
        stride_x = max(24, box_width // 2)
        stride_y = max(24, box_height // 2)
        for y in range(0, max(1, height - box_height + 1), stride_y):
            for x in range(0, max(1, width - box_width + 1), stride_x):
                region_ink = ink[y : y + box_height, x : x + box_width]
                region_edges = edges[y : y + box_height, x : x + box_width]
                ink_density = float(region_ink.mean())
                edge_density = float(region_edges.mean())
                if ink_density < 0.05 or ink_density > 0.55:
                    continue
                if edge_density < 0.025:
                    continue
                confidence = min(0.92, 0.35 + ink_density * 0.7 + edge_density * 1.8)
                candidates.append(((x, y, box_width, box_height), confidence))
    return candidates


def suppress_overlaps(
    candidates: list[tuple[tuple[int, int, int, int], float]],
    limit: int,
    iou_threshold: float = 0.55,
) -> list[tuple[tuple[int, int, int, int], float]]:
    kept: list[tuple[tuple[int, int, int, int], float]] = []
    for candidate in candidates:
        if all(box_iou(candidate[0], kept_candidate[0]) < iou_threshold for kept_candidate in kept):
            kept.append(candidate)
        if len(kept) >= limit:
            break
    return kept


def assign_clusters(
    detections: list[Detection],
    threshold: float = 0.88,
) -> list[Detection]:
    clusters: list[tuple[str, np.ndarray]] = []
    assigned: list[Detection] = []
    for detection in detections:
        embedding = crop_embedding(detection.crop_path)
        best_cluster_id: str | None = None
        best_similarity = -1.0
        for cluster_id, centroid in clusters:
            similarity = cosine_similarity(embedding, centroid)
            if similarity > best_similarity:
                best_cluster_id = cluster_id
                best_similarity = similarity

        if best_cluster_id is None or best_similarity < threshold:
            best_cluster_id = f"cluster_{len(clusters) + 1:03d}"
            clusters.append((best_cluster_id, embedding))
        else:
            for index, (cluster_id, centroid) in enumerate(clusters):
                if cluster_id == best_cluster_id:
                    clusters[index] = (cluster_id, normalize((centroid + embedding) / 2))
                    break

        assigned.append(
            Detection(
                id=detection.id,
                page=detection.page,
                page_path=detection.page_path,
                xywh=detection.xywh,
                confidence=detection.confidence,
                crop_path=detection.crop_path,
                cluster_id=best_cluster_id,
            )
        )
    return assigned


def group_by_cluster(detections: list[Detection]) -> dict[str, tuple[Detection, ...]]:
    clusters: dict[str, list[Detection]] = {}
    for detection in detections:
        cluster_id = detection.cluster_id or "cluster_000"
        clusters.setdefault(cluster_id, []).append(detection)
    return {cluster_id: tuple(items) for cluster_id, items in sorted(clusters.items())}


def crop_embedding(crop_path: Path, size: int = 32) -> np.ndarray:
    with Image.open(crop_path) as image:
        gray = np.array(image.convert("L").resize((size, size)))
    hist = np.histogram(gray, bins=16, range=(0, 255), density=True)[0].astype("float32")
    small = (gray.astype("float32") / 255.0).reshape(-1)
    digest = int(hashlib.sha1(crop_path.read_bytes()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return normalize(np.concatenate([small, hist, np.array([digest], dtype="float32")]))


def crop_image(image: Image.Image, xywh: tuple[int, int, int, int]) -> Image.Image:
    x, y, width, height = xywh
    return image.crop((x, y, x + width, y + height))


def write_detections(path: Path, detections: list[Detection], output_dir: Path) -> None:
    payload = {"detections": [detection.to_json(output_dir) for detection in detections]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def write_clusters_yaml(
    path: Path,
    clusters: dict[str, tuple[Detection, ...]],
    output_dir: Path,
) -> None:
    payload = {
        "clusters": {
            cluster_id: {
                "name": "",
                "swatches": default_swatches(),
                "anchors": default_anchors(),
                "appearances": [
                    {
                        "id": detection.id,
                        "page": detection.page,
                        "xywh": list(detection.xywh),
                        "crop": str(detection.crop_path.relative_to(output_dir)),
                        "confidence": detection.confidence,
                        "approved": True,
                    }
                    for detection in detections
                ],
            }
            for cluster_id, detections in clusters.items()
        }
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def write_characters_yaml(path: Path, clusters: dict[str, tuple[Detection, ...]]) -> None:
    payload = clusters_to_character_bible(
        {
            "clusters": {
                cluster_id: {
                    "name": "",
                    "swatches": default_swatches(),
                    "anchors": default_anchors(),
                    "appearances": [
                        {
                            "id": detection.id,
                            "page": detection.page,
                            "xywh": list(detection.xywh),
                            "approved": True,
                        }
                        for detection in detections
                    ],
                }
                for cluster_id, detections in clusters.items()
            }
        }
    )
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def export_reviewed_clusters(clusters_yaml: Path, characters_yaml: Path) -> dict[str, Any]:
    payload = load_clusters_yaml(clusters_yaml)
    character_bible = clusters_to_character_bible(payload)
    characters_yaml.write_text(yaml.safe_dump(character_bible, sort_keys=False), encoding="utf-8")
    return character_bible


def load_clusters_yaml(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(payload, dict):
        raise ValueError("clusters.yaml must contain a YAML mapping.")
    if not isinstance(payload.get("clusters"), dict):
        raise ValueError("clusters.yaml must contain a 'clusters' mapping.")
    return payload


def save_review_state(workspace: Path, state: dict[str, Any]) -> dict[str, Any]:
    apply_crop_edits(workspace, state)
    clusters_payload = review_state_to_clusters_yaml(state)
    clusters_path = workspace / "clusters.yaml"
    characters_path = workspace / "characters.yaml"
    clusters_path.write_text(yaml.safe_dump(clusters_payload, sort_keys=False), encoding="utf-8")
    character_bible = clusters_to_character_bible(clusters_payload)
    characters_path.write_text(yaml.safe_dump(character_bible, sort_keys=False), encoding="utf-8")
    return {"clusters": clusters_payload, "characters": character_bible}


def clusters_yaml_to_review_state(payload: dict[str, Any]) -> dict[str, Any]:
    raw_clusters = payload.get("clusters", {})
    if not isinstance(raw_clusters, dict):
        raise ValueError("clusters.yaml must contain a 'clusters' mapping.")

    clusters: list[dict[str, Any]] = []
    for cluster_id, cluster in raw_clusters.items():
        if not isinstance(cluster, dict):
            continue
        clusters.append(
            {
                "id": str(cluster_id),
                "name": str(cluster.get("name", "")),
                "swatches": cluster.get("swatches") or default_swatches(),
                "anchors": cluster.get("anchors") or default_anchors(),
                "appearances": [
                    normalize_review_appearance(appearance)
                    for appearance in cluster.get("appearances", [])
                    if isinstance(appearance, dict)
                ],
            }
        )
    return {"clusters": clusters}


def review_state_to_clusters_yaml(state: dict[str, Any]) -> dict[str, Any]:
    raw_clusters = state.get("clusters")
    if not isinstance(raw_clusters, list):
        raise ValueError("Review state must contain a 'clusters' list.")

    clusters: dict[str, Any] = {}
    used_ids: set[str] = set()
    for index, cluster in enumerate(raw_clusters, start=1):
        if not isinstance(cluster, dict):
            raise ValueError("Each cluster must be an object.")
        cluster_id = str(cluster.get("id") or f"cluster_{index:03d}").strip()
        if not cluster_id:
            cluster_id = f"cluster_{index:03d}"
        if cluster_id in used_ids:
            raise ValueError(f"Duplicate cluster id: {cluster_id}")
        used_ids.add(cluster_id)
        appearances = cluster.get("appearances", [])
        if not isinstance(appearances, list):
            raise ValueError(f"Cluster '{cluster_id}' appearances must be a list.")
        clusters[cluster_id] = {
            "name": str(cluster.get("name", "")),
            "swatches": validate_swatches(cluster.get("swatches") or default_swatches(), cluster_id),
            "anchors": validate_anchors(cluster.get("anchors") or default_anchors(), cluster_id),
            "appearances": [normalize_review_appearance(item) for item in appearances if isinstance(item, dict)],
        }
    return {"clusters": clusters}


def normalize_review_appearance(appearance: dict[str, Any]) -> dict[str, Any]:
    xywh = appearance.get("xywh")
    if (
        not isinstance(xywh, list)
        or len(xywh) != 4
        or not all(isinstance(value, int) for value in xywh)
    ):
        raise ValueError("Appearance xywh must be a four-integer list.")
    normalized = {
        "id": str(appearance.get("id", "")),
        "page": str(appearance.get("page", "")),
        "xywh": xywh,
        "crop": str(appearance.get("crop", "")),
        "confidence": float(appearance.get("confidence", 0.0)),
        "approved": bool(appearance.get("approved", True)),
    }
    crop_rect = appearance.get("crop_rect")
    if crop_rect is not None:
        if (
            not isinstance(crop_rect, list)
            or len(crop_rect) != 4
            or not all(isinstance(value, int) for value in crop_rect)
        ):
            raise ValueError("Appearance crop_rect must be a four-integer list.")
        normalized["crop_rect"] = crop_rect
    return normalized


def apply_crop_edits(workspace: Path, state: dict[str, Any]) -> None:
    clusters = state.get("clusters", [])
    if not isinstance(clusters, list):
        return
    for cluster in clusters:
        if not isinstance(cluster, dict):
            continue
        appearances = cluster.get("appearances", [])
        if not isinstance(appearances, list):
            continue
        for appearance in appearances:
            if not isinstance(appearance, dict) or "crop_rect" not in appearance:
                continue
            apply_crop_edit(workspace, appearance)


def apply_crop_edit(workspace: Path, appearance: dict[str, Any]) -> None:
    crop_rect = appearance.get("crop_rect")
    xywh = appearance.get("xywh")
    crop_path = appearance.get("crop")
    if not isinstance(crop_path, str):
        raise ValueError("Appearance crop path must be a string.")
    if (
        not isinstance(crop_rect, list)
        or len(crop_rect) != 4
        or not all(isinstance(value, int) for value in crop_rect)
    ):
        raise ValueError("Appearance crop_rect must be a four-integer list.")
    if (
        not isinstance(xywh, list)
        or len(xywh) != 4
        or not all(isinstance(value, int) for value in xywh)
    ):
        raise ValueError("Appearance xywh must be a four-integer list.")

    left, top, width, height = crop_rect
    if left < 0 or top < 0 or width <= 0 or height <= 0:
        raise ValueError("Crop rectangle must have positive width and height.")
    target = (workspace / crop_path).resolve()
    crops_root = (workspace / "crops").resolve()
    target.relative_to(crops_root)
    with Image.open(target) as image:
        if left + width > image.width or top + height > image.height:
            raise ValueError("Crop rectangle is outside the current crop image.")
        image.crop((left, top, left + width, top + height)).save(target)

    x, y, _, _ = xywh
    appearance["xywh"] = [x + left, y + top, width, height]
    appearance.pop("crop_rect", None)


def validate_swatches(raw: Any, cluster_id: str) -> dict[str, str]:
    if not isinstance(raw, dict):
        raise ValueError(f"Cluster '{cluster_id}' swatches must be a mapping.")
    swatches: dict[str, str] = {}
    for key, value in raw.items():
        color = str(value)
        if not color.startswith("#") or len(color) != 7:
            raise ValueError(f"Cluster '{cluster_id}' swatch '{key}' must be #rrggbb.")
        swatches[str(key)] = color
    return swatches


def validate_anchors(raw: Any, cluster_id: str) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        raise ValueError(f"Cluster '{cluster_id}' anchors must be a list.")
    anchors: list[dict[str, Any]] = []
    for anchor in raw:
        if not isinstance(anchor, dict):
            raise ValueError(f"Cluster '{cluster_id}' anchors must be objects.")
        anchors.append(
            {
                "part": str(anchor.get("part", "")),
                "color": str(anchor.get("color", "")),
                "relative_xy": anchor.get("relative_xy", [0.5, 0.5]),
                "radius": int(anchor.get("radius", 8)),
            }
        )
    return anchors


def clusters_to_character_bible(payload: dict[str, Any]) -> dict[str, Any]:
    characters: dict[str, Any] = {}
    pages: dict[str, Any] = {}
    raw_clusters = payload.get("clusters", {})
    if not isinstance(raw_clusters, dict):
        raise ValueError("clusters.yaml must contain a 'clusters' mapping.")

    for cluster_id, cluster in raw_clusters.items():
        if not isinstance(cluster, dict):
            continue
        name = str(cluster.get("name") or cluster_id).strip()
        if not name:
            continue
        appearances = cluster.get("appearances", [])
        approved = [item for item in appearances if isinstance(item, dict) and item.get("approved", True)]
        if not approved:
            continue

        characters[name] = {
            "display_name": name,
            "swatches": cluster.get("swatches") or default_swatches(),
            "anchors": cluster.get("anchors") or default_anchors(),
        }
        for appearance in approved:
            page_name = str(appearance["page"])
            pages.setdefault(page_name, {"characters": {}})
            pages[page_name]["characters"].setdefault(name, {"boxes": []})
            pages[page_name]["characters"][name]["boxes"].append({"xywh": appearance["xywh"]})

    return {"characters": characters, "pages": pages}


def write_review_html(
    path: Path,
    clusters: dict[str, tuple[Detection, ...]],
    output_dir: Path,
) -> None:
    sections = []
    for cluster_id, detections in clusters.items():
        cards = []
        for detection in detections:
            crop = html.escape(str(detection.crop_path.relative_to(output_dir)))
            xywh = ", ".join(str(value) for value in detection.xywh)
            cards.append(
                f"""
                <figure>
                  <img src="{crop}" alt="{html.escape(detection.id)}">
                  <figcaption>
                    <strong>{html.escape(detection.id)}</strong><br>
                    {html.escape(detection.page)}<br>
                    xywh: [{xywh}]<br>
                    confidence: {detection.confidence:.2f}
                  </figcaption>
                </figure>
                """
            )
        sections.append(
            f"""
            <section>
              <h2>{html.escape(cluster_id)}</h2>
              <p>Edit <code>clusters.yaml</code>: set <code>name</code>, colors, anchors, and mark wrong appearances as <code>approved: false</code>.</p>
              <div class="grid">{''.join(cards)}</div>
            </section>
            """
        )

    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Manga Cast Review</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, sans-serif; margin: 24px; background: #f8f7f4; color: #1f1f1f; }}
    h1 {{ margin-bottom: 4px; }}
    section {{ border-top: 1px solid #d8d3ca; padding-top: 18px; margin-top: 24px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(160px, 1fr)); gap: 14px; }}
    figure {{ margin: 0; padding: 10px; background: white; border: 1px solid #ddd7cf; border-radius: 6px; }}
    img {{ display: block; width: 100%; height: 180px; object-fit: contain; background: #eee; }}
    figcaption {{ font-size: 12px; line-height: 1.35; margin-top: 8px; }}
    code {{ background: #eee7dc; padding: 1px 4px; border-radius: 3px; }}
  </style>
</head>
<body>
  <h1>Manga Cast Review</h1>
  <p>Review clusters, then edit <code>clusters.yaml</code>. Export approved entries with <code>manga-colorist export-cast</code>.</p>
  {''.join(sections)}
</body>
</html>
""",
        encoding="utf-8",
    )


def default_swatches() -> dict[str, str]:
    return {"hair": "#888888", "skin": "#d2a47a", "clothes": "#666666"}


def default_anchors() -> list[dict[str, Any]]:
    return [
        {"part": "hair", "color": "hair", "relative_xy": [0.50, 0.18], "radius": 18},
        {"part": "skin", "color": "skin", "relative_xy": [0.50, 0.38], "radius": 14},
    ]


def normalize(vector: np.ndarray) -> np.ndarray:
    norm = float(np.linalg.norm(vector))
    if norm == 0:
        return vector
    return vector / norm


def cosine_similarity(left: np.ndarray, right: np.ndarray) -> float:
    return float(np.dot(left, right))


def box_iou(left: tuple[int, int, int, int], right: tuple[int, int, int, int]) -> float:
    left_x, left_y, left_w, left_h = left
    right_x, right_y, right_w, right_h = right
    x1 = max(left_x, right_x)
    y1 = max(left_y, right_y)
    x2 = min(left_x + left_w, right_x + right_w)
    y2 = min(left_y + left_h, right_y + right_h)
    intersection = max(0, x2 - x1) * max(0, y2 - y1)
    union = left_w * left_h + right_w * right_h - intersection
    return intersection / union if union else 0.0
