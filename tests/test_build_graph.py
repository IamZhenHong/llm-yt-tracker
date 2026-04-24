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
