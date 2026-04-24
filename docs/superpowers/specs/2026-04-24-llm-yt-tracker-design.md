# LLM YouTube Landscape Tracker — Design Spec

**Date**: 2026-04-24
**Status**: Approved, ready for implementation planning

## Problem Statement

Recruitment take-home: build an automated system that follows 8 popular YouTube channels focused on large language models, transcribes their videos, extracts what each creator is actually saying (not just titles), and presents both a browsable video table and an analytical view of how the channels' topic coverage relates. The site must stay up-to-date as new videos appear and run on free infrastructure.

## Goals

1. **Analytical depth** is the primary differentiator. Reviewers called out "how the channels relate to each other on LLM themes" — we answer that with quantified outputs (channel × topic matrix, channel signatures, cross-channel topic graph), not just a table of summaries.
2. **Auto-updating** via GitHub Actions daily cron, with the freshness pipeline visible in the git commit history.
3. **Public page** served from GitHub Pages, single scrolling narrative that ends in a filterable video table.
4. **Transcript-grounded content** — every row reflects what was said, captured as structured `summary`, `topics`, and `key_claims` extracted from the actual transcript.
5. **Honest evaluation** — automated LLM-as-judge metrics across all 24 videos with an explicit note about small-n limitations.

## Non-Goals

- Whisper fallback (local or hosted). Captions-only for MVP; revisit if coverage is bad.
- Temporal trend analysis, shared-conversation detection. Too thin at this dataset size.
- Cross-family eval judge. Keep infra minimal; one model family is acceptable given we flag the limitation.
- Any frontend framework or build step. Vanilla HTML/CSS/JS + D3 v7.
- Historical backfill beyond 3 videos per channel on first run. Config knob expands it later if needed.

## Channels

Eight channels, handles resolved to channel IDs once via a setup script and then hardcoded in `config.yaml`:

| Name | Handle |
|---|---|
| Andrej Karpathy | @AndrejKarpathy |
| Yannic Kilcher | @YannicKilcher |
| AI Explained | @aiexplained-official |
| Machine Learning Street Talk | @MachineLearningStreetTalk |
| Dwarkesh Patel | @DwarkeshPatel |
| Sam Witteveen | @SamWitteveen |
| 1littlecoder | @1littlecoder |
| Matthew Berman | @matthew_berman |

## Architecture

```
  GitHub Actions (daily 02:00 UTC + workflow_dispatch)
                  │
                  ▼
          Python pipeline (src/pipeline.py)
                  │
     ┌────────────┼─────────────────┐
     ▼            ▼                 ▼
  fetch_videos  transcribe      extract
  (YouTube API) (captions only) (gpt-4o-mini SO)
                  │
                  ▼
          data/videos.json  +  data/state.json
                  │
     ┌────────────┼─────────────┐
     ▼            ▼             ▼
  build_graph  build_signatures  eval
  → graph.json → signatures.json → eval.json
                  │
                  ▼
          git commit → push → Pages deploy
                  │
                  ▼
       site/index.html renders narrative
       scroll with D3 force graph + table
```

Single orchestrator (`pipeline.py`) runs the sequence with per-video try/except so one failure doesn't sink the run. Every step logs structured progress to stdout so Actions logs are the debugger.

## Components

### 1. `src/resolve_channels.py` (one-off)
Takes channel handles from `config.yaml`, resolves each to a channel ID via `channels.list?forHandle=...`, and writes the IDs back. Runs once locally; IDs are stable.

### 2. `src/fetch_videos.py`
For each channel ID, resolves the `uploads` playlist ID from `channels.list(part=contentDetails)`, then fetches recent items via `playlistItems.list`. Diffs against `data/state.json`: if `state.json[channel_id].last_video_id` is empty, fetch the most recent `backfill_per_channel` items; otherwise fetch everything newer than `last_video_id`. Returns a list of new `VideoRef` objects with `video_id`, `channel_id`, `title`, `published_at`, `duration_seconds`, `url`.

### 3. `src/transcribe.py`
Single function: `get_transcript(video_id) -> tuple[str | None, str]`. Uses `youtube-transcript-api`, returns `(transcript_text, "captions")` on success or `(None, "unavailable")` on failure. No fallback; no audio download.

### 4. `src/extract.py`
Single function: `extract(transcript, title, channel_name) -> ExtractionResult`. Uses OpenAI `gpt-4o-mini` with Structured Outputs (JSON schema). System prompt emphasizes "use only facts supported by the transcript" and provides the canonical topic alias list. Transcripts truncated to 120k chars before sending. For videos >2 hours, chunks the transcript and runs a final synthesis pass. Logs cumulative token usage per run.

Canonical topic list (LLM preferred to choose from this when applicable, otherwise free-form lowercase noun phrase):
> RLHF, RLAIF, fine-tuning, LoRA, QLoRA, quantization, tokenization, scaling laws, mixture of experts, transformers, attention, context length, retrieval augmented generation, agents, tool use, function calling, reasoning, chain of thought, test-time compute, reinforcement learning, alignment, interpretability, benchmarks, evals, multimodal, vision language models, code generation, open source models, closed models, MCP, synthetic data

### 5. `src/build_graph.py`
Pure function over `videos.json`. Nodes = channels + topics (after normalization: lowercase + canonical alias mapping). Edges = "channel discussed topic," weighted by count. Sizes: channel nodes scaled by total video count, topic nodes by total mentions. Output: `data/graph.json` (`{nodes, links}`).

### 6. `src/build_signatures.py`
Pure function over `videos.json`. For each channel, emits `{channel_id, total_videos, topics: [{topic, count, share}]}`. When a channel has ≥10 videos, also computes `distinctiveness_score` per topic (its share in this channel divided by its share across all channels, TF-IDF–style), and the site shows "distinctive topics" instead of "topics covered." At n=3 per channel, we ship with plain frequency ranking.

### 7. `src/pipeline.py`
Orchestrator. Loads config, iterates channels, for each new video:
1. Fetch transcript. If unavailable: log, write a "transcript_source: unavailable" stub into videos.json, continue.
2. Run extraction. On failure: log, write stub with error flag, continue.
3. Append full record.
4. Update `state.json` for the channel to the newest `video_id` seen — regardless of transcript availability or extraction success — so the next run doesn't reprocess the same videos.

After all channels processed, rebuilds graph, signatures, and (in a separate mode flag) eval. Writes all JSON outputs. Prints summary: `X new videos / Y captions / Z unavailable / $W tokens`.

### 8. `src/eval.py`
Runs three automated metrics over the full `videos.json` (24 records at launch), writes `data/eval.json`:

- **Schema validity**: count of successful Structured Outputs parses / total extraction attempts.
- **Caption availability**: `captions` vs `unavailable` counts and percentages.
- **Summary faithfulness** (LLM-as-judge): per video, prompt gpt-4o-mini with transcript + summary, ask it to classify each summary sentence as `supported` / `partially_supported` / `unsupported`. Aggregate to per-video score, then overall.
- **Topic precision** (LLM-as-judge, two-pass): pass 1, judge reads transcript cold and proposes its own 3–5 topics. Pass 2, judge compares extractor topics vs its own and labels each as `correct` / `partial` / `wrong`. Report precision.

Freshness test is manual: trigger `workflow_dispatch`, record timestamp, verify new videos appear in that run's commit. Reported as one line in `docs/evaluation.md`.

Report acknowledges: eval uses same model family as extractor; small n=24; numbers are directional.

### 9. Frontend (`site/`)

Single-page narrative scroll, no framework, no build. Layout sections in order:

1. **Header** — project title, "last updated" timestamp read from newest `processed_at`, link to repo.
2. **Intro** — two short paragraphs framing the project.
3. **The Landscape** — D3 v7 force-directed graph. Channel nodes larger + distinctly colored; topic nodes smaller. Hovering a channel highlights its topics and vice versa. Clicking a topic filters the table below.
4. **Who Covers What** — channel signature cards. Each card: channel name, video count, top topics as chips. Clicking a chip filters the table. At n≥10 videos per channel, card switches to showing "distinctive topics."
5. **What They're Actually Saying** — key claims table. Columns: claim, channel, video (link), topic. Client-side filter by topic or channel.
6. **All Videos** — the full table. Columns: date, channel, title (linked to YouTube), speakers, topics (as chips), summary (expandable). Client-side filter input + sort by date/channel. Videos with `transcript_source: "unavailable"` rendered with a badge and no summary/topics.

Filters are URL-synced (`?topic=rlhf&channel=UCxxx`) so graph clicks produce shareable links.

Visual: muted neutral background, system font stack, generous whitespace, one accent color per channel (categorical). Graph and table stack on narrow viewports.

### 10. GitHub Actions

Two workflows:

**`.github/workflows/update.yml`** — scheduled + manual.
- Triggers: `schedule: '0 2 * * *'` + `workflow_dispatch`.
- Concurrency: `group: update` (no overlapping runs).
- Permissions: `contents: write`.
- Steps: checkout → setup-python 3.11 → install deps → `python -m src.pipeline` → if `data/` changed, commit with message `chore: daily update YYYY-MM-DD` and push.
- Secrets: `OPENAI_API_KEY`, `YOUTUBE_API_KEY`.

**`.github/workflows/deploy.yml`** — GitHub Pages deploy.
- Trigger: `push` to `main`.
- Permissions: `pages: write`, `id-token: write`.
- Steps: checkout → copy `data/` into `site/data/` → upload artifact → `actions/deploy-pages`.

## Data Schemas

**`data/videos.json`** (array)
```json
{
  "video_id": "abc123",
  "channel_id": "UCxxx",
  "channel_name": "Andrej Karpathy",
  "title": "...",
  "published_at": "2026-04-20T14:00:00Z",
  "url": "https://www.youtube.com/watch?v=...",
  "duration_seconds": 1234,
  "transcript_source": "captions" | "unavailable",
  "speakers": ["Andrej Karpathy"],
  "summary": "2-4 sentences grounded in transcript.",
  "topics": ["scaling laws", "mixture of experts"],
  "key_claims": ["Claim 1...", "Claim 2..."],
  "processed_at": "2026-04-24T02:00:00Z"
}
```

For `transcript_source: "unavailable"` records, `speakers`, `summary`, `topics`, `key_claims` are empty arrays / empty string.

**`data/state.json`**
```json
{ "UCxxx": { "last_video_id": "abc", "last_checked": "2026-04-24T02:00:00Z" } }
```

**`data/graph.json`**
```json
{
  "nodes": [
    {"id": "channel:UCxxx", "type": "channel", "label": "Karpathy", "size": 12},
    {"id": "topic:rlhf", "type": "topic", "label": "RLHF", "size": 8}
  ],
  "links": [
    {"source": "channel:UCxxx", "target": "topic:rlhf", "weight": 3}
  ]
}
```

**`data/signatures.json`**
```json
{
  "UCxxx": {
    "channel_name": "Karpathy",
    "total_videos": 3,
    "mode": "frequency",
    "topics": [{"topic": "scaling laws", "count": 2, "share": 0.67}]
  }
}
```
`mode` becomes `"distinctive"` and topics gain a `distinctiveness_score` when `total_videos >= 10`.

**`data/eval.json`**
```json
{
  "schema_validity": {"successes": 24, "total": 24, "rate": 1.0},
  "caption_availability": {"captions": 22, "unavailable": 2},
  "summary_faithfulness": {
    "per_video": [{"video_id": "...", "supported": 3, "partial": 1, "unsupported": 0}],
    "overall": {"supported": 68, "partial": 15, "unsupported": 4, "rate_supported": 0.78}
  },
  "topic_precision": {
    "per_video": [{"video_id": "...", "correct": 3, "partial": 1, "wrong": 1}],
    "overall_precision": 0.72
  },
  "run_at": "2026-04-24T02:00:00Z"
}
```

## Repo Structure

```
llm-yt-tracker/
├── README.md                     # Submission report
├── config.yaml                   # Channels, model names, thresholds
├── requirements.txt
├── .env.example
├── .gitignore
├── .github/
│   └── workflows/
│       ├── update.yml
│       └── deploy.yml
├── src/
│   ├── __init__.py
│   ├── resolve_channels.py
│   ├── fetch_videos.py
│   ├── transcribe.py
│   ├── extract.py
│   ├── build_graph.py
│   ├── build_signatures.py
│   ├── eval.py
│   └── pipeline.py
├── data/
│   ├── videos.json
│   ├── state.json
│   ├── graph.json
│   ├── signatures.json
│   └── eval.json
├── site/
│   ├── index.html
│   ├── assets/
│   │   ├── app.js
│   │   └── style.css
│   └── data/                     # Copied from /data at deploy time
└── docs/
    ├── evaluation.md             # Eval results, linked from README
    └── superpowers/
        └── specs/
            └── 2026-04-24-llm-yt-tracker-design.md
```

## Config (`config.yaml`)

```yaml
channels:
  - name: "Andrej Karpathy"
    handle: "@AndrejKarpathy"
    id: ""  # Filled by resolve_channels.py
  # ... 7 more

backfill_per_channel: 3
min_duration_seconds: 300  # Skip Shorts / trailers

models:
  extraction: "gpt-4o-mini"
  judge: "gpt-4o-mini"

thresholds:
  transcript_max_chars: 120000
  long_video_seconds: 7200
  distinctive_signatures_min_videos: 10
```

## Report (`README.md`)

Required sections in order:

1. **Problem Statement** — 2–3 sentences.
2. **Methodology** — architecture diagram, data flow, cron behavior, tool-choice justification.
3. **Evaluation Dataset** — all 24 videos across 8 channels, date range.
4. **Evaluation Methods** — four automated metrics, brief.
5. **Experimental Results** — numbers from `docs/evaluation.md`.
6. **Limitations** — captions-only, small n, mono-family judge, daily polling lag, cost.
7. **Setup** — fork, secrets to add, manual trigger instructions.
8. **Live site** — URL.

## Ground Rules

- Per-video try/except in pipeline; one bad transcript doesn't sink the run.
- Log everything useful to stdout.
- Never commit secrets. `.env` local, GitHub Secrets in CI.
- Cost guard: log cumulative OpenAI token usage each run.
- Never skip hooks or rewrite published git history.

## Risks and Open Questions

- **Caption availability per channel** — we'll only know the real hit rate after resolve + first fetch. If any channel is <50% covered, we revisit (Deepgram fallback was already scoped).
- **YouTube API quota** — daily poll of 8 channels × a few API calls each is well under the 10k units/day quota. Not a concern.
- **topic normalization edge cases** — LLM may coin near-duplicates ("scaling laws" vs "scaling law"). Canonical alias map + lowercase normalization in `build_graph.py` mitigates but won't catch everything. Acceptable for v1.
- **gpt-4o-mini as own-judge** — acknowledged limitation. If eval numbers look suspiciously high, consider swapping to Claude Haiku 4.5 as judge (minimal code change).

## Build Order for the Implementation Plan

1. `requirements.txt`, `config.yaml`, `.gitignore`, `.env.example`
2. `src/resolve_channels.py` → run once locally, populate channel IDs
3. `src/fetch_videos.py` + state diffing
4. `src/transcribe.py`
5. `src/extract.py`
6. `src/build_graph.py` + `src/build_signatures.py`
7. `src/pipeline.py`
8. `src/eval.py`
9. Frontend: structure → styling → graph → table → signature cards → key claims table
10. GitHub Actions workflows
11. README + `docs/evaluation.md` (written after real data exists)

Each step has a natural test point; stop for user review between backend pieces and before committing the frontend pass.
