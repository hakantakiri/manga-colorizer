from __future__ import annotations

import json
import mimetypes
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from manga_colorist.discovery import (
    clusters_yaml_to_review_state,
    load_clusters_yaml,
    save_review_state,
)


def serve_review(workspace: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    workspace = workspace.resolve()
    if not (workspace / "clusters.yaml").exists():
        raise FileNotFoundError(f"clusters.yaml was not found in workspace: {workspace}")

    handler = make_review_handler(workspace)
    server = ThreadingHTTPServer((host, port), handler)
    print(f"Review cast UI: http://{host}:{server.server_port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped review server.")
    finally:
        server.server_close()


def make_review_handler(workspace: Path) -> type[BaseHTTPRequestHandler]:
    workspace = workspace.resolve()

    class ReviewHandler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            route = urlparse(self.path).path
            if route == "/":
                self.write_text(INTERACTIVE_HTML, content_type="text/html; charset=utf-8")
                return
            if route == "/api/clusters":
                self.write_json(load_review_state(workspace))
                return
            if route.startswith("/crops/"):
                self.serve_crop(route)
                return
            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            route = urlparse(self.path).path
            if route != "/api/clusters":
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                body = self.rfile.read(length)
                save_review_state_from_json(workspace, body)
                self.write_json({"ok": True})
            except Exception as exc:
                self.write_json({"ok": False, "error": str(exc)}, status=HTTPStatus.BAD_REQUEST)

        def serve_crop(self, route: str) -> None:
            try:
                target = resolve_crop_path(workspace, route)
            except Exception:
                self.send_error(HTTPStatus.FORBIDDEN)
                return
            if not target.exists() or not target.is_file():
                self.send_error(HTTPStatus.NOT_FOUND)
                return
            content_type = mimetypes.guess_type(target.name)[0] or "application/octet-stream"
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(target.stat().st_size))
            self.end_headers()
            self.wfile.write(target.read_bytes())

        def write_json(self, payload: object, status: HTTPStatus = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def write_text(self, payload: str, content_type: str = "text/plain; charset=utf-8") -> None:
            body = payload.encode("utf-8")
            self.send_response(HTTPStatus.OK)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            print(f"{self.address_string()} - {format % args}")

    return ReviewHandler


def load_review_state(workspace: Path) -> dict[str, object]:
    return clusters_yaml_to_review_state(load_clusters_yaml(workspace / "clusters.yaml"))


def save_review_state_from_json(workspace: Path, body: bytes) -> None:
    state = json.loads(body.decode("utf-8"))
    save_review_state(workspace, state)


def resolve_crop_path(workspace: Path, route: str) -> Path:
    relative = Path(unquote(route.lstrip("/")))
    target = (workspace / relative).resolve()
    crops_root = (workspace / "crops").resolve()
    target.relative_to(crops_root)
    return target


INTERACTIVE_HTML = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Manga Cast Editor</title>
  <style>
    :root { color-scheme: light; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
    body { margin: 0; background: #f5f3ef; color: #202020; }
    header { position: sticky; top: 0; z-index: 2; display: flex; align-items: center; gap: 16px; padding: 12px 16px; background: #ffffff; border-bottom: 1px solid #d7d1c8; }
    h1 { font-size: 18px; margin: 0; }
    button { border: 1px solid #a99f92; background: #fff; padding: 7px 10px; border-radius: 5px; cursor: pointer; }
    button.primary { background: #1f6f5f; border-color: #1f6f5f; color: white; }
    button.danger { color: #9f1f1f; border-color: #d8a6a6; }
    main { padding: 16px; }
    #clusters { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 14px; align-items: start; }
    .cluster { background: #fff; border: 1px solid #d7d1c8; border-radius: 7px; min-height: 260px; overflow: hidden; }
    .cluster.drag-over { outline: 3px solid #1f6f5f; }
    .cluster-header { display: grid; gap: 8px; padding: 10px; border-bottom: 1px solid #e5ded5; background: #fbfaf8; }
    .cluster-title { display: grid; gap: 2px; }
    .cluster-title strong { font-size: 16px; }
    .cluster-title small { color: #777067; }
    label { display: grid; gap: 4px; font-size: 12px; color: #4b4741; }
    input, textarea { font: inherit; border: 1px solid #cfc7bc; border-radius: 4px; padding: 6px; background: white; }
    textarea { min-height: 80px; resize: vertical; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 12px; }
    .swatches { display: grid; grid-template-columns: repeat(3, 1fr); gap: 6px; }
    .cards { display: grid; gap: 8px; padding: 10px; min-height: 100px; }
    .card { display: grid; grid-template-columns: 92px 1fr; gap: 8px; padding: 8px; border: 1px solid #ddd7cf; border-radius: 6px; background: white; cursor: grab; }
    .card.false-positive { opacity: 0.45; }
    .card img { width: 92px; height: 104px; object-fit: contain; background: #eee; border: 1px solid #e0ddd8; }
    .card img { cursor: zoom-in; }
    .meta { font-size: 12px; line-height: 1.35; }
    .card-actions { display: flex; gap: 6px; margin-top: 6px; flex-wrap: wrap; }
    .card-actions button { padding: 4px 7px; font-size: 12px; }
    .status { color: #4d4841; font-size: 13px; }
    code { background: #ece6dc; padding: 1px 4px; border-radius: 3px; }
    dialog { width: min(96vw, 1200px); height: min(96vh, 900px); padding: 0; border: 0; border-radius: 8px; background: #111; color: #fff; }
    dialog::backdrop { background: rgba(0, 0, 0, 0.78); }
    .lightbox { display: grid; grid-template-rows: auto 1fr auto; height: 100%; }
    .lightbox header { position: static; display: flex; justify-content: space-between; background: #161616; border-bottom: 1px solid #333; color: #fff; }
    .lightbox button { background: #2b2b2b; color: #fff; border-color: #555; }
    .lightbox-frame { position: relative; display: grid; place-items: center; min-height: 0; padding: 16px; overflow: hidden; cursor: crosshair; }
    .lightbox-frame img { max-width: 100%; max-height: 100%; object-fit: contain; background: #222; }
    .crop-box { position: absolute; border: 2px solid #ffdf6e; background: rgba(255, 223, 110, 0.18); pointer-events: none; display: none; }
    .lightbox-actions { display: flex; align-items: center; gap: 10px; padding: 10px 12px; background: #161616; border-top: 1px solid #333; }
    .lightbox-actions span { font-size: 13px; color: #d8d8d8; }
    .small-dialog { width: min(92vw, 520px); height: auto; background: #fff; color: #202020; }
    .dialog-panel { display: grid; gap: 12px; padding: 16px; }
    .dialog-panel h2 { margin: 0; font-size: 18px; }
    .dialog-actions { display: flex; justify-content: flex-end; gap: 8px; }
    .move-options { display: grid; gap: 8px; max-height: 55vh; overflow: auto; }
    .move-options button { display: grid; gap: 2px; text-align: left; padding: 9px; }
    .move-options small { color: #777067; }
    .move-create { display: grid; grid-template-columns: 1fr auto; gap: 8px; align-items: end; padding-bottom: 10px; border-bottom: 1px solid #e5ded5; }
    .move-create label { font-size: 12px; }
    .empty-state { padding: 30px 16px; border: 1px dashed #c5baac; border-radius: 7px; background: #fff; color: #6e665d; text-align: center; }
  </style>
</head>
<body>
  <header>
    <h1>Manga Cast Editor</h1>
    <button class="primary" id="save">Save</button>
    <button id="add-cluster">Add cluster</button>
    <button id="reload">Reload</button>
    <span class="status" id="status">Loading...</span>
  </header>
  <main>
    <p>Drag cards between clusters, rename clusters, edit colors/anchors, mark bad detections, then Save. Save updates <code>clusters.yaml</code> and regenerates <code>characters.yaml</code>.</p>
    <div id="clusters"></div>
  </main>
  <dialog id="lightbox">
    <div class="lightbox">
      <header>
        <div>
          <strong id="lightbox-title"></strong>
          <span id="lightbox-meta"></span>
        </div>
        <button id="close-lightbox">Close</button>
      </header>
      <div class="lightbox-frame">
        <img id="lightbox-image" src="" alt="">
        <div class="crop-box" id="crop-box"></div>
      </div>
      <div class="lightbox-actions">
        <button id="apply-crop">Apply crop</button>
        <button id="clear-crop">Clear selection</button>
        <span id="crop-meta">Drag on the image to select the useful region.</span>
      </div>
    </div>
  </dialog>
  <dialog id="move-dialog" class="small-dialog">
    <div class="dialog-panel">
      <h2>Move appearance</h2>
      <p id="move-dialog-meta"></p>
      <div class="move-create">
        <label>New cluster name <input id="new-move-cluster-name" placeholder="Character 3"></label>
        <button type="button" class="primary" id="create-and-move">Create and add</button>
      </div>
      <div class="move-options" id="move-options"></div>
      <div class="dialog-actions">
        <button id="cancel-move">Cancel</button>
      </div>
    </div>
  </dialog>
  <dialog id="delete-dialog" class="small-dialog">
    <div class="dialog-panel">
      <h2>Delete appearance?</h2>
      <p id="delete-dialog-meta"></p>
      <div class="dialog-actions">
        <button id="cancel-delete">Cancel</button>
        <button class="danger" id="confirm-delete">Delete</button>
      </div>
    </div>
  </dialog>
  <dialog id="delete-cluster-dialog" class="small-dialog">
    <div class="dialog-panel">
      <h2>Remove cluster?</h2>
      <p id="delete-cluster-dialog-meta"></p>
      <div class="dialog-actions">
        <button id="cancel-delete-cluster">Cancel</button>
        <button class="danger" id="confirm-delete-cluster">Remove cluster</button>
      </div>
    </div>
  </dialog>
  <script>
    let state = { clusters: [] };
    let dragged = null;
    const status = document.getElementById("status");
    const clustersEl = document.getElementById("clusters");
    const lightbox = document.getElementById("lightbox");
    const lightboxImage = document.getElementById("lightbox-image");
    const lightboxTitle = document.getElementById("lightbox-title");
    const lightboxMeta = document.getElementById("lightbox-meta");
    const cropBox = document.getElementById("crop-box");
    const cropMeta = document.getElementById("crop-meta");
    const moveDialog = document.getElementById("move-dialog");
    const moveOptions = document.getElementById("move-options");
    const moveDialogMeta = document.getElementById("move-dialog-meta");
    const newMoveClusterName = document.getElementById("new-move-cluster-name");
    const createAndMoveButton = document.getElementById("create-and-move");
    const deleteDialog = document.getElementById("delete-dialog");
    const deleteDialogMeta = document.getElementById("delete-dialog-meta");
    const confirmDeleteButton = document.getElementById("confirm-delete");
    const deleteClusterDialog = document.getElementById("delete-cluster-dialog");
    const deleteClusterDialogMeta = document.getElementById("delete-cluster-dialog-meta");
    const confirmDeleteClusterButton = document.getElementById("confirm-delete-cluster");
    let currentAppearance = null;
    let cropStart = null;
    let currentCropRect = null;
    let pendingDelete = null;
    let pendingClusterDelete = null;
    let pendingMove = null;

    async function loadState(options = {}) {
      status.textContent = options.message ? `${options.message}; refreshing...` : "Loading...";
      const response = await fetch("/api/clusters");
      state = await response.json();
      if (options.cacheBust) {
        for (const cluster of state.clusters) {
          for (const appearance of cluster.appearances || []) {
            appearance.cache_bust = options.cacheBust;
          }
        }
      }
      render();
      status.textContent = options.message || "Loaded";
    }

    function markDirty() {
      status.textContent = "Unsaved changes";
    }

    function addCluster() {
      const id = nextClusterId();
      const cluster = defaultCluster(id, newClusterName(id));
      state.clusters.push(cluster);
      render();
      markDirty();
      document.querySelector(`[data-cluster-id="${id}"] input[data-field="name"]`)?.focus();
    }

    function defaultCluster(id, name) {
      return {
        id,
        name,
        swatches: { hair: "#888888", skin: "#d2a47a", clothes: "#666666" },
        anchors: [
          { part: "hair", color: "hair", relative_xy: [0.5, 0.18], radius: 18 },
          { part: "skin", color: "skin", relative_xy: [0.5, 0.38], radius: 14 }
        ],
        appearances: []
      };
    }

    function newClusterName(clusterId) {
      const match = String(clusterId).match(/(\d+)$/);
      const number = match ? Number.parseInt(match[1], 10) : state.clusters.length + 1;
      return `Character ${number}`;
    }

    function clusterDisplayName(cluster) {
      return (cluster.name && cluster.name.trim()) || newClusterName(cluster.id);
    }

    function nextClusterId() {
      const used = new Set(state.clusters.map(cluster => cluster.id));
      let index = state.clusters.length + 1;
      while (used.has(`cluster_${String(index).padStart(3, "0")}`)) {
        index += 1;
      }
      return `cluster_${String(index).padStart(3, "0")}`;
    }

    function render() {
      clustersEl.innerHTML = "";
      if (!state.clusters.length) {
        const empty = document.createElement("div");
        empty.className = "empty-state";
        empty.textContent = "No clusters yet. Add a cluster or move an appearance into a new one before saving.";
        clustersEl.appendChild(empty);
        return;
      }
      for (const cluster of state.clusters) {
        const section = document.createElement("section");
        section.className = "cluster";
        section.dataset.clusterId = cluster.id;
        const displayName = clusterDisplayName(cluster);
        section.innerHTML = `
          <div class="cluster-header">
            <div class="cluster-title">
              <strong data-role="cluster-title">${escapeHtml(displayName)}</strong>
              <small>${escapeHtml(cluster.id)}</small>
            </div>
            <button type="button" class="danger" data-action="remove-cluster">Remove cluster</button>
            <label>Name <input data-field="name" value="${escapeAttr(cluster.name || "")}" placeholder="${escapeAttr(displayName)}"></label>
            <div class="swatches">
              ${["hair", "skin", "clothes"].map(key => `
                <label>${key}<input data-swatch="${key}" type="color" value="${escapeAttr((cluster.swatches && cluster.swatches[key]) || "#888888")}"></label>
              `).join("")}
            </div>
            <label>Anchors JSON <textarea data-field="anchors">${escapeHtml(JSON.stringify(cluster.anchors || [], null, 2))}</textarea></label>
          </div>
          <div class="cards"></div>
        `;
        const cards = section.querySelector(".cards");
        for (const appearance of cluster.appearances || []) {
          cards.appendChild(cardElement(appearance, cluster.id));
        }
        section.addEventListener("dragover", event => {
          event.preventDefault();
          section.classList.add("drag-over");
        });
        section.addEventListener("dragleave", () => section.classList.remove("drag-over"));
        section.addEventListener("drop", event => {
          event.preventDefault();
          section.classList.remove("drag-over");
          if (!dragged) return;
          moveAppearance(dragged.appearanceId, dragged.clusterId, cluster.id);
        });
        section.querySelector('[data-action="remove-cluster"]').addEventListener("click", event => {
          event.stopPropagation();
          openDeleteClusterDialog(cluster.id);
        });
        section.querySelector('[data-field="name"]').addEventListener("input", event => {
          cluster.name = event.target.value;
          syncClusterTitle(cluster.id);
          markDirty();
        });
        section.querySelectorAll("[data-swatch]").forEach(input => {
          input.addEventListener("input", event => {
            cluster.swatches = cluster.swatches || {};
            cluster.swatches[event.target.dataset.swatch] = event.target.value;
            markDirty();
          });
        });
        section.querySelector('[data-field="anchors"]').addEventListener("input", event => {
          try {
            cluster.anchors = JSON.parse(event.target.value);
            event.target.style.borderColor = "#cfc7bc";
            markDirty();
          } catch {
            event.target.style.borderColor = "#b3261e";
            status.textContent = "Anchor JSON is invalid";
          }
        });
        clustersEl.appendChild(section);
      }
    }

    function cardElement(appearance, clusterId) {
      const article = document.createElement("article");
      article.className = `card${appearance.approved === false ? " false-positive" : ""}`;
      article.draggable = true;
      article.dataset.appearanceId = appearance.id;
      article.innerHTML = `
        <img src="${escapeAttr(appearance.preview_src || imageUrl(appearance))}" alt="${escapeAttr(appearance.id)}">
        <div class="meta">
          <strong>${escapeHtml(appearance.id)}</strong><br>
          ${escapeHtml(appearance.page)}<br>
          xywh: [${appearance.xywh.join(", ")}]<br>
          confidence: ${Number(appearance.confidence || 0).toFixed(2)}<br>
          <label><input type="checkbox" ${appearance.approved !== false ? "checked" : ""}> approved</label>
          <div class="card-actions">
            <button type="button" data-action="move">Move</button>
            <button type="button" class="danger" data-action="delete">Delete</button>
          </div>
        </div>
      `;
      article.addEventListener("dragstart", () => { dragged = { appearanceId: appearance.id, clusterId }; });
      article.querySelector("img").addEventListener("click", event => {
        event.stopPropagation();
        openLightbox(appearance);
      });
      article.querySelector("input").addEventListener("change", event => {
        appearance.approved = event.target.checked;
        article.classList.toggle("false-positive", !appearance.approved);
        markDirty();
      });
      article.querySelector('[data-action="move"]').addEventListener("click", event => {
        event.stopPropagation();
        openMoveDialog(appearance.id, clusterId);
      });
      article.querySelector('[data-action="delete"]').addEventListener("click", event => {
        event.stopPropagation();
        openDeleteDialog(appearance.id, clusterId);
      });
      return article;
    }

    function syncClusterTitle(clusterId) {
      const cluster = state.clusters.find(item => item.id === clusterId);
      const title = document.querySelector(`[data-cluster-id="${clusterId}"] [data-role="cluster-title"]`);
      if (cluster && title) {
        title.textContent = clusterDisplayName(cluster);
      }
    }

    function openLightbox(appearance) {
      currentAppearance = appearance;
      cropStart = null;
      currentCropRect = null;
      updateCropBox(null);
      lightboxImage.src = appearance.preview_src || imageUrl(appearance);
      lightboxImage.alt = appearance.id;
      lightboxTitle.textContent = appearance.id;
      lightboxMeta.textContent = ` · ${appearance.page} · xywh [${appearance.xywh.join(", ")}] · confidence ${Number(appearance.confidence || 0).toFixed(2)}`;
      cropMeta.textContent = "Drag on the image to select the useful region.";
      lightbox.showModal();
    }

    function imagePointFromEvent(event) {
      const rect = lightboxImage.getBoundingClientRect();
      const x = Math.max(0, Math.min(rect.width, event.clientX - rect.left));
      const y = Math.max(0, Math.min(rect.height, event.clientY - rect.top));
      return {
        cssX: rect.left + x,
        cssY: rect.top + y,
        imageX: Math.round((x / rect.width) * lightboxImage.naturalWidth),
        imageY: Math.round((y / rect.height) * lightboxImage.naturalHeight)
      };
    }

    function cropRectFromPoints(a, b) {
      const left = Math.max(0, Math.min(a.imageX, b.imageX));
      const top = Math.max(0, Math.min(a.imageY, b.imageY));
      const right = Math.min(lightboxImage.naturalWidth, Math.max(a.imageX, b.imageX));
      const bottom = Math.min(lightboxImage.naturalHeight, Math.max(a.imageY, b.imageY));
      return [left, top, Math.max(0, right - left), Math.max(0, bottom - top)];
    }

    function updateCropBox(points) {
      if (!points) {
        cropBox.style.display = "none";
        return;
      }
      const imageRect = lightboxImage.getBoundingClientRect();
      const frameRect = document.querySelector(".lightbox-frame").getBoundingClientRect();
      const left = Math.min(points.start.cssX, points.end.cssX) - frameRect.left;
      const top = Math.min(points.start.cssY, points.end.cssY) - frameRect.top;
      const width = Math.abs(points.end.cssX - points.start.cssX);
      const height = Math.abs(points.end.cssY - points.start.cssY);
      cropBox.style.display = width > 2 && height > 2 ? "block" : "none";
      cropBox.style.left = `${left}px`;
      cropBox.style.top = `${top}px`;
      cropBox.style.width = `${width}px`;
      cropBox.style.height = `${height}px`;
    }

    function applyCrop() {
      if (!currentAppearance || !currentCropRect || currentCropRect[2] < 4 || currentCropRect[3] < 4) {
        cropMeta.textContent = "Select a larger crop rectangle first.";
        return;
      }
      const [left, top, width, height] = currentCropRect;
      const preview = croppedPreviewDataUrl(lightboxImage, currentCropRect);
      currentAppearance.crop_rect = currentCropRect;
      currentAppearance.xywh = [
        currentAppearance.xywh[0] + left,
        currentAppearance.xywh[1] + top,
        width,
        height
      ];
      if (preview) {
        currentAppearance.preview_src = preview;
      }
      render();
      markDirty();
      cropMeta.textContent = `Pending crop: [${currentCropRect.join(", ")}]. Press Save to write it.`;
      lightbox.close();
    }

    function croppedPreviewDataUrl(image, rect) {
      const [left, top, width, height] = rect;
      if (!image.naturalWidth || !image.naturalHeight || width <= 0 || height <= 0) {
        return null;
      }
      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const context = canvas.getContext("2d");
      context.drawImage(image, left, top, width, height, 0, 0, width, height);
      return canvas.toDataURL("image/png");
    }

    function clearCropSelection() {
      currentCropRect = null;
      cropStart = null;
      updateCropBox(null);
      cropMeta.textContent = "Drag on the image to select the useful region.";
    }

    function moveAppearance(appearanceId, sourceClusterId, targetClusterId) {
      moveAppearanceToCluster(appearanceId, sourceClusterId, targetClusterId);
    }

    function moveAppearanceToCluster(appearanceId, sourceClusterId, targetClusterId) {
      if (sourceClusterId === targetClusterId) return;
      const source = state.clusters.find(cluster => cluster.id === sourceClusterId);
      const target = state.clusters.find(cluster => cluster.id === targetClusterId);
      if (!source || !target) return;
      const index = source.appearances.findIndex(item => item.id === appearanceId);
      if (index < 0) return;
      const [appearance] = source.appearances.splice(index, 1);
      target.appearances.push(appearance);
      dragged = null;
      render();
      markDirty();
    }

    function openMoveDialog(appearanceId, sourceClusterId) {
      const source = state.clusters.find(cluster => cluster.id === sourceClusterId);
      const appearance = source?.appearances.find(item => item.id === appearanceId);
      if (!source || !appearance) return;
      pendingMove = { appearanceId, sourceClusterId };
      moveDialogMeta.textContent = `${appearance.id} from ${clusterDisplayName(source)} (${source.id})`;
      const newId = nextClusterId();
      newMoveClusterName.value = "";
      newMoveClusterName.placeholder = newClusterName(newId);
      moveOptions.innerHTML = "";
      for (const cluster of state.clusters) {
        if (cluster.id === sourceClusterId) continue;
        const option = document.createElement("button");
        option.type = "button";
        option.innerHTML = `<strong>${escapeHtml(clusterDisplayName(cluster))}</strong><small>${escapeHtml(cluster.id)}</small>`;
        option.addEventListener("click", () => {
          moveAppearanceToCluster(appearanceId, sourceClusterId, cluster.id);
          moveDialog.close();
        });
        moveOptions.appendChild(option);
      }
      if (!moveOptions.children.length) {
        moveOptions.textContent = "No other clusters available. Create one above.";
      }
      moveDialog.showModal();
      newMoveClusterName.focus();
    }

    function createClusterAndMoveAppearance(appearanceId, sourceClusterId) {
      const id = nextClusterId();
      const name = newMoveClusterName.value.trim() || newClusterName(id);
      state.clusters.push(defaultCluster(id, name));
      moveAppearanceToCluster(appearanceId, sourceClusterId, id);
      moveDialog.close();
      pendingMove = null;
    }

    function openDeleteDialog(appearanceId, clusterId) {
      const cluster = state.clusters.find(item => item.id === clusterId);
      const appearance = cluster?.appearances.find(item => item.id === appearanceId);
      if (!cluster || !appearance) return;
      pendingDelete = { appearanceId, clusterId };
      deleteDialogMeta.textContent = `Delete ${appearance.id} from ${appearance.page}? The crop image file stays on disk until you clean the workspace manually.`;
      deleteDialog.showModal();
      confirmDeleteButton.focus();
    }

    function confirmDeleteAppearance() {
      if (!pendingDelete) return;
      const cluster = state.clusters.find(item => item.id === pendingDelete.clusterId);
      if (!cluster) return;
      cluster.appearances = cluster.appearances.filter(item => item.id !== pendingDelete.appearanceId);
      pendingDelete = null;
      deleteDialog.close();
      render();
      markDirty();
    }

    function clusterAppearanceCount(cluster) {
      return (cluster.appearances || []).length;
    }

    function openDeleteClusterDialog(clusterId) {
      const cluster = state.clusters.find(item => item.id === clusterId);
      if (!cluster) return;
      pendingClusterDelete = { clusterId };
      const count = clusterAppearanceCount(cluster);
      const itemLabel = count === 1 ? "appearance" : "appearances";
      deleteClusterDialogMeta.textContent = `Remove ${clusterDisplayName(cluster)} (${cluster.id}) and its ${count} ${itemLabel}? Crop image files stay on disk until you clean the workspace manually.`;
      deleteClusterDialog.showModal();
      confirmDeleteClusterButton.focus();
    }

    function removeCluster(clusterId) {
      state.clusters = state.clusters.filter(cluster => cluster.id !== clusterId);
      dragged = null;
      render();
      markDirty();
    }

    function confirmDeleteCluster() {
      if (!pendingClusterDelete) return;
      removeCluster(pendingClusterDelete.clusterId);
      pendingClusterDelete = null;
      deleteClusterDialog.close();
    }

    async function save() {
      status.textContent = "Saving...";
      const response = await fetch("/api/clusters", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(state)
      });
      const payload = await response.json();
      if (!response.ok || !payload.ok) {
        status.textContent = `Save failed: ${payload.error || response.statusText}`;
        return;
      }
      stripPreviewState();
      await loadState({ cacheBust: Date.now(), message: "Saved" });
    }

    function stripPreviewState() {
      for (const cluster of state.clusters) {
        for (const appearance of cluster.appearances || []) {
          delete appearance.preview_src;
          delete appearance.crop_rect;
        }
      }
    }

    function imageUrl(appearance) {
      const suffix = appearance.cache_bust ? `?v=${appearance.cache_bust}` : "";
      return `/${appearance.crop}${suffix}`;
    }

    function escapeHtml(value) {
      return String(value).replace(/[&<>"']/g, char => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[char]));
    }

    function escapeAttr(value) {
      return escapeHtml(value);
    }

    document.getElementById("save").addEventListener("click", save);
    document.getElementById("add-cluster").addEventListener("click", addCluster);
    document.getElementById("reload").addEventListener("click", loadState);
    document.getElementById("cancel-move").addEventListener("click", () => {
      pendingMove = null;
      moveDialog.close();
    });
    createAndMoveButton.addEventListener("click", event => {
      event.stopPropagation();
      if (!pendingMove) return;
      createClusterAndMoveAppearance(pendingMove.appearanceId, pendingMove.sourceClusterId);
    });
    document.getElementById("cancel-delete").addEventListener("click", () => {
      pendingDelete = null;
      deleteDialog.close();
    });
    document.getElementById("cancel-delete-cluster").addEventListener("click", () => {
      pendingClusterDelete = null;
      deleteClusterDialog.close();
    });
    confirmDeleteButton.addEventListener("click", confirmDeleteAppearance);
    confirmDeleteClusterButton.addEventListener("click", confirmDeleteCluster);
    deleteDialog.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        confirmDeleteAppearance();
      }
    });
    deleteClusterDialog.addEventListener("keydown", event => {
      if (event.key === "Enter") {
        event.preventDefault();
        confirmDeleteCluster();
      }
    });
    document.getElementById("close-lightbox").addEventListener("click", () => lightbox.close());
    document.getElementById("apply-crop").addEventListener("click", applyCrop);
    document.getElementById("clear-crop").addEventListener("click", clearCropSelection);
    lightboxImage.addEventListener("pointerdown", event => {
      event.preventDefault();
      cropStart = imagePointFromEvent(event);
      currentCropRect = null;
      lightboxImage.setPointerCapture(event.pointerId);
    });
    lightboxImage.addEventListener("pointermove", event => {
      if (!cropStart) return;
      const end = imagePointFromEvent(event);
      currentCropRect = cropRectFromPoints(cropStart, end);
      updateCropBox({ start: cropStart, end });
      cropMeta.textContent = `Selection: [${currentCropRect.join(", ")}]`;
    });
    lightboxImage.addEventListener("pointerup", event => {
      if (!cropStart) return;
      const end = imagePointFromEvent(event);
      currentCropRect = cropRectFromPoints(cropStart, end);
      updateCropBox({ start: cropStart, end });
      cropStart = null;
    });
    lightbox.addEventListener("click", event => {
      if (event.target === lightbox) lightbox.close();
    });
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && lightbox.open) lightbox.close();
    });
    loadState().catch(error => { status.textContent = `Load failed: ${error}`; });
  </script>
</body>
</html>
"""
