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


def test_extract_calls_openai_with_structured_output_and_returns_result(monkeypatch, mocker):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
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
