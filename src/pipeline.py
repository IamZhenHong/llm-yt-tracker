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
