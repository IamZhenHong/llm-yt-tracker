from youtube_transcript_api import YouTubeTranscriptApi


def get_transcript(video_id: str) -> tuple[str | None, str]:
    """Return (transcript_text, source).

    source is:
      'captions'    — success
      'blocked'     — transient IP/rate-limit block; caller should NOT advance state
      'unavailable' — legitimately no English captions available; safe to skip forever
    """
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        segments = fetched.to_raw_data()
        text = " ".join(seg["text"].strip() for seg in segments if seg.get("text"))
        return text, "captions"
    except Exception as e:
        msg = str(e).lower()
        if "blocking requests" in msg or "ipblocked" in msg or "requestblocked" in msg:
            print(f"transcript BLOCKED for {video_id}: IP rate-limited")
            return None, "blocked"
        print(f"transcript unavailable for {video_id}: {e}")
        return None, "unavailable"
