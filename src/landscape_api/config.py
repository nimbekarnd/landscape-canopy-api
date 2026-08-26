from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class Settings:
    data_dir: Path


def get_settings() -> Settings:
    data_dir = Path(os.environ.get("LANDSCAPE_DATA_DIR", "./data"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return Settings(data_dir=data_dir)
