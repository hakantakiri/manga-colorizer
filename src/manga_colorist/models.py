from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal


ResultStatus = Literal["success", "skipped", "failed"]


@dataclass(frozen=True)
class ColorizationRequest:
    input_path: Path
    output_path: Path
    device: str
    reference_paths: tuple[Path, ...] = ()
    palette_path: Path | None = None
    settings: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ColorizationResult:
    input_path: Path
    output_path: Path
    status: ResultStatus
    elapsed_seconds: float
    warnings: list[str] = field(default_factory=list)
    error: str | None = None
    model_metadata: dict[str, Any] = field(default_factory=dict)
    details: dict[str, Any] = field(default_factory=dict)
