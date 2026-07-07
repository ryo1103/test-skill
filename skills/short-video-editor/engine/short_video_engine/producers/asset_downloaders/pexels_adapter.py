from __future__ import annotations

from .base import BaseAssetProvider


class PexelsProvider(BaseAssetProvider):
    name = "pexels"
    requires_api_key = True
    api_key_env = "PEXELS_API_KEY"
