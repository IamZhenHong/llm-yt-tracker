import os
import sys
from pathlib import Path
import yaml
from dotenv import load_dotenv
from googleapiclient.discovery import build


def resolve_handle_to_id(youtube, handle: str) -> str | None:
    """Return channel ID for a @handle, or None if not found."""
    resp = youtube.channels().list(part="id", forHandle=handle).execute()
    items = resp.get("items") or []
    if not items:
        return None
    return items[0]["id"]


def main() -> int:
    load_dotenv()
    api_key = os.environ.get("YOUTUBE_API_KEY")
    if not api_key:
        print("ERROR: YOUTUBE_API_KEY not set", file=sys.stderr)
        return 1

    youtube = build("youtube", "v3", developerKey=api_key)
    cfg_path = Path("config.yaml")
    cfg = yaml.safe_load(cfg_path.read_text())

    for channel in cfg["channels"]:
        if channel.get("id"):
            print(f"skip {channel['handle']} (id already set)")
            continue
        cid = resolve_handle_to_id(youtube, channel["handle"])
        if cid is None:
            print(f"WARN: could not resolve {channel['handle']}")
            continue
        channel["id"] = cid
        print(f"{channel['handle']} -> {cid}")

    cfg_path.write_text(yaml.safe_dump(cfg, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
