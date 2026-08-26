import uuid
from dataclasses import dataclass
from pathlib import Path

from landscape_api.models import Season
from landscape_api.services.image_edit_client import (
    GenerationRequest,
    ImageEditClient,
    ImageEditError,
)
from landscape_api.services.mask_overlay import build_mask_overlay
from landscape_api.services.prompt_builder import build_prompt
from landscape_api.services.reference_images import CachingReferenceImageService


@dataclass
class RenderOutcome:
    status: str
    image_path: Path | None
    error: str | None
    missing_species: list[str]


class GenerationOrchestrator:
    def __init__(
        self,
        reference_service: CachingReferenceImageService,
        image_edit_client: ImageEditClient,
        renders_dir: Path,
    ):
        self._reference_service = reference_service
        self._image_edit_client = image_edit_client
        self._renders_dir = renders_dir
        self._renders_dir.mkdir(parents=True, exist_ok=True)

    def close(self) -> None:
        """Release resources held by the image-edit client, if it holds any."""
        close = getattr(self._image_edit_client, "close", None)
        if close is not None:
            close()

    def generate_for_season(self, project, zones: list, season: Season) -> RenderOutcome:
        missing_species: list[str] = []

        # A failure anywhere in a season's processing (reference lookup, mask
        # building, prompt building, or the API call) must degrade to a failed
        # outcome for that season only -- never propagate and fail the whole
        # multi-season render request.
        try:
            reference_paths: list[Path] = []

            for zone in zones:
                for entry in zone.palette_entries:
                    path = self._reference_service.get_reference_image(
                        entry.species.common_name, season
                    )
                    if path is None:
                        missing_species.append(entry.species.common_name)
                    else:
                        reference_paths.append(path)

            mask_path = self._renders_dir / f"mask-{uuid.uuid4().hex}.png"
            build_mask_overlay(Path(project.photo_path), zones, mask_path)

            prompt = build_prompt(zones, season, missing_species)
            request = GenerationRequest(
                base_photo_path=Path(project.photo_path),
                mask_overlay_path=mask_path,
                reference_image_paths=reference_paths,
                prompt=prompt,
            )

            last_error: str | None = None
            for _ in range(2):  # one attempt + one retry
                try:
                    result = self._image_edit_client.generate(request)
                    image_path = self._renders_dir / f"render-{uuid.uuid4().hex}.jpg"
                    image_path.write_bytes(result.image_bytes)
                    return RenderOutcome(
                        status="succeeded",
                        image_path=image_path,
                        error=None,
                        missing_species=missing_species,
                    )
                except ImageEditError as exc:
                    last_error = str(exc)

            return RenderOutcome(
                status="failed",
                image_path=None,
                error=last_error,
                missing_species=missing_species,
            )
        except Exception as exc:  # noqa: BLE001 - deliberate per-season isolation
            return RenderOutcome(
                status="failed",
                image_path=None,
                error=str(exc) or type(exc).__name__,
                missing_species=missing_species,
            )
