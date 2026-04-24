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
