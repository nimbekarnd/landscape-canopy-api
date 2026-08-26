import base64
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx


@dataclass
class GenerationRequest:
    base_photo_path: Path
    mask_overlay_path: Path
    reference_image_paths: list[Path] = field(default_factory=list)
    prompt: str = ""


@dataclass
class GenerationResult:
    image_bytes: bytes


class ImageEditError(Exception):
    pass


class ImageEditClient(Protocol):
    def generate(self, request: GenerationRequest) -> GenerationResult: ...


class HttpImageEditClient:
    def __init__(self, api_url: str, api_key: str, http_client: httpx.Client | None = None):
        self._api_url = api_url
        self._api_key = api_key
        self._http_client = http_client or httpx.Client(timeout=60.0)

    def close(self) -> None:
        self._http_client.close()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        # A list of tuples (rather than a dict) so the repeated
        # "reference_images" multipart field can carry every reference image.
        files_list = [
            ("base_photo", request.base_photo_path.read_bytes()),
            ("mask_overlay", request.mask_overlay_path.read_bytes()),
        ] + [
            ("reference_images", path.read_bytes())
            for path in request.reference_image_paths
        ]
        data = {"prompt": request.prompt}
        headers = {"Authorization": f"Bearer {self._api_key}"}

        try:
            response = self._http_client.post(
                self._api_url, data=data, files=files_list, headers=headers
            )
        except httpx.HTTPError as exc:
            raise ImageEditError(f"Transport error calling image-edit API: {exc}") from exc

        if response.status_code >= 300:
            raise ImageEditError(
                f"Image-edit API returned {response.status_code}: {response.text[:200]}"
            )

        return GenerationResult(image_bytes=response.content)


def _mime_type_for(path: Path) -> str:
    return "image/png" if path.suffix.lower() == ".png" else "image/jpeg"


def _inline_data_part(path: Path) -> dict:
    return {
        "inlineData": {
            "mimeType": _mime_type_for(path),
            "data": base64.b64encode(path.read_bytes()).decode("ascii"),
        }
    }


class GeminiImageEditClient:
    """Calls Google's Gemini `generateContent` API for multimodal image editing.

    Sends the base photo, the zone mask, and any reference images as inline
    base64 image parts alongside the text prompt in a single request — this
    is Gemini's actual request contract, distinct from the generic
    multipart-form shape ``HttpImageEditClient`` uses for other providers.
    """

    API_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(
        self,
        api_key: str,
        model: str = "gemini-2.5-flash-image",
        http_client: httpx.Client | None = None,
    ):
        self._api_key = api_key
        self._model = model
        self._http_client = http_client or httpx.Client(timeout=120.0)

    def close(self) -> None:
        self._http_client.close()

    def generate(self, request: GenerationRequest) -> GenerationResult:
        if not self._api_key:
            raise ImageEditError("No Gemini API key configured.")

        parts = [{"text": request.prompt}]
        parts.append(_inline_data_part(request.base_photo_path))
        parts.append(_inline_data_part(request.mask_overlay_path))
        parts.extend(_inline_data_part(p) for p in request.reference_image_paths)

        url = f"{self.API_BASE}/{self._model}:generateContent"
        headers = {"x-goog-api-key": self._api_key, "Content-Type": "application/json"}
        body = {"contents": [{"parts": parts}]}

        try:
            response = self._http_client.post(url, headers=headers, json=body)
        except httpx.HTTPError as exc:
            raise ImageEditError(f"Transport error calling Gemini API: {exc}") from exc

        if response.status_code >= 300:
            raise ImageEditError(
                f"Gemini API returned {response.status_code}: {response.text[:200]}"
            )

        image_bytes = self._extract_image_bytes(response.json())
        if image_bytes is None:
            raise ImageEditError(
                "Gemini response contained no image data (it may have been "
                "safety-blocked or returned text only)."
            )
        return GenerationResult(image_bytes=image_bytes)

    @staticmethod
    def _extract_image_bytes(payload: dict) -> bytes | None:
        for candidate in payload.get("candidates", []):
            for part in candidate.get("content", {}).get("parts", []):
                inline = part.get("inlineData") or part.get("inline_data")
                if inline and inline.get("data"):
                    return base64.b64decode(inline["data"])
        return None
