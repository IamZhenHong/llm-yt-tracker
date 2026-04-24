# The LLM YouTube Landscape

Automated tracker for 5 popular YouTube channels covering large language models. Each day, new uploads are fetched, transcribed, and passed through `gpt-4o-mini` to extract structured `summary`, `topics`, and `key_claims`. Results are rendered as a narrative page on GitHub Pages with a D3 force graph, channel signature cards, a claims table, and a filterable video table.

**Live site:** `https://IamZhenHong.github.io/llm-yt-tracker/`

## Problem Statement

Follow a handful of leading LLM-focused YouTube creators, surface *what they actually say about LLM topics* (not just titles), and show how their topic coverage relates — served on a public page that stays current as new videos appear, using only free infrastructure.

## Methodology

```
cron (daily 02:00 UTC)       GitHub Actions
        │
        ▼
  fetch_videos ───► transcribe ───► extract ───► build_graph/signatures
(YouTube Data API) (3-tier fallback) (gpt-4o-mini           (pure functions)
                                      Structured Outputs)
                                                       │
                                                       ▼
                                  git commit data/ ──► Pages deploy
```

**Ingestion.** YouTube Data API v3 via the channel `uploads` playlist. Diffed against `data/state.json` so only new items are processed. 3-video backfill per channel on first run (config-driven).

**Transcription, three-tier fallback.**
1. `youtube-transcript-api` — free, fetches captions. Fast when it works; YouTube aggressively rate-limits it per-IP.
2. `supadata.ai` — managed transcript API that runs its own proxy pool and falls back to AI transcription when captions are unavailable. 100 free transcripts/month.
3. `yt-dlp + Deepgram Nova-3` — local audio download + STT. Last-resort path for when the first two fail.

Every video record carries a `transcript_source` field showing which tier delivered it, so the data is self-auditable.

**Extraction.** `gpt-4o-mini` with Structured Outputs (Pydantic schema) returns `speakers`, `summary` (2–4 sentences), `topics` (canonical list preferred), and `key_claims` (3–5). Long videos (>2 hours) are chunked and synthesized. A canonical topic list in the system prompt nudges the model toward consistent naming (`scaling laws` not `scaling-law`, `RLHF` not `reinforcement learning from human feedback`), with a local alias map on the output side to normalize any residual variation.

**Analytics.** Two pure functions over `videos.json`:
- `build_graph.py` → `graph.json`: channel↔topic bipartite graph, weighted by frequency.
- `build_signatures.py` → `signatures.json`: per-channel topic profile. Defaults to frequency ranking; auto-upgrades to a distinctiveness-weighted ranking (topic share in channel ÷ topic share across all channels) once a channel has ≥10 videos.

**Hosting.** GitHub Pages serves `/site` (vanilla HTML + CSS + JS, D3 v7 from CDN, no build step). GitHub Actions runs the pipeline on a 02:00 UTC daily cron and commits the updated JSON back to `/data`. A second workflow copies `/data` into the site artifact and deploys to Pages on every push.

**Why these choices:** free, no database, git history shows freshness, every piece is one readable Python module, and the frontend has no framework to maintain.

## Channels Tracked

1. **Andrej Karpathy** — foundational LLM mechanics, transformers from scratch, hands-on training
2. **Yannic Kilcher** — research paper breakdowns, new architectures and agent papers
3. **Matthew Berman** — practical LLM app building, local LLMs, agents, automation
4. **Matt Wolfe** — AI tool news and product use-cases
5. **DeepLearning.AI** — structured generative-AI courses

## Evaluation Dataset

All 12 videos currently indexed at launch, spanning uploads from **2024-06-09 to 2026-04-24**:

| Channel | Videos |
|---|---|
| Andrej Karpathy | 3 |
| Yannic Kilcher | 3 |
| Matthew Berman | 3 |
| Matt Wolfe | 2 |
| DeepLearning.AI | 1 |

Matt Wolfe's recent uploads and DeepLearning.AI's recent uploads include shorter clips below the 5-minute duration filter, which is why those two channels land under the 3-per-channel target. The daily cron will pick up qualifying new uploads as they appear.

See `docs/evaluation.md` for metric-by-metric detail.

## Evaluation Methods

Four automated metrics run by `src/eval.py` over every indexed video (no manual sampling; LLM-as-judge for the semantic metrics).

1. **Schema validity** — parse-success rate of Structured Outputs extraction calls.
2. **Transcript-source distribution** — which tier returned each transcript.
3. **Summary faithfulness** (LLM-as-judge). Judge LLM reads transcript + summary and classifies each summary sentence as `supported` / `partially_supported` / `unsupported`.
4. **Topic precision** (LLM-as-judge, two-pass). Pass 1: judge reads the transcript cold and proposes 3–5 topics of its own. Pass 2: judge grades the extractor's topics against its own as `correct` / `partial` / `wrong`.

The freshness test is a one-time manual `workflow_dispatch` trigger (documented in `docs/evaluation.md`).

## Experimental Results

From the run at `2026-04-24T15:28Z`:

| Metric | Result |
|---|---|
| Schema validity | **12/12 (100%)** |
| Transcript source | 6 captions, 6 supadata, 0 deepgram, 0 unavailable |
| Summary faithfulness | **68% supported**, 31% partial, 2% unsupported (n=59 sentences) |
| Topic precision (strict `correct` only) | **12%** (8 / 66 topics) |
| Topic precision (`correct` + `partial`) | **50%** (33 / 66 topics) |

See `docs/evaluation.md` for per-video breakdowns.

## Limitations

- **Topic precision looks low on the strict metric, but is probably a methodology artefact.** The judge proposes 3–5 high-level topics from the transcript; the extractor is instructed to emit 3–5 topics including specific canonical names. Many disagreements are really level-of-granularity disagreements ("compute" vs "inference cost", "pricing" vs "subscription models"), which show up as `partial`. 50% partial-or-better is probably a fairer signal of extractor quality.
- **Same-family judge.** `gpt-4o-mini` judges `gpt-4o-mini`. A cross-family judge (e.g. Claude Haiku 4.5) would be stronger methodology; omitted here to keep infra minimal.
- **Small dataset.** n=12 at launch. Percentages are directional. They sharpen as the daily cron accumulates history.
- **YouTube IP blocking.** Observed during backfill: after ~12 successful transcript-API calls from a single IP, YouTube flags the IP and both `youtube-transcript-api` *and* `yt-dlp` return bot-check errors until the flag expires (~hours). The Supadata fallback papers over this transparently at our scale. A residential-proxy solution via Webshare would be the equivalent fix if Supadata's free tier is ever exhausted.
- **Topic merging is heuristic** — lowercase + alias map catches common variants but not semantic near-duplicates.
- **Daily polling lag** — worst case ~24 hours from upload to appearance on the site.
- **Cost.** ~$0.01 per full-pipeline run at this volume (12 extractions + 24 judge calls at gpt-4o-mini rates). Supadata: 6 credits of the 100/month free tier used on day one. Deepgram: $200 credit untouched (fallback has not been triggered).

## Setup

1. Fork the repo.
2. **Enable GitHub Pages:** Settings → Pages → Source: GitHub Actions.
3. **Add repository secrets** (Settings → Secrets and variables → Actions):
   - `OPENAI_API_KEY` (required — extraction + eval)
   - `YOUTUBE_API_KEY` (required — YouTube Data API v3, enable it in your Google Cloud project)
   - `SUPADATA_API_KEY` (recommended — managed transcript fallback, free tier covers this volume)
   - `DEEPGRAM_API_KEY` (optional — last-resort STT fallback)
4. **Local one-time setup** (to populate channel IDs):
   ```bash
   python3.11 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   cp .env.example .env   # fill in the same keys locally
   python -m src.resolve_channels
   git commit -am "chore: populate channel IDs"
   git push
   ```
5. **Trigger the first run:** Actions → "update" → Run workflow. Wait for the deploy workflow to complete.
6. **Visit** `https://<username>.github.io/llm-yt-tracker/`.

## Local Development

```bash
source .venv/bin/activate
python -m src.pipeline      # one pipeline iteration against live APIs
python -m src.eval          # re-run eval on existing videos.json
pytest                      # full unit suite (29 tests)
cp data/*.json site/data/ && cd site && python3 -m http.server 8000
# open http://localhost:8000
```

## Repository Layout

```
llm-yt-tracker/
├── src/                          # Python pipeline
├── tests/                        # pytest unit tests
├── data/                         # JSON state, committed by CI
├── site/                         # GitHub Pages frontend
├── .github/workflows/            # update + deploy
├── docs/
│   ├── evaluation.md             # evaluation results
│   └── superpowers/              # design spec + implementation plan
├── config.yaml                   # channels, thresholds, model names
├── requirements.txt
└── README.md
```
