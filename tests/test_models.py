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
