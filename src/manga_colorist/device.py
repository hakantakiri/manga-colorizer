from __future__ import annotations


class DeviceSelectionError(RuntimeError):
    """Raised when the requested compute device is unavailable."""


def _torch():
    try:
        import torch  # type: ignore
    except Exception:
        return None
    return torch


def select_device(requested: str) -> str:
    if requested == "cpu":
        return "cpu"

    torch = _torch()
    if torch is None:
        if requested == "auto":
            return "cpu"
        raise DeviceSelectionError(
            f"Device '{requested}' requires PyTorch. Install with: pip install -e '.[ml]'"
        )

    if requested in ("auto", "mps"):
        mps = getattr(getattr(torch, "backends", None), "mps", None)
        if mps is not None and mps.is_available():
            return "mps"
        if requested == "mps":
            raise DeviceSelectionError("MPS was requested, but PyTorch reports it is unavailable.")

    if requested in ("auto", "cuda"):
        cuda = getattr(torch, "cuda", None)
        if cuda is not None and cuda.is_available():
            return "cuda"
        if requested == "cuda":
            raise DeviceSelectionError("CUDA was requested, but PyTorch reports it is unavailable.")

    return "cpu"
