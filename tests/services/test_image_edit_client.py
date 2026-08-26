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


def test_generate_uploads_reference_images(tmp_path):
    """I1: every reference image must be sent to the image-edit API."""
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")
    ref_one = tmp_path / "ref1.jpg"
    ref_one.write_bytes(b"reference-one-bytes")
    ref_two = tmp_path / "ref2.jpg"
    ref_two.write_bytes(b"reference-two-bytes")

    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, content=b"rendered-image-bytes")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = HttpImageEditClient(
        api_url="https://example.test/edit", api_key="fake-key", http_client=http_client
    )

    result = client.generate(
        GenerationRequest(
            base_photo_path=photo,
            mask_overlay_path=mask,
            reference_image_paths=[ref_one, ref_two],
            prompt="add trees",
        )
    )

    assert result.image_bytes == b"rendered-image-bytes"
    body = captured["body"]
    assert b"photo-bytes" in body
    assert b"mask-bytes" in body
    assert b"reference-one-bytes" in body
    assert b"reference-two-bytes" in body
    assert body.count(b'name="reference_images"') == 2


def test_generate_with_no_reference_images_sends_no_reference_field(tmp_path):
    """I1 regression guard: the zero-reference case must still work."""
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")

    captured: dict[str, bytes] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = request.content
        return httpx.Response(200, content=b"rendered-image-bytes")

    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport)
    client = HttpImageEditClient(
        api_url="https://example.test/edit", api_key="fake-key", http_client=http_client
    )

    result = client.generate(
        GenerationRequest(
            base_photo_path=photo,
            mask_overlay_path=mask,
            reference_image_paths=[],
            prompt="add trees",
        )
    )

    assert result.image_bytes == b"rendered-image-bytes"
    assert b'name="reference_images"' not in captured["body"]


def test_close_closes_the_http_client(tmp_path):
    """I2: the HTTP client exposes explicit cleanup."""
    http_client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    client = HttpImageEditClient(
        api_url="https://example.test/edit", api_key="fake-key", http_client=http_client
    )

    client.close()

    assert http_client.is_closed
