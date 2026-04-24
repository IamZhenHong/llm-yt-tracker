from pathlib import Path
import textwrap
from src.config import load_config


def test_load_config_parses_channels_and_thresholds(tmp_path: Path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        channels:
          - name: "Andrej Karpathy"
            handle: "@AndrejKarpathy"
            id: "UCxxx"
        backfill_per_channel: 3
        min_duration_seconds: 300
        models:
          extraction: "gpt-4o-mini"
          judge: "gpt-4o-mini"
        thresholds:
          transcript_max_chars: 120000
          long_video_seconds: 7200
          distinctive_signatures_min_videos: 10
    """))

    cfg = load_config(cfg_file)

    assert cfg.backfill_per_channel == 3
    assert cfg.min_duration_seconds == 300
    assert cfg.models.extraction == "gpt-4o-mini"
    assert cfg.thresholds.transcript_max_chars == 120000
    assert len(cfg.channels) == 1
    assert cfg.channels[0].handle == "@AndrejKarpathy"
    assert cfg.channels[0].id == "UCxxx"
