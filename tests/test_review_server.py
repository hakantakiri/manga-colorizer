from __future__ import annotations

import json
from pathlib import Path

import yaml
from PIL import Image
from typer.testing import CliRunner

from manga_colorist.cli import app
from manga_colorist.discovery import (
    clusters_yaml_to_review_state,
    load_clusters_yaml,
    review_state_to_clusters_yaml,
)
from manga_colorist.review_server import (
    INTERACTIVE_HTML,
    load_review_state,
    resolve_crop_path,
    save_review_state_from_json,
)


def make_workspace(tmp_path: Path) -> Path:
    workspace = tmp_path / "cast"
    crops = workspace / "crops"
    crops.mkdir(parents=True)
    Image.new("RGB", (8, 8), "white").save(crops / "app_1.png")
    (workspace / "clusters.yaml").write_text(
        """
clusters:
  cluster_001:
    name: zoro
    swatches:
      hair: "#8fb86a"
      skin: "#d2a47a"
      clothes: "#2f6f5f"
    anchors:
      - part: hair
        color: hair
        relative_xy: [0.5, 0.2]
        radius: 4
    appearances:
      - id: app_1
        page: "01.png"
        xywh: [1, 2, 3, 4]
        crop: "crops/app_1.png"
        confidence: 0.75
        approved: true
  cluster_002:
    name: sanji
    swatches:
      hair: "#dddd88"
    anchors:
      - part: hair
        color: hair
        relative_xy: [0.5, 0.2]
        radius: 4
    appearances: []
""".strip(),
        encoding="utf-8",
    )
    return workspace


def test_review_state_roundtrip_preserves_move_and_approval(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = clusters_yaml_to_review_state(load_clusters_yaml(workspace / "clusters.yaml"))
    app_1 = state["clusters"][0]["appearances"].pop()
    app_1["approved"] = False
    state["clusters"][1]["appearances"].append(app_1)

    payload = review_state_to_clusters_yaml(state)

    assert payload["clusters"]["cluster_001"]["appearances"] == []
    moved = payload["clusters"]["cluster_002"]["appearances"][0]
    assert moved["id"] == "app_1"
    assert moved["approved"] is False


def test_review_cast_cli_help_includes_command() -> None:
    result = CliRunner().invoke(app, ["review-cast", "--help"])

    assert result.exit_code == 0
    assert "--workspace" in result.output


def test_review_html_has_add_cluster_and_lightbox_controls() -> None:
    assert 'id="add-cluster"' in INTERACTIVE_HTML
    assert 'id="lightbox"' in INTERACTIVE_HTML
    assert "openLightbox" in INTERACTIVE_HTML
    assert 'id="apply-crop"' in INTERACTIVE_HTML
    assert "crop_rect" in INTERACTIVE_HTML
    assert "preview_src" in INTERACTIVE_HTML
    assert "croppedPreviewDataUrl" in INTERACTIVE_HTML
    assert "cacheBust" in INTERACTIVE_HTML
    assert "Character ${number}" in INTERACTIVE_HTML
    assert 'id="move-dialog"' in INTERACTIVE_HTML
    assert 'id="delete-dialog"' in INTERACTIVE_HTML
    assert 'id="delete-cluster-dialog"' in INTERACTIVE_HTML
    assert 'id="new-move-cluster-name"' in INTERACTIVE_HTML
    assert 'id="create-and-move"' in INTERACTIVE_HTML
    assert "openMoveDialog" in INTERACTIVE_HTML
    assert "clusterDisplayName" in INTERACTIVE_HTML
    assert "confirmDeleteAppearance" in INTERACTIVE_HTML
    assert "openDeleteClusterDialog" in INTERACTIVE_HTML
    assert "confirmDeleteCluster" in INTERACTIVE_HTML
    assert "createClusterAndMoveAppearance" in INTERACTIVE_HTML
    assert 'data-action="remove-cluster"' in INTERACTIVE_HTML
    assert 'event.key === "Enter"' in INTERACTIVE_HTML


def test_review_server_load_and_save_clusters(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)

    assert state["clusters"][0]["id"] == "cluster_001"
    state["clusters"][0]["name"] = "roronoa_zoro"
    state["clusters"][0]["appearances"][0]["approved"] = False
    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    assert clusters["clusters"]["cluster_001"]["name"] == "roronoa_zoro"
    characters = yaml.safe_load((workspace / "characters.yaml").read_text(encoding="utf-8"))
    assert characters["characters"] == {}


def test_review_server_saves_new_empty_cluster(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)
    state["clusters"].append(
        {
            "id": "cluster_003",
            "name": "nami",
            "swatches": {"hair": "#e6a44c", "skin": "#d2a47a", "clothes": "#3366aa"},
            "anchors": [{"part": "hair", "color": "hair", "relative_xy": [0.5, 0.2], "radius": 8}],
            "appearances": [],
        }
    )

    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    assert clusters["clusters"]["cluster_003"]["name"] == "nami"


def test_review_server_saves_move_to_named_cluster(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)
    app_1 = state["clusters"][0]["appearances"].pop()
    state["clusters"][1]["name"] = "Character 2"
    state["clusters"][1]["appearances"].append(app_1)

    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    assert clusters["clusters"]["cluster_001"]["appearances"] == []
    assert clusters["clusters"]["cluster_002"]["appearances"][0]["id"] == "app_1"
    characters = yaml.safe_load((workspace / "characters.yaml").read_text(encoding="utf-8"))
    assert "Character 2" in characters["characters"]


def test_review_server_saves_move_to_created_named_cluster(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)
    app_1 = state["clusters"][0]["appearances"].pop()
    state["clusters"].append(
        {
            "id": "cluster_003",
            "name": "nami",
            "swatches": {"hair": "#e6a44c", "skin": "#d2a47a", "clothes": "#3366aa"},
            "anchors": [{"part": "hair", "color": "hair", "relative_xy": [0.5, 0.2], "radius": 8}],
            "appearances": [app_1],
        }
    )

    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    assert clusters["clusters"]["cluster_001"]["appearances"] == []
    assert clusters["clusters"]["cluster_003"]["name"] == "nami"
    assert clusters["clusters"]["cluster_003"]["appearances"][0]["id"] == "app_1"
    characters = yaml.safe_load((workspace / "characters.yaml").read_text(encoding="utf-8"))
    assert "nami" in characters["characters"]
    assert characters["pages"]["01.png"]["characters"]["nami"]["boxes"] == [{"xywh": [1, 2, 3, 4]}]


def test_review_server_saves_deleted_appearance(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)
    state["clusters"][0]["appearances"] = []

    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    assert clusters["clusters"]["cluster_001"]["appearances"] == []
    characters = yaml.safe_load((workspace / "characters.yaml").read_text(encoding="utf-8"))
    assert "zoro" not in characters["characters"]


def test_review_server_saves_removed_cluster_with_appearances(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)
    state["clusters"] = [cluster for cluster in state["clusters"] if cluster["id"] != "cluster_001"]

    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    assert "cluster_001" not in clusters["clusters"]
    assert "cluster_002" in clusters["clusters"]
    characters = yaml.safe_load((workspace / "characters.yaml").read_text(encoding="utf-8"))
    assert "zoro" not in characters["characters"]
    assert (workspace / "crops" / "app_1.png").exists()


def test_review_server_applies_pending_crop_on_save(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)
    state = load_review_state(workspace)
    state["clusters"][0]["appearances"][0]["xywh"] = [10, 20, 8, 8]
    state["clusters"][0]["appearances"][0]["crop_rect"] = [2, 1, 4, 5]

    save_review_state_from_json(workspace, json.dumps(state).encode("utf-8"))

    clusters = yaml.safe_load((workspace / "clusters.yaml").read_text(encoding="utf-8"))
    appearance = clusters["clusters"]["cluster_001"]["appearances"][0]
    assert appearance["xywh"] == [12, 21, 4, 5]
    assert "crop_rect" not in appearance
    with Image.open(workspace / "crops" / "app_1.png") as image:
        assert image.size == (4, 5)


def test_review_server_resolves_crops_and_rejects_traversal(tmp_path: Path) -> None:
    workspace = make_workspace(tmp_path)

    assert resolve_crop_path(workspace, "/crops/app_1.png").name == "app_1.png"
    try:
        resolve_crop_path(workspace, "/crops/../clusters.yaml")
    except ValueError:
        pass
    else:
        raise AssertionError("Expected traversal request to be rejected.")
