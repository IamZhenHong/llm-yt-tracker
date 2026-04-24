import json
from pathlib import Path
from unittest.mock import MagicMock
import pytest
from src.fetch_videos import (
    get_uploads_playlist_id,
    list_playlist_video_ids,
    fetch_video_durations,
    iso8601_duration_to_seconds,
    diff_against_state,
    fetch_new_videos,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_fixture(name):
    return json.loads((FIXTURES / name).read_text())


def test_get_uploads_playlist_id():
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = load_fixture(
        "youtube_channels_response.json"
    )
    assert get_uploads_playlist_id(youtube, "UCxxx") == "UUxxx"


def test_list_playlist_video_ids_returns_newest_first():
    youtube = MagicMock()
    youtube.playlistItems.return_value.list.return_value.execute.return_value = load_fixture(
        "youtube_playlist_items_response.json"
    )
    items = list_playlist_video_ids(youtube, "UUxxx", max_results=10)
    assert [i["video_id"] for i in items] == ["vid_newest", "vid_middle", "vid_oldest"]
    assert items[0]["title"] == "Newest video"


def test_iso8601_duration_to_seconds():
    assert iso8601_duration_to_seconds("PT10M30S") == 630
    assert iso8601_duration_to_seconds("PT1H2M3S") == 3723
    assert iso8601_duration_to_seconds("PT45S") == 45
    assert iso8601_duration_to_seconds("PT2H") == 7200


def test_fetch_video_durations_returns_seconds_per_id():
    youtube = MagicMock()
    youtube.videos.return_value.list.return_value.execute.return_value = load_fixture(
        "youtube_videos_response.json"
    )
    result = fetch_video_durations(youtube, ["vid_newest", "vid_middle", "vid_oldest"])
    assert result == {"vid_newest": 630, "vid_middle": 240, "vid_oldest": 3723}


def test_diff_against_state_empty_state_returns_top_n():
    items = [
        {"video_id": "a", "title": "A"},
        {"video_id": "b", "title": "B"},
        {"video_id": "c", "title": "C"},
        {"video_id": "d", "title": "D"},
    ]
    new_items = diff_against_state(items, last_seen=None, backfill=2)
    assert [i["video_id"] for i in new_items] == ["a", "b"]


def test_diff_against_state_with_last_seen_returns_only_newer():
    items = [
        {"video_id": "a", "title": "A"},
        {"video_id": "b", "title": "B"},
        {"video_id": "c", "title": "C"},
    ]
    new_items = diff_against_state(items, last_seen="b", backfill=10)
    assert [i["video_id"] for i in new_items] == ["a"]


def test_diff_against_state_last_seen_not_in_list_returns_all():
    items = [{"video_id": "a", "title": "A"}]
    new_items = diff_against_state(items, last_seen="unknown", backfill=10)
    assert [i["video_id"] for i in new_items] == ["a"]
