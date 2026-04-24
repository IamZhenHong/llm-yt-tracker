from youtube_transcript_api import YouTubeTranscriptApi


def get_transcript(video_id: str) -> tuple[str | None, str]:
    """Return (transcript_text, source). source is 'captions' on success, 'unavailable' on failure."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        segments = fetched.to_raw_data()
        text = " ".join(seg["text"].strip() for seg in segments if seg.get("text"))
        return text, "captions"
    except Exception as e:
        print(f"transcript fetch failed for {video_id}: {e}")
        return None, "unavailable"
