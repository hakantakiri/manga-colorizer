from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from PIL import Image

from manga_colorist.models import ColorizationRequest


class BaseColorizer(ABC):
    name: str

    @abstractmethod
    def colorize(self, image: Image.Image, request: ColorizationRequest) -> Image.Image:
        """Return a colorized RGB image."""

    @abstractmethod
    def metadata(self) -> dict[str, Any]:
        """Return model and runtime metadata suitable for the run report."""

