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
