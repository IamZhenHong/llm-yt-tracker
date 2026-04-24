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
