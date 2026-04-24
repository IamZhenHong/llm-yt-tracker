from pathlib import Path
import yaml
from pydantic import BaseModel


class Channel(BaseModel):
    name: str
    handle: str
    id: str = ""


class Models(BaseModel):
    extraction: str
    judge: str


class Thresholds(BaseModel):
    transcript_max_chars: int
    long_video_seconds: int
    distinctive_signatures_min_videos: int


class Config(BaseModel):
    channels: list[Channel]
    backfill_per_channel: int
    min_duration_seconds: int
    models: Models
    thresholds: Thresholds


def load_config(path: Path = Path("config.yaml")) -> Config:
    with open(path) as f:
        data = yaml.safe_load(f)
    return Config.model_validate(data)
