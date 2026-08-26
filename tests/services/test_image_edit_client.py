from pathlib import Path

import httpx
import pytest

from landscape_api.services.image_edit_client import (
    GenerationRequest,
    HttpImageEditClient,
    ImageEditError,
)


def test_generate_returns_image_bytes_on_success(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"rendered-image-bytes")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = HttpImageEditClient(api_url="https://example.test/edit", api_key="fake-key", http_client=http_client)

    result = client.generate(
        GenerationRequest(
            base_photo_path=photo,
            mask_overlay_path=mask,
            reference_image_paths=[],
            prompt="add trees",
        )
    )

    assert result.image_bytes == b"rendered-image-bytes"


def test_generate_raises_image_edit_error_on_failure(tmp_path):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"server error")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = HttpImageEditClient(api_url="https://example.test/edit", api_key="fake-key", http_client=http_client)

    with pytest.raises(ImageEditError):
        client.generate(
            GenerationRequest(
                base_photo_path=photo,
                mask_overlay_path=mask,
                reference_image_paths=[],
                prompt="add trees",
            )
        )
