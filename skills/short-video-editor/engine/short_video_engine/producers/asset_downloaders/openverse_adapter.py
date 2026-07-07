from __future__ import annotations

from typing import Any

from .base import BaseAssetProvider


class OpenverseProvider(BaseAssetProvider):
    name = "openverse"

    def search(self, query: str, wanted_visuals: list[str], avoid_visuals: list[str], required_entities: list[str], limit: int) -> list[dict[str, Any]]:
        del query, wanted_visuals, avoid_visuals, required_entities, limit
        # Openverse's public API exposes images and audio. Static images cannot
        # satisfy S3 video_broll, so this provider intentionally returns no
        # candidates instead of misclassifying images as video evidence.
        return []
