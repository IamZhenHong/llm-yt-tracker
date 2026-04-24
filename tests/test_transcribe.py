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
