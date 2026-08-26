import re
from pathlib import Path
from typing import Protocol

from landscape_api.models import Season


class ReferenceImageProvider(Protocol):
    def fetch(self, common_name: str, season: Season) -> bytes | None: ...


def _cache_key(common_name: str, season: Season) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", common_name.lower()).strip("-")
    return f"{slug}_{season.value}.jpg"


class CachingReferenceImageService:
    def __init__(self, provider: ReferenceImageProvider, cache_dir: Path):
        self._provider = provider
        self._cache_dir = cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def get_reference_image(self, common_name: str, season: Season) -> Path | None:
        cache_path = self._cache_dir / _cache_key(common_name, season)
        if cache_path.exists():
            return cache_path

        image_bytes = self._provider.fetch(common_name, season)
        if image_bytes is None:
            return None

        cache_path.write_bytes(image_bytes)
        return cache_path
