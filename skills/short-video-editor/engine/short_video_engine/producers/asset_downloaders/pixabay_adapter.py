from __future__ import annotations

from .base import BaseAssetProvider


class PixabayProvider(BaseAssetProvider):
    name = "pixabay"
    requires_api_key = True
    api_key_env = "PIXABAY_API_KEY"
