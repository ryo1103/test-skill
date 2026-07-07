"""Asset downloader adapters for S3 asset sourcing."""

from .base import PROVIDER_LADDER, BaseAssetProvider, ProviderAttempt

__all__ = ["BaseAssetProvider", "ProviderAttempt", "PROVIDER_LADDER"]
