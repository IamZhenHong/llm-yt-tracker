# LLM YouTube Landscape Tracker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an automated system that tracks 8 LLM-focused YouTube channels, extracts structured metadata from transcripts, and publishes a narrative-style public page on GitHub Pages that stays up to date via a daily GitHub Actions cron.

**Architecture:** Python pipeline reads a config of channels, diffs YouTube uploads against `data/state.json`, fetches captions via `youtube-transcript-api`, runs `gpt-4o-mini` with Structured Outputs to get `summary`, `topics`, `key_claims`, writes everything to JSON files in `/data`, derives `graph.json` and `signatures.json`, runs LLM-as-judge eval, commits, and pushes. A separate Actions job deploys `/site` to Pages with `/data` copied in.

**Tech Stack:** Python 3.11, pytest, `google-api-python-client`, `youtube-transcript-api`, `openai` SDK with Pydantic, `pyyaml`, vanilla HTML/CSS/JS, D3 v7 (CDN), GitHub Actions.

**Working directory:** `/Users/zhenhongseng/projects/tadreamk/llm-yt-tracker/` (already initialized as a git repo with the design spec committed).

---

## File Structure

**Backend (`src/`)**
- `src/__init__.py` — empty, makes `src` importable
- `src/config.py` — loads + validates `config.yaml`
- `src/models.py` — Pydantic models: `VideoRef`, `ExtractionResult`, `VideoRecord`
- `src/resolve_channels.py` — one-off: handles → channel IDs, writes back to `config.yaml`
- `src/fetch_videos.py` — uploads-playlist lookup, diff against state, returns new `VideoRef`s
- `src/transcribe.py` — `youtube-transcript-api` wrapper
- `src/extract.py` — OpenAI Structured Outputs extraction
- `src/build_graph.py` — pure: `videos.json` → `graph.json`
- `src/build_signatures.py` — pure: `videos.json` → `signatures.json`
- `src/eval.py` — LLM-as-judge metrics, writes `eval.json`
- `src/pipeline.py` — orchestrator; entrypoint is `python -m src.pipeline`

**Tests (`tests/`)**
- `tests/conftest.py` — shared fixtures
- `tests/fixtures/` — canned API responses, sample transcripts
- `tests/test_<module>.py` — one per source module

**Config / infra**
- `requirements.txt`
- `config.yaml`
- `.gitignore`, `.env.example`, `pytest.ini`

**Data (`data/`)**
- Initially: empty `videos.json` (`[]`), empty `state.json` (`{}`)
- Generated: `graph.json`, `signatures.json`, `eval.json`

**Frontend (`site/`)**
- `site/index.html`, `site/assets/app.js`, `site/assets/style.css`
- D3 loaded from CDN

**Docs**
- `README.md` (submission report)
- `docs/evaluation.md` (eval results, written after first run)

**CI**
- `.github/workflows/update.yml` — cron + manual trigger, runs pipeline, commits
- `.github/workflows/deploy.yml` — push → Pages deploy

---

## Task 1: Project Scaffolding

**Files:**
- Create: `requirements.txt`, `config.yaml`, `.gitignore`, `.env.example`, `pytest.ini`
- Create: `src/__init__.py`, `tests/__init__.py`, `tests/conftest.py`
- Create: `data/videos.json`, `data/state.json`

- [ ] **Step 1: Create `requirements.txt`**

```
google-api-python-client==2.151.0
youtube-transcript-api==1.2.4
openai==1.60.0
pydantic==2.9.0
pyyaml==6.0.2
python-dotenv==1.0.1
pytest==8.3.3
pytest-mock==3.14.0
```

- [ ] **Step 2: Create `config.yaml`** (channel IDs blank; `resolve_channels.py` fills them)

```yaml
channels:
  - name: "Andrej Karpathy"
    handle: "@AndrejKarpathy"
    id: ""
  - name: "Yannic Kilcher"
    handle: "@YannicKilcher"
    id: ""
  - name: "AI Explained"
    handle: "@aiexplained-official"
    id: ""
  - name: "Machine Learning Street Talk"
    handle: "@MachineLearningStreetTalk"
    id: ""
  - name: "Dwarkesh Patel"
    handle: "@DwarkeshPatel"
    id: ""
  - name: "Sam Witteveen"
    handle: "@SamWitteveen"
    id: ""
  - name: "1littlecoder"
    handle: "@1littlecoder"
    id: ""
  - name: "Matthew Berman"
    handle: "@matthew_berman"
    id: ""

backfill_per_channel: 3
min_duration_seconds: 300

models:
  extraction: "gpt-4o-mini"
  judge: "gpt-4o-mini"

thresholds:
  transcript_max_chars: 120000
  long_video_seconds: 7200
  distinctive_signatures_min_videos: 10
```

- [ ] **Step 3: Create `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.env
.venv/
venv/
.DS_Store
*.egg-info/
```

- [ ] **Step 4: Create `.env.example`**

```
OPENAI_API_KEY=sk-...
YOUTUBE_API_KEY=AIza...
```

- [ ] **Step 5: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v --tb=short
```

- [ ] **Step 6: Create empty init files**

Run: `touch src/__init__.py tests/__init__.py tests/conftest.py`

- [ ] **Step 7: Create empty data files**

`data/videos.json`:
```json
[]
```

`data/state.json`:
```json
{}
```

- [ ] **Step 8: Install deps locally in a venv**

Run:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Expected: installs without error.

- [ ] **Step 9: Commit**

```bash
git add requirements.txt config.yaml .gitignore .env.example pytest.ini src/__init__.py tests/__init__.py tests/conftest.py data/videos.json data/state.json
git commit -m "chore: project scaffolding"
```

---

## Task 2: Config Loader

**Files:**
- Create: `src/config.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path
import textwrap
from src.config import load_config


def test_load_config_parses_channels_and_thresholds(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        channels:
          - name: "Andrej Karpathy"
            handle: "@AndrejKarpathy"
            id: "UCxxx"
        backfill_per_channel: 3
        min_duration_seconds: 300
        models:
          extraction: "gpt-4o-mini"
          judge: "gpt-4o-mini"
        thresholds:
          transcript_max_chars: 120000
          long_video_seconds: 7200
          distinctive_signatures_min_videos: 10
    """))

    cfg = load_config(cfg_file)

    assert cfg.backfill_per_channel == 3
    assert cfg.min_duration_seconds == 300
    assert cfg.models.extraction == "gpt-4o-mini"
    assert cfg.thresholds.transcript_max_chars == 120000
    assert len(cfg.channels) == 1
    assert cfg.channels[0].handle == "@AndrejKarpathy"
    assert cfg.channels[0].id == "UCxxx"
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_config.py -v`
Expected: `ModuleNotFoundError: No module named 'src.config'` or `ImportError`.

- [ ] **Step 3: Implement `src/config.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_config.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/config.py tests/test_config.py
git commit -m "feat: config loader with pydantic validation"
```

---

## Task 3: Pydantic Models

**Files:**
- Create: `src/models.py`
- Test: `tests/test_models.py`

- [ ] **Step 1: Write the failing test**

`tests/test_models.py`:
```python
from src.models import VideoRef, ExtractionResult, VideoRecord


def test_video_ref_minimum_fields():
    ref = VideoRef(
        video_id="abc123",
        channel_id="UCxxx",
        channel_name="Karpathy",
        title="Test",
        published_at="2026-04-20T14:00:00Z",
        url="https://www.youtube.com/watch?v=abc123",
        duration_seconds=1234,
    )
    assert ref.video_id == "abc123"


def test_extraction_result_defaults_and_validation():
    result = ExtractionResult(
        speakers=["Karpathy"],
        summary="A summary.",
        topics=["scaling laws"],
        key_claims=["Claim 1"],
    )
    assert result.speakers == ["Karpathy"]
    assert result.topics == ["scaling laws"]


def test_video_record_unavailable_transcript_uses_empty_extraction():
    record = VideoRecord(
        video_id="abc123",
        channel_id="UCxxx",
        channel_name="Karpathy",
        title="Test",
        published_at="2026-04-20T14:00:00Z",
        url="https://www.youtube.com/watch?v=abc123",
        duration_seconds=1234,
        transcript_source="unavailable",
        speakers=[],
        summary="",
        topics=[],
        key_claims=[],
        processed_at="2026-04-24T02:00:00Z",
    )
    assert record.transcript_source == "unavailable"
    assert record.topics == []
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_models.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/models.py`**

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_models.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/models.py tests/test_models.py
git commit -m "feat: pydantic data models for pipeline"
```

---

## Task 4: Resolve Channel Handles to IDs

**Files:**
- Create: `src/resolve_channels.py`
- Test: `tests/test_resolve_channels.py`

This is a one-off utility the user runs locally: `python -m src.resolve_channels` — fetches each channel's ID via the YouTube API and rewrites `config.yaml` in place.

- [ ] **Step 1: Write the failing test**

`tests/test_resolve_channels.py`:
```python
from unittest.mock import MagicMock
from src.resolve_channels import resolve_handle_to_id


def test_resolve_handle_queries_youtube_api_and_returns_channel_id():
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {
        "items": [{"id": "UCxxx"}]
    }

    result = resolve_handle_to_id(youtube, "@AndrejKarpathy")

    assert result == "UCxxx"
    youtube.channels.return_value.list.assert_called_once_with(
        part="id", forHandle="@AndrejKarpathy"
    )


def test_resolve_handle_returns_none_when_not_found():
    youtube = MagicMock()
    youtube.channels.return_value.list.return_value.execute.return_value = {"items": []}

    result = resolve_handle_to_id(youtube, "@missing")

    assert result is None
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_resolve_channels.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/resolve_channels.py`**

```python
import os
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv
from googleapiclient.discovery import build


def resolve_handle_to_id(youtube, handle: str) -> str | None:
    """Return channel ID for a @handle, or None if not found."""
    resp = youtube.channels().list(part="id", forHandle=handle).execute()
    items = resp.get("items") or []
    if not items:
        return None
    return items[0]["id"]


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY not set", file=sys.stderr)
        return 1

    youtube = build("youtube", "v3", developerKey=api_key)
    cfg_path = Path("config.yaml")
    cfg = yaml.safe_load(cfg_path.read_text())

    for channel in cfg["channels"]:
        if channel.get("id"):
            print(f"skip {channel['handle']} (id already set)")
            continue
        cid = resolve_handle_to_id(youtube, channel["handle"])
        if cid is None:
            print(f"WARN: could not resolve {channel['handle']}")
            continue
        channel["id"] = cid
        print(f"{channel['handle']} -> {cid}")

    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_resolve_channels.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/resolve_channels.py tests/test_resolve_channels.py
git commit -m "feat: resolve channel handles to IDs via YouTube API"
```

- [ ] **Step 6: Pause for user action**

The user must run this once locally:
```bash
cp .env.example .env
# fill in YOUTUBE_API_KEY
source .venv/bin/activate
python -m src.resolve_channels
git add config.yaml
git commit -m "chore: populate channel IDs"
```

**Do not proceed to Task 5 until channel IDs are populated in `config.yaml`.**

---

## Task 5: Fetch New Videos with State Diffing

**Files:**
- Create: `src/fetch_videos.py`
- Test: `tests/test_fetch_videos.py`, `tests/fixtures/youtube_channels_response.json`, `tests/fixtures/youtube_playlist_items_response.json`

- [ ] **Step 1: Create fixture files**

`tests/fixtures/youtube_channels_response.json`:
```json
{
  "items": [
    {
      "id": "UCxxx",
      "contentDetails": {
        "relatedPlaylists": {
          "uploads": "UUxxx"
        }
      }
    }
  ]
}
```

`tests/fixtures/youtube_playlist_items_response.json`:
```json
{
  "items": [
    {
      "contentDetails": {
        "videoId": "vid_newest",
        "videoPublishedAt": "2026-04-23T10:00:00Z"
      },
      "snippet": {
        "title": "Newest video",
        "channelId": "UCxxx"
      }
    },
    {
      "contentDetails": {
        "videoId": "vid_middle",
        "videoPublishedAt": "2026-04-22T10:00:00Z"
      },
      "snippet": {
        "title": "Middle video",
        "channelId": "UCxxx"
      }
    },
    {
      "contentDetails": {
        "videoId": "vid_oldest",
        "videoPublishedAt": "2026-04-21T10:00:00Z"
      },
      "snippet": {
        "title": "Oldest video",
        "channelId": "UCxxx"
      }
    }
  ]
}
```

`tests/fixtures/youtube_videos_response.json`:
```json
{
  "items": [
    {"id": "vid_newest", "contentDetails": {"duration": "PT10M30S"}},
    {"id": "vid_middle", "contentDetails": {"duration": "PT4M"}},
    {"id": "vid_oldest", "contentDetails": {"duration": "PT1H2M3S"}}
  ]
}
```

- [ ] **Step 2: Write the failing test**

`tests/test_fetch_videos.py`:
```python
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
```

- [ ] **Step 3: Run test and verify it fails**

Run: `pytest tests/test_fetch_videos.py -v`
Expected: `ModuleNotFoundError: No module named 'src.fetch_videos'`.

- [ ] **Step 4: Implement `src/fetch_videos.py`**

```python
import re
from src.models import VideoRef

ISO_DURATION_RE = re.compile(
    r"PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?"
)


def iso8601_duration_to_seconds(duration: str) -> int:
    match = ISO_DURATION_RE.fullmatch(duration)
    if not match:
        return 0
    h = int(match.group("h") or 0)
    m = int(match.group("m") or 0)
    s = int(match.group("s") or 0)
    return h * 3600 + m * 60 + s


def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items") or []
    if not items:
        raise ValueError(f"no channel found for id {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_playlist_video_ids(youtube, playlist_id: str, max_results: int = 10) -> list[dict]:
    """Return items newest-first with minimal fields."""
    resp = (
        youtube.playlistItems()
        .list(part="contentDetails,snippet", playlistId=playlist_id, maxResults=max_results)
        .execute()
    )
    items = []
    for raw in resp.get("items", []):
        items.append(
            {
                "video_id": raw["contentDetails"]["videoId"],
                "published_at": raw["contentDetails"]["videoPublishedAt"],
                "title": raw["snippet"]["title"],
                "channel_id": raw["snippet"]["channelId"],
            }
        )
    return items


def fetch_video_durations(youtube, video_ids: list[str]) -> dict[str, int]:
    if not video_ids:
        return {}
    resp = (
        youtube.videos()
        .list(part="contentDetails", id=",".join(video_ids))
        .execute()
    )
    out = {}
    for item in resp.get("items", []):
        out[item["id"]] = iso8601_duration_to_seconds(item["contentDetails"]["duration"])
    return out


def diff_against_state(items: list[dict], last_seen: str | None, backfill: int) -> list[dict]:
    """Return items newer than last_seen (or first `backfill` if last_seen is empty/unknown)."""
    if not last_seen:
        return items[:backfill]
    new_items = []
    for item in items:
        if item["video_id"] == last_seen:
            return new_items
        new_items.append(item)
    # last_seen not found in the fetched window → treat everything as new
    return new_items


def fetch_new_videos(
    youtube,
    channel_id: str,
    channel_name: str,
    last_seen: str | None,
    backfill: int,
    min_duration_seconds: int,
) -> list[VideoRef]:
    uploads_id = get_uploads_playlist_id(youtube, channel_id)
    # Fetch enough to cover backfill even after min_duration filter
    items = list_playlist_video_ids(youtube, uploads_id, max_results=max(backfill * 3, 10))
    new_items = diff_against_state(items, last_seen, backfill * 3)
    if not new_items:
        return []
    durations = fetch_video_durations(youtube, [i["video_id"] for i in new_items])
    refs: list[VideoRef] = []
    for item in new_items:
        dur = durations.get(item["video_id"], 0)
        if dur < min_duration_seconds:
            continue
        refs.append(
            VideoRef(
                video_id=item["video_id"],
                channel_id=channel_id,
                channel_name=channel_name,
                title=item["title"],
                published_at=item["published_at"],
                url=f"https://www.youtube.com/watch?v={item['video_id']}",
                duration_seconds=dur,
            )
        )
        if len(refs) >= backfill:
            break
    return refs
```

- [ ] **Step 5: Run tests**

Run: `pytest tests/test_fetch_videos.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add src/fetch_videos.py tests/test_fetch_videos.py tests/fixtures/youtube_channels_response.json tests/fixtures/youtube_playlist_items_response.json tests/fixtures/youtube_videos_response.json
git commit -m "feat: fetch new videos with state diffing and duration filter"
```

---

## Task 6: Transcribe via Captions

**Files:**
- Create: `src/transcribe.py`
- Test: `tests/test_transcribe.py`

- [ ] **Step 1: Write the failing test**

`tests/test_transcribe.py`:
```python
import pytest
from src.transcribe import get_transcript


def test_get_transcript_returns_text_when_captions_available(mocker):
    mock_api = mocker.patch("src.transcribe.YouTubeTranscriptApi")
    mock_api.return_value.fetch.return_value.to_raw_data.return_value = [
        {"text": "Hello world.", "start": 0.0, "duration": 1.0},
        {"text": "This is a test.", "start": 1.0, "duration": 2.0},
    ]

    text, source = get_transcript("abc123")

    assert source == "captions"
    assert "Hello world" in text
    assert "This is a test" in text


def test_get_transcript_returns_none_on_failure(mocker):
    mock_api = mocker.patch("src.transcribe.YouTubeTranscriptApi")
    mock_api.return_value.fetch.side_effect = Exception("no captions")

    text, source = get_transcript("abc123")

    assert text is None
    assert source == "unavailable"
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_transcribe.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/transcribe.py`**

```python
from youtube_transcript_api import YouTubeTranscriptApi


def get_transcript(video_id: str) -> tuple[str | None, str]:
    """Return (transcript_text, source). source is 'captions' on success, 'unavailable' on failure."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        segments = fetched.to_raw_data()
        text = " ".join(seg["text"].strip() for seg in segments if seg.get("text"))
        return text, "captions"
    except Exception as e:
        print(f"transcript fetch failed for {video_id}: {e}")
        return None, "unavailable"
```

- [ ] **Step 4: Run test and verify it passes**

Run: `pytest tests/test_transcribe.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/transcribe.py tests/test_transcribe.py
git commit -m "feat: captions-only transcript fetcher"
```

---

## Task 7: Structured Extraction with gpt-4o-mini

**Files:**
- Create: `src/extract.py`
- Test: `tests/test_extract.py`

- [ ] **Step 1: Write the failing test**

`tests/test_extract.py`:
```python
from unittest.mock import MagicMock
from src.extract import extract, chunk_transcript
from src.models import ExtractionResult


def test_chunk_transcript_short_returns_single_chunk():
    text = "abc" * 100
    chunks = chunk_transcript(text, max_chars=1000)
    assert chunks == [text]


def test_chunk_transcript_long_splits_at_sentences():
    # 5 sentences of ~200 chars each
    sentences = [f"Sentence number {i} " + "x" * 180 + "." for i in range(5)]
    text = " ".join(sentences)
    chunks = chunk_transcript(text, max_chars=500)
    assert len(chunks) > 1
    # No chunk should exceed budget by a wild amount
    for c in chunks:
        assert len(c) <= 600  # small slack for last sentence


def test_extract_calls_openai_with_structured_output_and_returns_result(mocker):
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock()]
    fake_completion.choices[0].message.parsed = ExtractionResult(
        speakers=["Karpathy"],
        summary="This video discusses scaling laws.",
        topics=["scaling laws", "transformers"],
        key_claims=["Larger models generalize better.", "Data quality matters more than quantity."],
    )
    fake_completion.usage = MagicMock(prompt_tokens=1000, completion_tokens=200, total_tokens=1200)
    mock_client = mocker.patch("src.extract.OpenAI")
    mock_client.return_value.beta.chat.completions.parse.return_value = fake_completion

    result, tokens = extract(
        transcript="Some transcript text.",
        title="My Title",
        channel_name="Karpathy",
        model="gpt-4o-mini",
        max_chars=120000,
        long_video_seconds=7200,
        duration_seconds=600,
    )

    assert result.topics == ["scaling laws", "transformers"]
    assert result.summary.startswith("This video")
    assert tokens == 1200
    mock_client.return_value.beta.chat.completions.parse.assert_called_once()
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_extract.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/extract.py`**

```python
import os
import re
from openai import OpenAI
from src.models import ExtractionResult


SYSTEM_PROMPT = """You extract structured metadata from YouTube video transcripts about large language models. Be precise. Only use facts supported by the transcript. Prefer canonical topic names from this list when applicable: RLHF, RLAIF, fine-tuning, LoRA, QLoRA, quantization, tokenization, scaling laws, mixture of experts, transformers, attention, context length, retrieval augmented generation, agents, tool use, function calling, reasoning, chain of thought, test-time compute, reinforcement learning, alignment, interpretability, benchmarks, evals, multimodal, vision language models, code generation, open source models, closed models, MCP, synthetic data. For topics outside this list, use a short noun phrase in lowercase. Return 3-5 key_claims that are concrete statements made in the video. Summary should be 2-4 sentences."""


def chunk_transcript(text: str, max_chars: int) -> list[str]:
    """Split on sentence boundaries so no chunk exceeds max_chars."""
    if len(text) <= max_chars:
        return [text]
    # Split on ". " to preserve rough sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent) if current else sent
    if current:
        chunks.append(current.strip())
    return chunks


def _call(
    client: OpenAI,
    model: str,
    transcript: str,
    title: str,
    channel_name: str,
    is_synthesis: bool = False,
) -> tuple[ExtractionResult, int]:
    user_prefix = (
        "Synthesize across the prior chunks.\n"
        if is_synthesis
        else ""
    )
    user = (
        f"{user_prefix}Channel: {channel_name}\nTitle: {title}\n\nTranscript:\n{transcript}"
    )
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format=ExtractionResult,
        temperature=0,
    )
    result = completion.choices[0].message.parsed
    tokens = completion.usage.total_tokens if completion.usage else 0
    return result, tokens


def extract(
    transcript: str,
    title: str,
    channel_name: str,
    model: str,
    max_chars: int,
    long_video_seconds: int,
    duration_seconds: int,
) -> tuple[ExtractionResult, int]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    total_tokens = 0

    if duration_seconds < long_video_seconds and len(transcript) <= max_chars:
        result, tokens = _call(client, model, transcript, title, channel_name)
        return result, tokens

    # Long path: chunk, extract per chunk, then synthesize
    chunks = chunk_transcript(transcript, max_chars=max_chars)
    partials: list[ExtractionResult] = []
    for chunk in chunks:
        partial, tokens = _call(client, model, chunk, title, channel_name)
        partials.append(partial)
        total_tokens += tokens

    # Synthesize: feed the concatenated summaries + all topics + all claims
    synthesis_input = "\n\n".join(
        f"Chunk {i+1} summary: {p.summary}\nTopics: {', '.join(p.topics)}\nClaims: " +
        "; ".join(p.key_claims)
        for i, p in enumerate(partials)
    )
    final, tokens = _call(client, model, synthesis_input, title, channel_name, is_synthesis=True)
    total_tokens += tokens
    return final, total_tokens
```

- [ ] **Step 4: Run tests**

Run: `pytest tests/test_extract.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/extract.py tests/test_extract.py
git commit -m "feat: OpenAI structured extraction with long-video chunking"
```

---

## Task 8: Build Graph

**Files:**
- Create: `src/build_graph.py`
- Test: `tests/test_build_graph.py`

- [ ] **Step 1: Write the failing test**

`tests/test_build_graph.py`:
```python
from src.build_graph import build_graph, normalize_topic


def test_normalize_topic_lowercases_and_strips():
    assert normalize_topic("Scaling Laws") == "scaling laws"
    assert normalize_topic("  RLHF ") == "rlhf"
    assert normalize_topic("scaling-law") == "scaling laws"  # alias map


def test_build_graph_produces_channel_and_topic_nodes_with_weighted_edges():
    videos = [
        {
            "video_id": "v1",
            "channel_id": "UC_A",
            "channel_name": "A",
            "transcript_source": "captions",
            "topics": ["Scaling Laws", "RLHF"],
        },
        {
            "video_id": "v2",
            "channel_id": "UC_A",
            "channel_name": "A",
            "transcript_source": "captions",
            "topics": ["RLHF"],
        },
        {
            "video_id": "v3",
            "channel_id": "UC_B",
            "channel_name": "B",
            "transcript_source": "captions",
            "topics": ["RLHF", "agents"],
        },
    ]
    graph = build_graph(videos)

    node_ids = {n["id"] for n in graph["nodes"]}
    assert "channel:UC_A" in node_ids
    assert "channel:UC_B" in node_ids
    assert "topic:rlhf" in node_ids
    assert "topic:scaling laws" in node_ids
    assert "topic:agents" in node_ids

    link_tuples = {(l["source"], l["target"], l["weight"]) for l in graph["links"]}
    assert ("channel:UC_A", "topic:rlhf", 2) in link_tuples
    assert ("channel:UC_A", "topic:scaling laws", 1) in link_tuples
    assert ("channel:UC_B", "topic:rlhf", 1) in link_tuples
    assert ("channel:UC_B", "topic:agents", 1) in link_tuples


def test_build_graph_excludes_unavailable_transcripts():
    videos = [
        {
            "video_id": "v1",
            "channel_id": "UC_A",
            "channel_name": "A",
            "transcript_source": "unavailable",
            "topics": [],
        }
    ]
    graph = build_graph(videos)
    # No topic nodes, but channel still appears
    assert any(n["id"] == "channel:UC_A" for n in graph["nodes"])
    assert not any(n["type"] == "topic" for n in graph["nodes"])
    assert graph["links"] == []
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_build_graph.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/build_graph.py`**

```python
from collections import defaultdict


TOPIC_ALIASES = {
    "scaling-law": "scaling laws",
    "scaling law": "scaling laws",
    "moe": "mixture of experts",
    "rag": "retrieval augmented generation",
    "cot": "chain of thought",
    "vlms": "vision language models",
    "vlm": "vision language models",
    "rl": "reinforcement learning",
    "fine tuning": "fine-tuning",
    "finetuning": "fine-tuning",
}


def normalize_topic(raw: str) -> str:
    t = raw.strip().lower()
    return TOPIC_ALIASES.get(t, t)


def build_graph(videos: list[dict]) -> dict:
    channel_video_counts: dict[str, int] = defaultdict(int)
    channel_names: dict[str, str] = {}
    topic_counts: dict[str, int] = defaultdict(int)
    edge_counts: dict[tuple[str, str], int] = defaultdict(int)

    for v in videos:
        cid = v["channel_id"]
        channel_names[cid] = v["channel_name"]
        channel_video_counts[cid] += 1
        if v.get("transcript_source") != "captions":
            continue
        for raw_topic in v.get("topics", []):
            t = normalize_topic(raw_topic)
            topic_counts[t] += 1
            edge_counts[(cid, t)] += 1

    nodes = []
    for cid, count in channel_video_counts.items():
        nodes.append(
            {
                "id": f"channel:{cid}",
                "type": "channel",
                "label": channel_names[cid],
                "size": count,
            }
        )
    for topic, count in topic_counts.items():
        nodes.append(
            {
                "id": f"topic:{topic}",
                "type": "topic",
                "label": topic,
                "size": count,
            }
        )

    links = []
    for (cid, topic), weight in edge_counts.items():
        links.append(
            {
                "source": f"channel:{cid}",
                "target": f"topic:{topic}",
                "weight": weight,
            }
        )

    return {"nodes": nodes, "links": links}
```

- [ ] **Step 4: Run test and verify it passes**

Run: `pytest tests/test_build_graph.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/build_graph.py tests/test_build_graph.py
git commit -m "feat: build channel-topic graph with alias normalization"
```

---

## Task 9: Build Channel Signatures

**Files:**
- Create: `src/build_signatures.py`
- Test: `tests/test_build_signatures.py`

- [ ] **Step 1: Write the failing test**

`tests/test_build_signatures.py`:
```python
import pytest
from src.build_signatures import build_signatures


def make_video(cid, cname, topics):
    return {
        "channel_id": cid,
        "channel_name": cname,
        "transcript_source": "captions",
        "topics": topics,
    }


def test_signatures_frequency_mode_for_low_video_count():
    videos = [
        make_video("UC_A", "A", ["RLHF", "scaling laws"]),
        make_video("UC_A", "A", ["RLHF"]),
        make_video("UC_A", "A", ["agents"]),
    ]
    sigs = build_signatures(videos, distinctive_min=10)

    assert sigs["UC_A"]["mode"] == "frequency"
    assert sigs["UC_A"]["total_videos"] == 3
    topics = {t["topic"]: t for t in sigs["UC_A"]["topics"]}
    assert topics["rlhf"]["count"] == 2
    assert topics["rlhf"]["share"] == pytest.approx(2 / 4)  # 2 of 4 total topic mentions


def test_signatures_distinctive_mode_at_threshold():
    # Channel A covers only RLHF (10 videos). Channel B covers RLHF once and agents once.
    videos = [make_video("UC_A", "A", ["RLHF"]) for _ in range(10)]
    videos += [make_video("UC_B", "B", ["RLHF"]), make_video("UC_B", "B", ["agents"])]

    sigs = build_signatures(videos, distinctive_min=10)

    assert sigs["UC_A"]["mode"] == "distinctive"
    # A's RLHF share is 1.0; global RLHF share is 11/12. Distinctiveness ≈ 1.0 / (11/12) ≈ 1.09
    a_rlhf = next(t for t in sigs["UC_A"]["topics"] if t["topic"] == "rlhf")
    assert a_rlhf["distinctiveness_score"] > 1.0

    # B has too few videos → frequency mode
    assert sigs["UC_B"]["mode"] == "frequency"


def test_signatures_excludes_unavailable_videos_from_counts():
    videos = [
        make_video("UC_A", "A", ["RLHF"]),
        {
            "channel_id": "UC_A",
            "channel_name": "A",
            "transcript_source": "unavailable",
            "topics": [],
        },
    ]
    sigs = build_signatures(videos, distinctive_min=10)
    # Unavailable videos contribute to total_videos count but not topics
    assert sigs["UC_A"]["total_videos"] == 2
    assert len(sigs["UC_A"]["topics"]) == 1
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_build_signatures.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/build_signatures.py`**

```python
from collections import defaultdict
from src.build_graph import normalize_topic


def build_signatures(videos: list[dict], distinctive_min: int) -> dict:
    channel_topic_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    channel_names: dict[str, str] = {}
    channel_video_totals: dict[str, int] = defaultdict(int)
    global_topic_counts: dict[str, int] = defaultdict(int)
    global_total_mentions = 0

    for v in videos:
        cid = v["channel_id"]
        channel_names[cid] = v["channel_name"]
        channel_video_totals[cid] += 1
        if v.get("transcript_source") != "captions":
            continue
        for raw_topic in v.get("topics", []):
            t = normalize_topic(raw_topic)
            channel_topic_counts[cid][t] += 1
            global_topic_counts[t] += 1
            global_total_mentions += 1

    out: dict[str, dict] = {}
    for cid, topic_counts in channel_topic_counts.items():
        total_mentions_in_channel = sum(topic_counts.values())
        topic_entries = []
        for topic, count in topic_counts.items():
            share = count / total_mentions_in_channel if total_mentions_in_channel else 0
            entry = {"topic": topic, "count": count, "share": share}
            topic_entries.append(entry)
        # Sort by count desc
        topic_entries.sort(key=lambda x: (-x["count"], x["topic"]))

        total_videos = channel_video_totals[cid]
        if total_videos >= distinctive_min and global_total_mentions > 0:
            mode = "distinctive"
            for e in topic_entries:
                global_share = global_topic_counts[e["topic"]] / global_total_mentions
                e["distinctiveness_score"] = e["share"] / global_share if global_share else 0
            topic_entries.sort(
                key=lambda x: (-x.get("distinctiveness_score", 0), -x["count"])
            )
        else:
            mode = "frequency"

        out[cid] = {
            "channel_name": channel_names[cid],
            "total_videos": total_videos,
            "mode": mode,
            "topics": topic_entries,
        }

    # Include channels that have only unavailable videos
    for cid, total in channel_video_totals.items():
        if cid not in out:
            out[cid] = {
                "channel_name": channel_names[cid],
                "total_videos": total,
                "mode": "frequency",
                "topics": [],
            }

    return out
```

- [ ] **Step 4: Run test and verify it passes**

Run: `pytest tests/test_build_signatures.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/build_signatures.py tests/test_build_signatures.py
git commit -m "feat: build channel signatures with frequency/distinctive modes"
```

---

## Task 10: Pipeline Orchestrator

**Files:**
- Create: `src/pipeline.py`
- Test: `tests/test_pipeline.py`

- [ ] **Step 1: Write the failing test**

`tests/test_pipeline.py`:
```python
import json
from pathlib import Path
from unittest.mock import MagicMock
from src.pipeline import run_pipeline
from src.models import VideoRef, ExtractionResult


def test_run_pipeline_happy_path(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")

    # Stub fetch_new_videos to return one video per channel
    def fake_fetch_new_videos(youtube, channel_id, channel_name, last_seen, backfill, min_dur):
        return [
            VideoRef(
                video_id=f"vid_{channel_id}",
                channel_id=channel_id,
                channel_name=channel_name,
                title=f"{channel_name} video",
                published_at="2026-04-23T10:00:00Z",
                url=f"https://youtube.com/watch?v=vid_{channel_id}",
                duration_seconds=600,
            )
        ]

    mocker.patch("src.pipeline.fetch_new_videos", side_effect=fake_fetch_new_videos)
    mocker.patch(
        "src.pipeline.get_transcript",
        return_value=("Some transcript content", "captions"),
    )
    mocker.patch(
        "src.pipeline.extract",
        return_value=(
            ExtractionResult(
                speakers=["Host"],
                summary="Summary.",
                topics=["RLHF", "agents"],
                key_claims=["Claim A", "Claim B"],
            ),
            1500,
        ),
    )
    mocker.patch("src.pipeline.build", return_value=MagicMock())

    # Write a minimal config
    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
channels:
  - name: "Channel A"
    handle: "@a"
    id: "UC_A"
  - name: "Channel B"
    handle: "@b"
    id: "UC_B"
backfill_per_channel: 3
min_duration_seconds: 300
models:
  extraction: "gpt-4o-mini"
  judge: "gpt-4o-mini"
thresholds:
  transcript_max_chars: 120000
  long_video_seconds: 7200
  distinctive_signatures_min_videos: 10
"""
    )

    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "videos.json").write_text("[]")
    (data_dir / "state.json").write_text("{}")

    summary = run_pipeline(config_path=cfg_path, data_dir=data_dir)

    videos = json.loads((data_dir / "videos.json").read_text())
    state = json.loads((data_dir / "state.json").read_text())
    graph = json.loads((data_dir / "graph.json").read_text())
    sigs = json.loads((data_dir / "signatures.json").read_text())

    assert len(videos) == 2
    ids = {v["video_id"] for v in videos}
    assert ids == {"vid_UC_A", "vid_UC_B"}
    assert state["UC_A"]["last_video_id"] == "vid_UC_A"
    assert state["UC_B"]["last_video_id"] == "vid_UC_B"
    assert any(n["type"] == "topic" for n in graph["nodes"])
    assert "UC_A" in sigs
    assert summary["new_videos"] == 2
    assert summary["captions"] == 2
    assert summary["unavailable"] == 0


def test_run_pipeline_unavailable_transcript_does_not_call_extract(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("YOUTUBE_API_KEY", "test")

    def fake_fetch(youtube, channel_id, channel_name, last_seen, backfill, min_dur):
        return [
            VideoRef(
                video_id="vid_1",
                channel_id=channel_id,
                channel_name=channel_name,
                title="T",
                published_at="2026-04-23T10:00:00Z",
                url="https://youtube.com/watch?v=vid_1",
                duration_seconds=600,
            )
        ]

    mocker.patch("src.pipeline.fetch_new_videos", side_effect=fake_fetch)
    mocker.patch("src.pipeline.get_transcript", return_value=(None, "unavailable"))
    extract_mock = mocker.patch("src.pipeline.extract")
    mocker.patch("src.pipeline.build", return_value=MagicMock())

    cfg_path = tmp_path / "config.yaml"
    cfg_path.write_text(
        """
channels:
  - name: "Channel A"
    handle: "@a"
    id: "UC_A"
backfill_per_channel: 3
min_duration_seconds: 300
models:
  extraction: "gpt-4o-mini"
  judge: "gpt-4o-mini"
thresholds:
  transcript_max_chars: 120000
  long_video_seconds: 7200
  distinctive_signatures_min_videos: 10
"""
    )
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    (data_dir / "videos.json").write_text("[]")
    (data_dir / "state.json").write_text("{}")

    summary = run_pipeline(config_path=cfg_path, data_dir=data_dir)
    extract_mock.assert_not_called()
    videos = json.loads((data_dir / "videos.json").read_text())
    assert videos[0]["transcript_source"] == "unavailable"
    assert videos[0]["topics"] == []
    assert summary["unavailable"] == 1
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_pipeline.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/pipeline.py`**

```python
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from googleapiclient.discovery import build

from src.build_graph import build_graph
from src.build_signatures import build_signatures
from src.config import load_config
from src.extract import extract
from src.fetch_videos import fetch_new_videos
from src.transcribe import get_transcript


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def run_pipeline(config_path: Path = Path("config.yaml"), data_dir: Path = Path("data")) -> dict:
    cfg = load_config(config_path)

    youtube = build("youtube", "v3", developerKey=os.environ["YOUTUBE_API_KEY"])

    videos_path = data_dir / "videos.json"
    state_path = data_dir / "state.json"

    videos = json.loads(videos_path.read_text())
    state = json.loads(state_path.read_text())

    new_count = 0
    caption_count = 0
    unavailable_count = 0
    failed_extract = 0
    total_tokens = 0

    for channel in cfg.channels:
        if not channel.id:
            print(f"WARN: {channel.handle} has no id, skipping")
            continue

        last_seen = state.get(channel.id, {}).get("last_video_id") or None
        try:
            refs = fetch_new_videos(
                youtube,
                channel.id,
                channel.name,
                last_seen,
                cfg.backfill_per_channel,
                cfg.min_duration_seconds,
            )
        except Exception as e:
            print(f"ERROR fetching {channel.name}: {e}")
            continue

        if not refs:
            print(f"{channel.name}: no new videos")
            state.setdefault(channel.id, {})["last_checked"] = _now_iso()
            continue

        newest_id = refs[0].video_id

        # Process oldest-first so on partial failure we still advance state sensibly
        for ref in reversed(refs):
            print(f"{channel.name}: processing {ref.video_id} ({ref.title[:60]})")
            new_count += 1
            transcript, source = get_transcript(ref.video_id)
            record = ref.model_dump()
            record.update(
                {
                    "transcript_source": source,
                    "speakers": [],
                    "summary": "",
                    "topics": [],
                    "key_claims": [],
                    "processed_at": _now_iso(),
                }
            )
            if source == "captions" and transcript:
                caption_count += 1
                try:
                    result, tokens = extract(
                        transcript=transcript,
                        title=ref.title,
                        channel_name=ref.channel_name,
                        model=cfg.models.extraction,
                        max_chars=cfg.thresholds.transcript_max_chars,
                        long_video_seconds=cfg.thresholds.long_video_seconds,
                        duration_seconds=ref.duration_seconds,
                    )
                    total_tokens += tokens
                    record.update(
                        {
                            "speakers": result.speakers,
                            "summary": result.summary,
                            "topics": result.topics,
                            "key_claims": result.key_claims,
                        }
                    )
                except Exception as e:
                    failed_extract += 1
                    print(f"ERROR extracting {ref.video_id}: {e}")
            else:
                unavailable_count += 1

            videos.append(record)

        state[channel.id] = {"last_video_id": newest_id, "last_checked": _now_iso()}

    videos_path.write_text(json.dumps(videos, indent=2) + "\n")
    state_path.write_text(json.dumps(state, indent=2) + "\n")

    graph = build_graph(videos)
    (data_dir / "graph.json").write_text(json.dumps(graph, indent=2) + "\n")

    sigs = build_signatures(videos, cfg.thresholds.distinctive_signatures_min_videos)
    (data_dir / "signatures.json").write_text(json.dumps(sigs, indent=2) + "\n")

    summary = {
        "new_videos": new_count,
        "captions": caption_count,
        "unavailable": unavailable_count,
        "failed_extract": failed_extract,
        "total_tokens": total_tokens,
    }
    print(f"Pipeline summary: {summary}")
    return summary


def main() -> int:
    load_dotenv()
    for key in ("OPENAI_API_KEY", "YOUTUBE_API_KEY"):
        if not os.environ.get(key):
            print(f"ERROR: {key} not set", file=sys.stderr)
            return 1
    run_pipeline()
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test and verify it passes**

Run: `pytest tests/test_pipeline.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline orchestrator with per-video resilience"
```

- [ ] **Step 6: Run pipeline locally against real APIs**

With `.env` populated and channel IDs resolved:
```bash
source .venv/bin/activate
python -m src.pipeline
```

Expected: 24 videos processed (3 per channel × 8 channels), `data/videos.json`, `data/state.json`, `data/graph.json`, `data/signatures.json` populated. Stop and confirm output looks reasonable before proceeding.

- [ ] **Step 7: Commit real data**

```bash
git add data/
git commit -m "chore: initial backfill, 3 videos per channel"
```

---

## Task 11: LLM-as-Judge Evaluation

**Files:**
- Create: `src/eval.py`
- Test: `tests/test_eval.py`

- [ ] **Step 1: Write the failing test**

`tests/test_eval.py`:
```python
from unittest.mock import MagicMock
from src.eval import (
    compute_availability,
    judge_summary_faithfulness,
    judge_topic_precision,
    SummaryFaithfulness,
    TopicPrecision,
)


def test_compute_availability_counts_sources():
    videos = [
        {"transcript_source": "captions"},
        {"transcript_source": "captions"},
        {"transcript_source": "unavailable"},
    ]
    assert compute_availability(videos) == {"captions": 2, "unavailable": 1}


def test_judge_summary_faithfulness_calls_openai_and_returns_labels(mocker):
    fake_completion = MagicMock()
    fake_completion.choices = [MagicMock()]
    fake_completion.choices[0].message.parsed = SummaryFaithfulness(
        per_sentence=["supported", "supported", "partially_supported"]
    )
    client = MagicMock()
    client.beta.chat.completions.parse.return_value = fake_completion

    result = judge_summary_faithfulness(
        client=client,
        model="gpt-4o-mini",
        transcript="Long transcript text",
        summary="First. Second. Third.",
    )

    assert result.per_sentence == ["supported", "supported", "partially_supported"]
    client.beta.chat.completions.parse.assert_called_once()


def test_judge_topic_precision_uses_two_passes(mocker):
    # Pass 1 → judge proposes its own topics
    pass1 = MagicMock()
    pass1.choices = [MagicMock()]
    pass1.choices[0].message.parsed = MagicMock(topics=["rlhf", "agents", "evals"])

    # Pass 2 → compares extractor vs judge
    pass2 = MagicMock()
    pass2.choices = [MagicMock()]
    pass2.choices[0].message.parsed = TopicPrecision(
        labels={"rlhf": "correct", "scaling laws": "wrong"}
    )

    client = MagicMock()
    client.beta.chat.completions.parse.side_effect = [pass1, pass2]

    result = judge_topic_precision(
        client=client,
        model="gpt-4o-mini",
        transcript="Transcript",
        extractor_topics=["rlhf", "scaling laws"],
    )

    assert result.labels == {"rlhf": "correct", "scaling laws": "wrong"}
    assert client.beta.chat.completions.parse.call_count == 2
```

- [ ] **Step 2: Run test and verify it fails**

Run: `pytest tests/test_eval.py -v`
Expected: `ModuleNotFoundError`.

- [ ] **Step 3: Implement `src/eval.py`**

```python
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from src.config import load_config


class SummaryFaithfulness(BaseModel):
    per_sentence: list[Literal["supported", "partially_supported", "unsupported"]]


class JudgeTopics(BaseModel):
    topics: list[str]


class TopicPrecision(BaseModel):
    labels: dict[str, Literal["correct", "partial", "wrong"]]


def compute_availability(videos: list[dict]) -> dict[str, int]:
    out = {"captions": 0, "unavailable": 0}
    for v in videos:
        src = v.get("transcript_source", "unavailable")
        out[src] = out.get(src, 0) + 1
    return out


def judge_summary_faithfulness(
    client: OpenAI, model: str, transcript: str, summary: str
) -> SummaryFaithfulness:
    sys_prompt = (
        "You are an evaluator. You are given a transcript and a summary. "
        "Classify EACH SENTENCE of the summary as 'supported', 'partially_supported', "
        "or 'unsupported' by the transcript. Return a list of labels in the same order as the sentences."
    )
    user = (
        f"Transcript (first 60k chars):\n{transcript[:60000]}\n\n"
        f"Summary:\n{summary}"
    )
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user},
        ],
        response_format=SummaryFaithfulness,
        temperature=0,
    )
    return completion.choices[0].message.parsed


def judge_topic_precision(
    client: OpenAI, model: str, transcript: str, extractor_topics: list[str]
) -> TopicPrecision:
    # Pass 1: judge proposes its own topics
    sys_propose = (
        "You are an evaluator. Read the transcript and propose 3-5 topics (short noun phrases, lowercase) "
        "that best characterize its content."
    )
    pass1 = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sys_propose},
            {"role": "user", "content": f"Transcript (first 60k chars):\n{transcript[:60000]}"},
        ],
        response_format=JudgeTopics,
        temperature=0,
    )
    judge_topics = pass1.choices[0].message.parsed.topics

    # Pass 2: grade extractor_topics against judge_topics
    sys_grade = (
        "You compare two sets of topics for a video transcript. "
        "For each topic in EXTRACTOR_TOPICS, label it: "
        "'correct' if it matches or is semantically equivalent to any topic in JUDGE_TOPICS; "
        "'partial' if it's related but narrower/broader; "
        "'wrong' if it does not reflect the transcript's content."
    )
    user = (
        f"JUDGE_TOPICS: {judge_topics}\n"
        f"EXTRACTOR_TOPICS: {extractor_topics}\n"
        f"Transcript snippet (first 20k chars):\n{transcript[:20000]}"
    )
    pass2 = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sys_grade},
            {"role": "user", "content": user},
        ],
        response_format=TopicPrecision,
        temperature=0,
    )
    return pass2.choices[0].message.parsed


def run_eval(config_path: Path = Path("config.yaml"), data_dir: Path = Path("data")) -> dict:
    cfg = load_config(config_path)
    videos = json.loads((data_dir / "videos.json").read_text())
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    availability = compute_availability(videos)

    # Schema validity — extraction never explicitly errored for recorded records with source=captions,
    # so success rate is simply records with non-empty summary / records attempted.
    attempted = [v for v in videos if v.get("transcript_source") == "captions"]
    successes = [v for v in attempted if v.get("summary")]
    schema_validity = {
        "successes": len(successes),
        "total": len(attempted),
        "rate": (len(successes) / len(attempted)) if attempted else 0,
    }

    # Faithfulness and topic precision need the transcript. We re-fetch captions here
    # so eval is decoupled from the pipeline's transcript in memory.
    from src.transcribe import get_transcript

    faithfulness_per = []
    topic_prec_per = []
    overall_fs = {"supported": 0, "partially_supported": 0, "unsupported": 0}
    overall_tp = {"correct": 0, "partial": 0, "wrong": 0}

    for v in successes:
        transcript, source = get_transcript(v["video_id"])
        if source != "captions" or not transcript:
            continue
        try:
            fs = judge_summary_faithfulness(
                client, cfg.models.judge, transcript, v["summary"]
            )
            for label in fs.per_sentence:
                overall_fs[label] += 1
            faithfulness_per.append(
                {
                    "video_id": v["video_id"],
                    "supported": fs.per_sentence.count("supported"),
                    "partial": fs.per_sentence.count("partially_supported"),
                    "unsupported": fs.per_sentence.count("unsupported"),
                }
            )
        except Exception as e:
            print(f"faithfulness eval failed for {v['video_id']}: {e}")

        try:
            tp = judge_topic_precision(client, cfg.models.judge, transcript, v["topics"])
            for label in tp.labels.values():
                overall_tp[label] = overall_tp.get(label, 0) + 1
            correct = sum(1 for lbl in tp.labels.values() if lbl == "correct")
            partial = sum(1 for lbl in tp.labels.values() if lbl == "partial")
            wrong = sum(1 for lbl in tp.labels.values() if lbl == "wrong")
            topic_prec_per.append(
                {
                    "video_id": v["video_id"],
                    "correct": correct,
                    "partial": partial,
                    "wrong": wrong,
                }
            )
        except Exception as e:
            print(f"topic precision eval failed for {v['video_id']}: {e}")

    fs_total = sum(overall_fs.values())
    tp_total = sum(overall_tp.values())

    eval_out = {
        "schema_validity": schema_validity,
        "caption_availability": availability,
        "summary_faithfulness": {
            "per_video": faithfulness_per,
            "overall": {
                **overall_fs,
                "rate_supported": (overall_fs["supported"] / fs_total) if fs_total else 0,
            },
        },
        "topic_precision": {
            "per_video": topic_prec_per,
            "overall": overall_tp,
            "precision": (overall_tp["correct"] / tp_total) if tp_total else 0,
        },
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (data_dir / "eval.json").write_text(json.dumps(eval_out, indent=2) + "\n")
    return eval_out


def main() -> int:
    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1
    result = run_eval()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test and verify it passes**

Run: `pytest tests/test_eval.py -v`
Expected: 3 passed.

- [ ] **Step 5: Run eval locally against real data**

```bash
source .venv/bin/activate
python -m src.eval
```

Expected: `data/eval.json` populated with schema_validity, caption_availability, summary_faithfulness, topic_precision numbers. Eyeball the output for sanity.

- [ ] **Step 6: Commit**

```bash
git add src/eval.py tests/test_eval.py data/eval.json
git commit -m "feat: LLM-as-judge eval (schema, captions, faithfulness, topic precision)"
```

---

## Task 12: Frontend — HTML Skeleton + Styling

**Files:**
- Create: `site/index.html`, `site/assets/style.css`, `site/assets/app.js`

No automated tests; verify via browser.

- [ ] **Step 1: Create `site/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<meta name="viewport" content="width=device-width, initial-scale=1" />
<title>LLM YouTube Landscape</title>
<link rel="stylesheet" href="assets/style.css" />
<script src="https://d3js.org/d3.v7.min.js"></script>
</head>
<body>
<header class="site-header">
  <h1>The LLM YouTube Landscape</h1>
  <p class="sub">What eight leading creators are actually saying, summarized from their transcripts.</p>
  <p class="timestamp" id="last-updated">Loading…</p>
</header>

<main>
  <section class="intro">
    <p>
      This page tracks eight popular YouTube channels focused on large language models.
      Each video is transcribed from captions and passed through a small language model
      to extract <em>topics</em>, a <em>summary</em>, and <em>key claims</em> — so every
      row below reflects what the creator actually said, not just the title.
    </p>
    <p>
      Start with the landscape view, explore who covers what, skim the claims, and search
      the full video table.
    </p>
  </section>

  <section class="graph-section">
    <h2>The Landscape</h2>
    <p class="section-lede">Channels and topics, linked by how often they're discussed. Hover a node to highlight its connections. Click a topic to filter the table below.</p>
    <div id="graph"></div>
  </section>

  <section class="signatures-section">
    <h2>Who Covers What</h2>
    <p class="section-lede">Each card shows a channel's topic profile. Click a topic to filter.</p>
    <div id="signatures"></div>
  </section>

  <section class="claims-section">
    <h2>What They're Actually Saying</h2>
    <p class="section-lede">Direct claims extracted from transcripts. Filter by topic or channel above.</p>
    <div id="claims-filters"></div>
    <table id="claims-table"><thead><tr><th>Claim</th><th>Channel</th><th>Video</th></tr></thead><tbody></tbody></table>
  </section>

  <section class="videos-section">
    <h2>All Videos</h2>
    <div class="filters">
      <input type="search" id="video-search" placeholder="Filter by title, channel, topic, summary…" />
      <select id="sort-by">
        <option value="date">Sort by date</option>
        <option value="channel">Sort by channel</option>
      </select>
    </div>
    <table id="videos-table">
      <thead>
        <tr><th>Date</th><th>Channel</th><th>Title</th><th>Topics</th><th>Summary</th></tr>
      </thead>
      <tbody></tbody>
    </table>
  </section>
</main>

<footer>
  <p><a href="https://github.com/">Source on GitHub</a></p>
</footer>

<script src="assets/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Create `site/assets/style.css`**

```css
:root {
  --bg: #f7f5f1;
  --text: #1d1d1b;
  --muted: #6b6b66;
  --accent: #2a4b7c;
  --border: #d9d5cc;
  --chip-bg: #e8e4da;
  --chip-text: #35352f;
  --c1: #2a4b7c; --c2: #7a3e3a; --c3: #4b6b3f; --c4: #8a6436;
  --c5: #5c3e6e; --c6: #3a6a6b; --c7: #8e5d2a; --c8: #3d3a4f;
}

* { box-sizing: border-box; }
html, body {
  margin: 0;
  padding: 0;
  background: var(--bg);
  color: var(--text);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  line-height: 1.55;
}

main { max-width: 1100px; margin: 0 auto; padding: 0 24px; }

.site-header {
  max-width: 1100px;
  margin: 0 auto;
  padding: 64px 24px 24px;
  border-bottom: 1px solid var(--border);
}
.site-header h1 { font-size: 36px; margin: 0 0 8px; letter-spacing: -0.01em; }
.site-header .sub { color: var(--muted); margin: 0 0 4px; }
.site-header .timestamp { color: var(--muted); font-size: 13px; margin: 0; }

section { margin: 64px 0; }
h2 { font-size: 24px; margin: 0 0 8px; letter-spacing: -0.01em; }
.section-lede { color: var(--muted); margin: 0 0 24px; max-width: 720px; }

.intro p { max-width: 720px; color: var(--text); }
.intro em { color: var(--accent); font-style: normal; font-weight: 600; }

#graph { width: 100%; height: 560px; border: 1px solid var(--border); background: #fff; border-radius: 6px; }
#graph svg { display: block; width: 100%; height: 100%; }

.signatures-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 16px; }
.signature-card { background: #fff; border: 1px solid var(--border); border-radius: 6px; padding: 16px; }
.signature-card h3 { margin: 0 0 4px; font-size: 16px; }
.signature-card .meta { color: var(--muted); font-size: 12px; margin-bottom: 8px; }
.signature-card .topic-chip { display: inline-block; background: var(--chip-bg); color: var(--chip-text); padding: 3px 9px; border-radius: 999px; margin: 2px 3px 2px 0; font-size: 12px; cursor: pointer; }
.signature-card .topic-chip:hover { background: var(--accent); color: #fff; }

.filters { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.filters input, .filters select { padding: 8px 10px; border: 1px solid var(--border); border-radius: 6px; background: #fff; color: var(--text); font-size: 14px; font-family: inherit; }
.filters input { flex: 1; min-width: 200px; }

table { width: 100%; border-collapse: collapse; background: #fff; border: 1px solid var(--border); border-radius: 6px; overflow: hidden; font-size: 14px; }
thead th { text-align: left; padding: 10px 12px; font-weight: 600; color: var(--muted); background: #faf8f3; border-bottom: 1px solid var(--border); }
tbody td { padding: 12px; border-top: 1px solid var(--border); vertical-align: top; }
tbody tr:first-child td { border-top: none; }
tbody a { color: var(--accent); text-decoration: none; }
tbody a:hover { text-decoration: underline; }

.topic-chip { display: inline-block; background: var(--chip-bg); color: var(--chip-text); padding: 2px 8px; border-radius: 999px; margin: 1px 3px 1px 0; font-size: 11.5px; cursor: pointer; }
.topic-chip:hover { background: var(--accent); color: #fff; }

.unavailable-badge { display: inline-block; background: #f3e6dd; color: #8b5a3b; padding: 2px 8px; border-radius: 999px; font-size: 11px; }

.summary-cell { max-width: 420px; color: var(--muted); }
.summary-cell.collapsed { max-height: 3.6em; overflow: hidden; position: relative; }
.summary-cell.collapsed::after { content: "…"; }

footer { text-align: center; padding: 32px 0; color: var(--muted); font-size: 13px; }

@media (max-width: 720px) {
  .site-header { padding: 32px 20px 20px; }
  .site-header h1 { font-size: 28px; }
  main { padding: 0 16px; }
  #graph { height: 380px; }
}
```

- [ ] **Step 3: Create `site/assets/app.js` skeleton**

```javascript
const state = {
  videos: [],
  graph: { nodes: [], links: [] },
  signatures: {},
  filter: { topic: null, channel: null, text: "" },
  sortBy: "date",
};

async function boot() {
  const [videos, graph, signatures] = await Promise.all([
    fetch("./data/videos.json").then(r => r.json()).catch(() => []),
    fetch("./data/graph.json").then(r => r.json()).catch(() => ({ nodes: [], links: [] })),
    fetch("./data/signatures.json").then(r => r.json()).catch(() => ({})),
  ]);
  state.videos = videos;
  state.graph = graph;
  state.signatures = signatures;

  readFiltersFromUrl();
  renderTimestamp();
  renderGraph();
  renderSignatures();
  renderClaims();
  renderVideos();
  wireFilters();
}

function readFiltersFromUrl() {
  const p = new URLSearchParams(window.location.search);
  if (p.get("topic")) state.filter.topic = p.get("topic");
  if (p.get("channel")) state.filter.channel = p.get("channel");
  if (p.get("q")) state.filter.text = p.get("q");
}

function writeFiltersToUrl() {
  const p = new URLSearchParams();
  if (state.filter.topic) p.set("topic", state.filter.topic);
  if (state.filter.channel) p.set("channel", state.filter.channel);
  if (state.filter.text) p.set("q", state.filter.text);
  const qs = p.toString();
  const newUrl = qs ? `?${qs}` : window.location.pathname;
  window.history.replaceState({}, "", newUrl);
}

function renderTimestamp() {
  if (!state.videos.length) {
    document.getElementById("last-updated").textContent = "No data yet.";
    return;
  }
  const newest = state.videos.reduce((a, b) =>
    a.processed_at > b.processed_at ? a : b);
  document.getElementById("last-updated").textContent = `Last updated: ${newest.processed_at}`;
}

// Stubs (implemented in later tasks)
function renderGraph() { /* Task 13 */ }
function renderSignatures() { /* Task 14 */ }
function renderClaims() { /* Task 15 */ }
function renderVideos() { /* Task 16 */ }
function wireFilters() { /* Task 16 */ }

boot();
```

- [ ] **Step 4: Verify in browser**

Run:
```bash
cd site && python3 -m http.server 8000
```

Also copy `../data/` into `site/data/`:
```bash
cp -r ../data ./data
```

Open `http://localhost:8000`. Expected: header + section headings render; no errors in console; timestamp shows last processed time.

- [ ] **Step 5: Commit**

```bash
git add site/
git commit -m "feat: frontend skeleton with narrative scroll layout"
```

---

## Task 13: Frontend — D3 Force Graph

**Files:**
- Modify: `site/assets/app.js` (replace `renderGraph()` stub)

- [ ] **Step 1: Replace the `renderGraph()` function**

Replace the stub in `site/assets/app.js`:

```javascript
function renderGraph() {
  const container = document.getElementById("graph");
  container.innerHTML = "";
  if (!state.graph.nodes.length) {
    container.innerHTML = "<p style='padding:16px;color:var(--muted)'>No graph data yet.</p>";
    return;
  }

  const rect = container.getBoundingClientRect();
  const width = rect.width;
  const height = rect.height;

  const svg = d3.select("#graph").append("svg")
    .attr("viewBox", `0 0 ${width} ${height}`);

  const channelColors = ["#2a4b7c", "#7a3e3a", "#4b6b3f", "#8a6436", "#5c3e6e", "#3a6a6b", "#8e5d2a", "#3d3a4f"];
  const channelIds = state.graph.nodes.filter(n => n.type === "channel").map(n => n.id);
  const colorFor = (id) => channelColors[channelIds.indexOf(id) % channelColors.length];

  const nodes = state.graph.nodes.map(d => ({ ...d }));
  const links = state.graph.links.map(d => ({ ...d }));

  const linkEl = svg.append("g")
    .attr("stroke", "#bbb")
    .attr("stroke-opacity", 0.5)
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", d => Math.sqrt(d.weight));

  const nodeEl = svg.append("g")
    .selectAll("g")
    .data(nodes)
    .join("g");

  nodeEl.append("circle")
    .attr("r", d => d.type === "channel" ? 8 + Math.sqrt(d.size) * 2 : 4 + Math.sqrt(d.size))
    .attr("fill", d => d.type === "channel" ? colorFor(d.id) : "#bcae92")
    .attr("stroke", "#fff")
    .attr("stroke-width", 1.5)
    .style("cursor", d => d.type === "topic" ? "pointer" : "default")
    .on("click", (event, d) => {
      if (d.type === "topic") {
        const topicLabel = d.label;
        state.filter.topic = topicLabel;
        writeFiltersToUrl();
        renderClaims();
        renderVideos();
        document.getElementById("videos-table").scrollIntoView({ behavior: "smooth" });
      }
    });

  nodeEl.append("text")
    .attr("dy", d => d.type === "channel" ? -14 : -8)
    .attr("text-anchor", "middle")
    .style("font-size", d => d.type === "channel" ? "12px" : "10px")
    .style("font-weight", d => d.type === "channel" ? "600" : "400")
    .style("fill", "#333")
    .style("pointer-events", "none")
    .text(d => d.label);

  nodeEl.append("title").text(d => `${d.type}: ${d.label} (${d.size})`);

  nodeEl.on("mouseover", (event, d) => {
    const connected = new Set([d.id]);
    links.forEach(l => {
      if (l.source.id === d.id || l.source === d.id) connected.add(l.target.id || l.target);
      if (l.target.id === d.id || l.target === d.id) connected.add(l.source.id || l.source);
    });
    nodeEl.style("opacity", n => connected.has(n.id) ? 1 : 0.2);
    linkEl.style("opacity", l => (l.source.id === d.id || l.target.id === d.id) ? 0.9 : 0.05);
  }).on("mouseout", () => {
    nodeEl.style("opacity", 1);
    linkEl.style("opacity", 0.5);
  });

  const sim = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(80))
    .force("charge", d3.forceManyBody().strength(-240))
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collision", d3.forceCollide().radius(d => d.type === "channel" ? 24 : 12));

  sim.on("tick", () => {
    linkEl
      .attr("x1", d => d.source.x).attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x).attr("y2", d => d.target.y);
    nodeEl.attr("transform", d => `translate(${d.x}, ${d.y})`);
  });

  const drag = d3.drag()
    .on("start", (event, d) => { if (!event.active) sim.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
    .on("drag", (event, d) => { d.fx = event.x; d.fy = event.y; })
    .on("end", (event, d) => { if (!event.active) sim.alphaTarget(0); d.fx = null; d.fy = null; });
  nodeEl.call(drag);
}
```

- [ ] **Step 2: Verify in browser**

Reload `http://localhost:8000`. Expected: force graph renders, channel nodes larger and colored, hovering highlights connected nodes, clicking a topic scrolls to video table and filters it (videos table itself not yet wired in — that's Task 16, so this will scroll but not filter yet).

- [ ] **Step 3: Commit**

```bash
git add site/assets/app.js
git commit -m "feat: D3 force-directed landscape graph"
```

---

## Task 14: Frontend — Signature Cards

**Files:**
- Modify: `site/assets/app.js` (replace `renderSignatures()` stub)

- [ ] **Step 1: Replace `renderSignatures()`**

```javascript
function renderSignatures() {
  const container = document.getElementById("signatures");
  container.innerHTML = '<div class="signatures-grid"></div>';
  const grid = container.querySelector(".signatures-grid");

  const entries = Object.entries(state.signatures).sort((a, b) => a[1].channel_name.localeCompare(b[1].channel_name));
  if (!entries.length) {
    container.innerHTML = "<p style='color:var(--muted)'>No signatures yet.</p>";
    return;
  }

  for (const [cid, sig] of entries) {
    const card = document.createElement("div");
    card.className = "signature-card";
    const heading = sig.mode === "distinctive" ? "Distinctive topics" : "Topics covered";
    const top = (sig.topics || []).slice(0, 8);
    const chips = top.map(t =>
      `<span class="topic-chip" data-topic="${t.topic}">${t.topic}</span>`
    ).join(" ");
    card.innerHTML = `
      <h3>${sig.channel_name}</h3>
      <p class="meta">${sig.total_videos} video${sig.total_videos === 1 ? "" : "s"} · ${heading}</p>
      <div>${chips || "<span class='meta'>No topics yet</span>"}</div>
    `;
    card.querySelectorAll(".topic-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        state.filter.topic = chip.dataset.topic;
        writeFiltersToUrl();
        renderClaims();
        renderVideos();
        document.getElementById("videos-table").scrollIntoView({ behavior: "smooth" });
      });
    });
    grid.appendChild(card);
  }
}
```

- [ ] **Step 2: Verify in browser**

Reload. Expected: one card per channel, each showing video count + topic chips. Clicking a chip scrolls to video table (filter hooks wire up in Task 16).

- [ ] **Step 3: Commit**

```bash
git add site/assets/app.js
git commit -m "feat: channel signature cards"
```

---

## Task 15: Frontend — Key Claims Table

**Files:**
- Modify: `site/assets/app.js` (replace `renderClaims()` stub)

- [ ] **Step 1: Replace `renderClaims()`**

```javascript
function renderClaims() {
  const tbody = document.querySelector("#claims-table tbody");
  tbody.innerHTML = "";
  const filtersDiv = document.getElementById("claims-filters");
  filtersDiv.innerHTML = state.filter.topic
    ? `<p style="color:var(--muted);font-size:13px;">Filtered to topic: <strong>${state.filter.topic}</strong> <a href="#" id="clear-claim-topic">clear</a></p>`
    : "";
  const clearLink = document.getElementById("clear-claim-topic");
  if (clearLink) {
    clearLink.addEventListener("click", (e) => {
      e.preventDefault();
      state.filter.topic = null;
      writeFiltersToUrl();
      renderClaims();
      renderVideos();
    });
  }

  const rows = [];
  for (const v of state.videos) {
    if (v.transcript_source !== "captions") continue;
    if (state.filter.topic && !v.topics.map(normalizeForMatch).includes(normalizeForMatch(state.filter.topic))) continue;
    if (state.filter.channel && v.channel_id !== state.filter.channel) continue;
    for (const claim of v.key_claims || []) {
      rows.push({ claim, channel: v.channel_name, title: v.title, url: v.url });
    }
  }

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="3" style="color:var(--muted);padding:16px;">No claims match current filters.</td></tr>`;
    return;
  }

  for (const r of rows.slice(0, 200)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${escapeHtml(r.claim)}</td>
      <td>${escapeHtml(r.channel)}</td>
      <td><a href="${r.url}" target="_blank" rel="noopener">${escapeHtml(r.title)}</a></td>
    `;
    tbody.appendChild(tr);
  }
}

function normalizeForMatch(s) {
  return s.trim().toLowerCase();
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}
```

- [ ] **Step 2: Verify in browser**

Reload. Expected: claims table populated with all key claims across videos, filter status line updates when you click a topic chip elsewhere, cap at 200 rows for perf.

- [ ] **Step 3: Commit**

```bash
git add site/assets/app.js
git commit -m "feat: key claims table with topic filter"
```

---

## Task 16: Frontend — Videos Table + Filter Wiring

**Files:**
- Modify: `site/assets/app.js` (replace `renderVideos()` and `wireFilters()` stubs)

- [ ] **Step 1: Replace `renderVideos()` and `wireFilters()`**

```javascript
function renderVideos() {
  const tbody = document.querySelector("#videos-table tbody");
  tbody.innerHTML = "";

  let rows = [...state.videos];

  if (state.filter.topic) {
    const t = normalizeForMatch(state.filter.topic);
    rows = rows.filter(v => (v.topics || []).map(normalizeForMatch).includes(t));
  }
  if (state.filter.channel) {
    rows = rows.filter(v => v.channel_id === state.filter.channel);
  }
  if (state.filter.text) {
    const q = state.filter.text.toLowerCase();
    rows = rows.filter(v =>
      (v.title || "").toLowerCase().includes(q) ||
      (v.channel_name || "").toLowerCase().includes(q) ||
      (v.summary || "").toLowerCase().includes(q) ||
      (v.topics || []).some(t => t.toLowerCase().includes(q))
    );
  }

  if (state.sortBy === "date") {
    rows.sort((a, b) => b.published_at.localeCompare(a.published_at));
  } else if (state.sortBy === "channel") {
    rows.sort((a, b) =>
      (a.channel_name || "").localeCompare(b.channel_name || "") ||
      b.published_at.localeCompare(a.published_at)
    );
  }

  if (!rows.length) {
    tbody.innerHTML = `<tr><td colspan="5" style="color:var(--muted);padding:16px;">No videos match current filters.</td></tr>`;
    return;
  }

  for (const v of rows) {
    const tr = document.createElement("tr");
    const dateStr = (v.published_at || "").slice(0, 10);
    const topicChips = (v.topics || []).map(t =>
      `<span class="topic-chip" data-topic="${escapeHtml(t)}">${escapeHtml(t)}</span>`
    ).join(" ");
    const summaryCell = v.transcript_source === "unavailable"
      ? `<span class="unavailable-badge">transcript unavailable</span>`
      : `<div class="summary-cell collapsed" data-full="${escapeHtml(v.summary || '')}">${escapeHtml(v.summary || '')}</div>`;
    tr.innerHTML = `
      <td>${dateStr}</td>
      <td>${escapeHtml(v.channel_name || "")}</td>
      <td><a href="${v.url}" target="_blank" rel="noopener">${escapeHtml(v.title || "")}</a></td>
      <td>${topicChips}</td>
      <td>${summaryCell}</td>
    `;
    tbody.appendChild(tr);
  }

  tbody.querySelectorAll(".topic-chip").forEach(chip => {
    chip.addEventListener("click", () => {
      state.filter.topic = chip.dataset.topic;
      writeFiltersToUrl();
      renderClaims();
      renderVideos();
    });
  });
  tbody.querySelectorAll(".summary-cell").forEach(cell => {
    cell.addEventListener("click", () => cell.classList.toggle("collapsed"));
  });
}

function wireFilters() {
  const search = document.getElementById("video-search");
  search.value = state.filter.text || "";
  search.addEventListener("input", (e) => {
    state.filter.text = e.target.value;
    writeFiltersToUrl();
    renderVideos();
  });

  const sortSel = document.getElementById("sort-by");
  sortSel.value = state.sortBy;
  sortSel.addEventListener("change", (e) => {
    state.sortBy = e.target.value;
    renderVideos();
  });
}
```

- [ ] **Step 2: Verify in browser**

Reload. Expected: video table populated, filter box works, sort dropdown works, clicking topic chip filters both claims and videos. Click a topic node in the graph → table filters. Summary cells expand on click.

- [ ] **Step 3: Commit**

```bash
git add site/assets/app.js
git commit -m "feat: video table with filters, sort, and chip wiring"
```

---

## Task 17: GitHub Actions — Daily Update Workflow

**Files:**
- Create: `.github/workflows/update.yml`

- [ ] **Step 1: Create workflow**

```yaml
name: update

on:
  schedule:
    - cron: '0 2 * * *'
  workflow_dispatch:

concurrency:
  group: update
  cancel-in-progress: false

permissions:
  contents: write

jobs:
  update:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
          cache: 'pip'

      - run: pip install -r requirements.txt

      - run: python -m src.pipeline
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}
          YOUTUBE_API_KEY: ${{ secrets.YOUTUBE_API_KEY }}

      - run: python -m src.eval
        env:
          OPENAI_API_KEY: ${{ secrets.OPENAI_API_KEY }}

      - name: Commit data if changed
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          if git diff --quiet data/; then
            echo "no changes"
          else
            git add data/
            git commit -m "chore: daily update $(date -u +%Y-%m-%d)"
            git push
          fi
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/update.yml
git commit -m "ci: daily update workflow (cron + manual trigger)"
```

---

## Task 18: GitHub Actions — Pages Deploy Workflow

**Files:**
- Create: `.github/workflows/deploy.yml`

- [ ] **Step 1: Create workflow**

```yaml
name: deploy

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

concurrency:
  group: pages
  cancel-in-progress: true

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Copy data into site
        run: |
          mkdir -p site/data
          cp data/*.json site/data/
      - uses: actions/upload-pages-artifact@v3
        with:
          path: site

  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/deploy.yml
git commit -m "ci: GitHub Pages deploy workflow"
```

---

## Task 19: README + Evaluation Docs

**Files:**
- Create: `README.md`, `docs/evaluation.md`

These are written after the first real run so actual eval numbers go in. Run `python -m src.pipeline && python -m src.eval` once before writing.

- [ ] **Step 1: Create `README.md`**

Replace `{live-url}`, `{numbers}`, `{date-range}`, `{username}` with real values.

```markdown
# The LLM YouTube Landscape

An automated tracker for 8 popular YouTube channels covering large language models. Every day, new uploads are fetched, transcribed from captions, and passed through `gpt-4o-mini` to extract structured `summary`, `topics`, and `key_claims`. Results are rendered as a narrative page on GitHub Pages with a D3 force graph, channel signature cards, a claims table, and a filterable video table.

**Live site:** https://{username}.github.io/llm-yt-tracker/

## Problem Statement

Track eight LLM-focused YouTube creators, surface *what they actually say* (not just titles), and show how their topic coverage relates — served on a public page that stays current as new videos appear.

## Methodology

```
cron (daily 02:00 UTC) → fetch_videos → transcribe → extract → build_graph/signatures → commit → Pages deploy
```

- **Ingestion:** YouTube Data API v3 via the channel `uploads` playlist (cheaper than `search.list`), diffed against `data/state.json` so only new items are processed. 3-video backfill per channel on first run (config-driven).
- **Transcription:** `youtube-transcript-api` (captions only). Videos without captions are kept in the table with a badge but excluded from analytical aggregates.
- **Extraction:** `gpt-4o-mini` with Structured Outputs (Pydantic schema). System prompt biases the model toward a canonical topic list for normalization; long videos are chunked + synthesized.
- **Analytics:** pure functions over `videos.json` produce `graph.json` (channel↔topic bipartite) and `signatures.json` (per-channel topic profile; switches from `frequency` to `distinctive` mode at ≥10 videos per channel).
- **Hosting:** GitHub Pages serves `/site`; GitHub Actions runs the pipeline on a daily cron and commits results back to `/data`, which a separate workflow copies into the site artifact before deploy.

Why these choices: free infrastructure, zero database, the git commit history itself documents freshness, and every piece is one readable Python module.

## Evaluation Dataset

All videos currently indexed (N = {numbers}) across the 8 channels, covering uploads from {date-range}. See `data/videos.json`.

## Evaluation Methods

Four automated metrics run by `src/eval.py` across every indexed video:

1. **Schema validity** — parse-success rate of Structured Outputs extraction calls.
2. **Caption availability** — fraction of videos for which `youtube-transcript-api` returned captions.
3. **Summary faithfulness (LLM-as-judge)** — per-sentence `supported` / `partially_supported` / `unsupported` labels from `gpt-4o-mini` given transcript + summary.
4. **Topic precision (LLM-as-judge, two-pass)** — judge first proposes its own 3–5 topics from the transcript; pass 2 grades the extractor's topics against the judge's as `correct` / `partial` / `wrong`.

The freshness test is a one-time manual `workflow_dispatch` trigger (documented in `docs/evaluation.md`).

## Experimental Results

See `docs/evaluation.md` for per-metric tables. Summary:

- Schema validity: {rate}%
- Caption availability: {captions}/{total}
- Summary faithfulness (supported): {rate_supported}%
- Topic precision: {precision}%

## Limitations

- **Captions-only transcription.** Channels that disable captions lose coverage. A Deepgram fallback is scoped but unimplemented; swap-in is a single module.
- **Small dataset.** With 3 videos/channel at launch, eval numbers are directional, not statistical. The pipeline grows the dataset daily, so numbers will sharpen over time.
- **Same-family judge.** `gpt-4o-mini` judges `gpt-4o-mini`. Cross-family grading (Claude Haiku 4.5) would be stronger methodology.
- **Topic merging is heuristic** — lowercase + alias map catches common variants but not semantic near-duplicates.
- **Daily polling lag** — the worst case is ~24 hours from upload to appearance.
- **Cost** — pennies per day at current volume (24 videos × 2 eval calls × gpt-4o-mini ≈ $0.05).

## Setup

1. Fork and enable GitHub Pages (Settings → Pages → Source: GitHub Actions).
2. Add repository secrets:
   - `OPENAI_API_KEY`
   - `YOUTUBE_API_KEY`
3. Resolve channel IDs once:
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env  # fill in keys
   python -m src.resolve_channels
   git commit -am "chore: populate channel IDs"
   git push
   ```
4. Trigger a first run manually: Actions → "update" → Run workflow.
5. Wait for the deploy workflow to complete; visit the live site.
```

- [ ] **Step 2: Create `docs/evaluation.md`**

Populate actual numbers from `data/eval.json`.

```markdown
# Evaluation Results

Generated by `python -m src.eval` on {date}. Numbers reflect the full set of indexed videos at that time.

## 1. Schema Validity (automated)

| Successes | Total | Rate |
|---|---|---|
| {n} | {n} | {pct}% |

Structured Outputs parse-rate.

## 2. Caption Availability (automated)

| Source | Count |
|---|---|
| captions | {n} |
| unavailable | {n} |

## 3. Summary Faithfulness (LLM-as-judge)

| Label | Count | % |
|---|---|---|
| supported | {n} | {pct}% |
| partially_supported | {n} | {pct}% |
| unsupported | {n} | {pct}% |

Per-video detail in `data/eval.json`.

## 4. Topic Precision (LLM-as-judge, two-pass)

| Label | Count | % |
|---|---|---|
| correct | {n} | {pct}% |
| partial | {n} | {pct}% |
| wrong | {n} | {pct}% |

Overall precision: {pct}%.

## 5. Freshness Test (manual)

- Triggered `workflow_dispatch` at {timestamp}.
- Resulting commit: {sha}.
- New videos published within 24h of trigger that appeared in the commit: {list}.

## Caveats

- Same model family for extractor and judge. Numbers are directional; absolute values likely slightly optimistic.
- Small dataset (N = {total}). Percentages will sharpen as daily cron accumulates history.
```

- [ ] **Step 3: Commit**

```bash
git add README.md docs/evaluation.md
git commit -m "docs: submission report and evaluation results"
```

---

## Final Checks

- [ ] **Step 1: Full test suite passes**

Run: `pytest`
Expected: all tests pass.

- [ ] **Step 2: Pipeline is idempotent**

Run: `python -m src.pipeline`
Expected: "no new videos" for all channels; `data/` unchanged.

- [ ] **Step 3: Create public GitHub repo and push**

User action:
```bash
gh repo create llm-yt-tracker --public --source=. --remote=origin --push
```

Then Settings → Pages → Source: GitHub Actions.
Then Settings → Secrets → add `OPENAI_API_KEY` and `YOUTUBE_API_KEY`.

- [ ] **Step 4: Verify live site**

Wait for deploy workflow to complete. Visit `https://<user>.github.io/llm-yt-tracker/`. Confirm graph, signatures, claims, and video table render with data.

- [ ] **Step 5: Update README with live URL**

Fill in the `{username}` placeholder in `README.md`, commit, push.

---

## Self-Review Summary

- Every section of the design spec is covered by at least one task: channels/config (T1–T4), fetch (T5), transcribe (T6), extract (T7), graph (T8), signatures (T9), pipeline (T10), eval (T11), frontend (T12–T16), CI (T17–T18), report (T19).
- No placeholders — every code step shows complete code.
- Type consistency checked: `VideoRef`, `ExtractionResult`, `VideoRecord` are defined in Task 3 and used consistently thereafter; `normalize_topic` is defined in Task 8 and reused in Task 9.
- Frontend tasks have manual browser QA instead of TDD (no JS test harness; acceptable given the framework-free brief).
