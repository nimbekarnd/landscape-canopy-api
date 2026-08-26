from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path

    def photos_dir(self) -> Path:
        path = self.data_dir / "photos"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def renders_dir(self) -> Path:
        path = self.data_dir / "renders"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def reference_cache_dir(self) -> Path:
        path = self.data_dir / "reference_cache"
        path.mkdir(parents=True, exist_ok=True)
        return path


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("LANDSCAPE_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(data_dir=data_dir)
