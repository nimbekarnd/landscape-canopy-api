from landscape_api.models import Season
from landscape_api.services.reference_images import CachingReferenceImageService


class FakeProvider:
    def __init__(self, image_bytes: bytes | None):
        self.image_bytes = image_bytes
        self.calls = 0

    def fetch(self, common_name: str, season: Season) -> bytes | None:
        self.calls += 1
        return self.image_bytes


def test_returns_cached_path_on_second_call_without_refetching(tmp_path):
    provider = FakeProvider(b"fake-image-bytes")
    service = CachingReferenceImageService(provider=provider, cache_dir=tmp_path)

    first = service.get_reference_image("Red Maple", Season.FALL)
    second = service.get_reference_image("Red Maple", Season.FALL)

    assert first == second
    assert first.exists()
    assert provider.calls == 1  # cached on the second call


def test_returns_none_when_provider_has_no_image(tmp_path):
    provider = FakeProvider(None)
    service = CachingReferenceImageService(provider=provider, cache_dir=tmp_path)

    result = service.get_reference_image("Unknown Shrub", Season.WINTER)

    assert result is None
