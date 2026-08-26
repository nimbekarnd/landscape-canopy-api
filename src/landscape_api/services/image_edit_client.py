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
