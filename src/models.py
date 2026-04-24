from typing import Literal
from pydantic import BaseModel


class VideoRef(BaseModel):
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    published_at: str
    url: str
    duration_seconds: int


class ExtractionResult(BaseModel):
    speakers: list[str]
    summary: str
    topics: list[str]
    key_claims: list[str]


class VideoRecord(BaseModel):
    video_id: str
    channel_id: str
    channel_name: str
    title: str
    published_at: str
    url: str
    duration_seconds: int
    transcript_source: Literal["captions", "unavailable"]
    speakers: list[str]
    summary: str
    topics: list[str]
    key_claims: list[str]
    processed_at: str
