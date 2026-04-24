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
