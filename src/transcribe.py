import os
import tempfile
from pathlib import Path

import requests
from youtube_transcript_api import YouTubeTranscriptApi


def _try_captions(video_id: str) -> tuple[str | None, str]:
    """Try YouTube captions. Return (text, status) where status is
    'captions' (success), 'blocked' (IP rate-limit), or 'unavailable' (no English captions)."""
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB"])
        segments = fetched.to_raw_data()
        text = " ".join(seg["text"].strip() for seg in segments if seg.get("text"))
        return text, "captions"
    except Exception as e:
        msg = str(e).lower()
        if "blocking requests" in msg or "ipblocked" in msg or "requestblocked" in msg:
            print(f"captions BLOCKED for {video_id}: IP rate-limited")
            return None, "blocked"
        print(f"captions unavailable for {video_id}: {e}")
        return None, "unavailable"


def _download_audio(video_id: str, out_dir: Path) -> Path:
    """Download the audio-only stream for a YouTube video using yt-dlp. Return the file path."""
    import yt_dlp

    out_template = str(out_dir / f"{video_id}.%(ext)s")
    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": out_template,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
    }
    url = f"https://www.youtube.com/watch?v={video_id}"
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
    ext = info.get("ext", "m4a")
    return out_dir / f"{video_id}.{ext}"


def _transcribe_with_deepgram(audio_path: Path) -> str:
    """Send an audio file to Deepgram's pre-recorded API and return the transcript text."""
    from deepgram import DeepgramClient, PrerecordedOptions, FileSource

    api_key = os.environ["DEEPGRAM_API_KEY"]
    client = DeepgramClient(api_key)
    with open(audio_path, "rb") as f:
        buffer_data = f.read()
    payload: FileSource = {"buffer": buffer_data}
    options = PrerecordedOptions(model="nova-3", language="en", smart_format=True)
    response = client.listen.rest.v("1").transcribe_file(payload, options, timeout=600)
    return response.results.channels[0].alternatives[0].transcript


def _try_supadata(video_id: str) -> str | None:
    """Try Supadata's managed transcript API. Handles proxy rotation + AI fallback server-side.
    Returns text on success, None on failure."""
    api_key = os.environ.get("SUPADATA_API_KEY")
    if not api_key:
        return None
    try:
        print(f"Supadata fallback: fetching {video_id}")
        resp = requests.get(
            "https://api.supadata.ai/v1/transcript",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "text": "true"},
            headers={"x-api-key": api_key},
            timeout=180,
        )
        if resp.status_code != 200:
            print(f"Supadata HTTP {resp.status_code} for {video_id}: {resp.text[:300]}")
            return None
        data = resp.json()
        # Supadata returns either a `content` string (when text=true) or an array of segments.
        text = data.get("content")
        if not text and isinstance(data.get("content"), list):
            text = " ".join(seg.get("text", "") for seg in data["content"])
        return text or None
    except Exception as e:
        print(f"Supadata fallback failed for {video_id}: {e}")
        return None


def _try_deepgram(video_id: str) -> str | None:
    """Download audio and transcribe via Deepgram. Return text on success, None on failure."""
    if not os.environ.get("DEEPGRAM_API_KEY"):
        return None
    with tempfile.TemporaryDirectory() as tmpdir:
        try:
            print(f"Deepgram fallback: downloading audio for {video_id}")
            audio_path = _download_audio(video_id, Path(tmpdir))
            print(f"Deepgram fallback: transcribing {audio_path.name}")
            text = _transcribe_with_deepgram(audio_path)
            return text or None
        except Exception as e:
            print(f"Deepgram fallback failed for {video_id}: {e}")
            return None


def get_transcript(video_id: str) -> tuple[str | None, str]:
    """Return (transcript_text, source).

    source is:
      'captions'    — YouTube captions returned a transcript
      'supadata'    — Supadata managed API returned a transcript
      'deepgram'    — Deepgram + yt-dlp audio transcription succeeded
      'blocked'     — all paths failed AND captions fetch was IP-blocked (retriable)
      'unavailable' — all paths failed AND captions were definitively absent
    """
    text, status = _try_captions(video_id)
    if status == "captions" and text:
        return text, "captions"

    # Layer 2: managed fallback (cloud-side proxies + AI fallback)
    sd_text = _try_supadata(video_id)
    if sd_text:
        return sd_text, "supadata"

    # Layer 3: local audio download + STT (only works when yt-dlp isn't IP-blocked)
    dg_text = _try_deepgram(video_id)
    if dg_text:
        return dg_text, "deepgram"

    return None, status
