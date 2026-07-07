from __future__ import annotations

from .base import BaseAssetProvider


class CoverrProvider(BaseAssetProvider):
    name = "coverr"
    requires_api_key = True
    api_key_env = "COVERR_API_KEY"
