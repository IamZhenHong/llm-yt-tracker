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
