import re
from src.models import VideoRef

ISO_DURATION_RE = re.compile(
    r"PT(?:(?P<h>\d+)H)?(?:(?P<m>\d+)M)?(?:(?P<s>\d+)S)?"
)


def iso8601_duration_to_seconds(duration: str) -> int:
    match = ISO_DURATION_RE.fullmatch(duration)
    if not match:
        return 0
    h = int(match.group("h") or 0)
    m = int(match.group("m") or 0)
    s = int(match.group("s") or 0)
    return h * 3600 + m * 60 + s


def get_uploads_playlist_id(youtube, channel_id: str) -> str:
    resp = youtube.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items") or []
    if not items:
        raise ValueError(f"no channel found for id {channel_id}")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_playlist_video_ids(youtube, playlist_id: str, max_results: int = 10) -> list[dict]:
    """Return items newest-first with minimal fields."""
    resp = (
        youtube.playlistItems()
        .list(part="contentDetails,snippet", playlistId=playlist_id, maxResults=max_results)
        .execute()
    )
    items = []
    for raw in resp.get("items", []):
        items.append(
            {
                "video_id": raw["contentDetails"]["videoId"],
                "published_at": raw["contentDetails"]["videoPublishedAt"],
                "title": raw["snippet"]["title"],
                "channel_id": raw["snippet"]["channelId"],
            }
        )
    return items


def fetch_video_durations(youtube, video_ids: list[str]) -> dict[str, int]:
    if not video_ids:
        return {}
    resp = (
        youtube.videos()
        .list(part="contentDetails", id=",".join(video_ids))
        .execute()
    )
    out = {}
    for item in resp.get("items", []):
        out[item["id"]] = iso8601_duration_to_seconds(item["contentDetails"]["duration"])
    return out


def diff_against_state(items: list[dict], last_seen: str | None, backfill: int) -> list[dict]:
    """Return items newer than last_seen (or first `backfill` if last_seen is empty/unknown)."""
    if not last_seen:
        return items[:backfill]
    new_items = []
    for item in items:
        if item["video_id"] == last_seen:
            return new_items
        new_items.append(item)
    # last_seen not found in the fetched window → treat everything as new
    return new_items


def fetch_new_videos(
    youtube,
    channel_id: str,
    channel_name: str,
    last_seen: str | None,
    backfill: int,
    min_duration_seconds: int,
) -> list[VideoRef]:
    uploads_id = get_uploads_playlist_id(youtube, channel_id)
    # Fetch enough to cover backfill even after min_duration filter
    items = list_playlist_video_ids(youtube, uploads_id, max_results=max(backfill * 3, 10))
    new_items = diff_against_state(items, last_seen, backfill * 3)
    if not new_items:
        return []
    durations = fetch_video_durations(youtube, [i["video_id"] for i in new_items])
    refs: list[VideoRef] = []
    for item in new_items:
        dur = durations.get(item["video_id"], 0)
        if dur < min_duration_seconds:
            continue
        refs.append(
            VideoRef(
                video_id=item["video_id"],
                channel_id=channel_id,
                channel_name=channel_name,
                title=item["title"],
                published_at=item["published_at"],
                url=f"https://www.youtube.com/watch?v={item['video_id']}",
                duration_seconds=dur,
            )
        )
        if len(refs) >= backfill:
            break
    return refs
