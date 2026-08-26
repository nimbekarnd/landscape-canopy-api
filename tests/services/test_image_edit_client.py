import base64
import json
from pathlib import Path

import httpx
import pytest

from landscape_api.services.image_edit_client import (
    GeminiImageEditClient,
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


def _gemini_success_response(image_bytes: bytes) -> dict:
    return {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {"text": "Here is the rendered yard."},
                        {
                            "inlineData": {
                                "mimeType": "image/jpeg",
                                "data": base64.b64encode(image_bytes).decode(),
                            }
                        },
                    ]
                }
            }
        ]
    }


def _make_request(tmp_path, reference_image_paths=None):
    photo = tmp_path / "photo.jpg"
    photo.write_bytes(b"photo-bytes")
    mask = tmp_path / "mask.png"
    mask.write_bytes(b"mask-bytes")
    return GenerationRequest(
        base_photo_path=photo,
        mask_overlay_path=mask,
        reference_image_paths=reference_image_paths or [],
        prompt="add trees",
    )


def test_gemini_generate_returns_decoded_image_bytes_on_success(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_gemini_success_response(b"rendered-image-bytes"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = GeminiImageEditClient(api_key="fake-key", http_client=http_client)

    result = client.generate(_make_request(tmp_path))

    assert result.image_bytes == b"rendered-image-bytes"


def test_gemini_generate_sends_correct_request_shape(tmp_path):
    captured = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_gemini_success_response(b"rendered-image-bytes"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = GeminiImageEditClient(api_key="fake-key", http_client=http_client)

    ref = tmp_path / "ref.jpg"
    ref.write_bytes(b"reference-bytes")
    client.generate(_make_request(tmp_path, reference_image_paths=[ref]))

    assert "gemini-2.5-flash-image" in captured["url"]
    assert captured["headers"]["x-goog-api-key"] == "fake-key"
    parts = captured["body"]["contents"][0]["parts"]
    assert parts[0] == {"text": "add trees"}
    inline_datas = [p["inlineData"]["data"] for p in parts[1:]]
    assert base64.b64encode(b"photo-bytes").decode() in inline_datas
    assert base64.b64encode(b"mask-bytes").decode() in inline_datas
    assert base64.b64encode(b"reference-bytes").decode() in inline_datas


def test_gemini_generate_raises_on_non_2xx(tmp_path):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, content=b"server error")

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = GeminiImageEditClient(api_key="fake-key", http_client=http_client)

    with pytest.raises(ImageEditError):
        client.generate(_make_request(tmp_path))


def test_gemini_generate_raises_when_response_has_no_image(tmp_path):
    """A safety-blocked or text-only response must not silently succeed."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"candidates": [{"content": {"parts": [{"text": "Sorry, I can't do that."}]}}]},
        )

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = GeminiImageEditClient(api_key="fake-key", http_client=http_client)

    with pytest.raises(ImageEditError, match="no image"):
        client.generate(_make_request(tmp_path))


def test_gemini_generate_raises_without_a_request_when_api_key_missing(tmp_path):
    calls = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        calls["count"] += 1
        return httpx.Response(200, json=_gemini_success_response(b"x"))

    http_client = httpx.Client(transport=httpx.MockTransport(handler))
    client = GeminiImageEditClient(api_key="", http_client=http_client)

    with pytest.raises(ImageEditError, match="key"):
        client.generate(_make_request(tmp_path))

    assert calls["count"] == 0


def test_gemini_close_closes_the_http_client():
    http_client = httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200)))
    client = GeminiImageEditClient(api_key="fake-key", http_client=http_client)

    client.close()

    assert http_client.is_closed
