from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from manga_colorist.models import ColorizationResult


@dataclass
class RunReport:
    started_at: str
    finished_at: str | None
    settings: dict[str, Any]
    model_metadata: dict[str, Any]
    totals: dict[str, int] = field(default_factory=dict)
    results: list[ColorizationResult] = field(default_factory=list)

    @classmethod
    def start(cls, settings: dict[str, Any], model_metadata: dict[str, Any]) -> "RunReport":
        return cls(
            started_at=datetime.now(timezone.utc).isoformat(),
            finished_at=None,
            settings=settings,
            model_metadata=model_metadata,
        )

    def finish(self) -> None:
        self.finished_at = datetime.now(timezone.utc).isoformat()
        self.totals = {
            "success": sum(1 for result in self.results if result.status == "success"),
            "skipped": sum(1 for result in self.results if result.status == "skipped"),
            "failed": sum(1 for result in self.results if result.status == "failed"),
            "total": len(self.results),
        }

    def write(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = asdict(self)
        for result in payload["results"]:
            result["input_path"] = str(result["input_path"])
            result["output_path"] = str(result["output_path"])
        path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

