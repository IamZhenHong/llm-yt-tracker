import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from src.config import load_config


class SummaryFaithfulness(BaseModel):
    per_sentence: list[Literal["supported", "partially_supported", "unsupported"]]


class JudgeTopics(BaseModel):
    topics: list[str]


class TopicPrecision(BaseModel):
    labels: dict[str, Literal["correct", "partial", "wrong"]]


def compute_availability(videos: list[dict]) -> dict[str, int]:
    out = {"captions": 0, "unavailable": 0}
    for v in videos:
        src = v.get("transcript_source", "unavailable")
        out[src] = out.get(src, 0) + 1
    return out


def judge_summary_faithfulness(
    client: OpenAI, model: str, transcript: str, summary: str
) -> SummaryFaithfulness:
    sys_prompt = (
        "You are an evaluator. You are given a transcript and a summary. "
        "Classify EACH SENTENCE of the summary as 'supported', 'partially_supported', "
        "or 'unsupported' by the transcript. Return a list of labels in the same order as the sentences."
    )
    user = (
        f"Transcript (first 60k chars):\n{transcript[:60000]}\n\n"
        f"Summary:\n{summary}"
    )
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user", "content": user},
        ],
        response_format=SummaryFaithfulness,
        temperature=0,
    )
    return completion.choices[0].message.parsed


def judge_topic_precision(
    client: OpenAI, model: str, transcript: str, extractor_topics: list[str]
) -> TopicPrecision:
    # Pass 1: judge proposes its own topics
    sys_propose = (
        "You are an evaluator. Read the transcript and propose 3-5 topics (short noun phrases, lowercase) "
        "that best characterize its content."
    )
    pass1 = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sys_propose},
            {"role": "user", "content": f"Transcript (first 60k chars):\n{transcript[:60000]}"},
        ],
        response_format=JudgeTopics,
        temperature=0,
    )
    judge_topics = pass1.choices[0].message.parsed.topics

    # Pass 2: grade extractor_topics against judge_topics
    sys_grade = (
        "You compare two sets of topics for a video transcript. "
        "For each topic in EXTRACTOR_TOPICS, label it: "
        "'correct' if it matches or is semantically equivalent to any topic in JUDGE_TOPICS; "
        "'partial' if it's related but narrower/broader; "
        "'wrong' if it does not reflect the transcript's content."
    )
    user = (
        f"JUDGE_TOPICS: {judge_topics}\n"
        f"EXTRACTOR_TOPICS: {extractor_topics}\n"
        f"Transcript snippet (first 20k chars):\n{transcript[:20000]}"
    )
    pass2 = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": sys_grade},
            {"role": "user", "content": user},
        ],
        response_format=TopicPrecision,
        temperature=0,
    )
    return pass2.choices[0].message.parsed


def run_eval(config_path: Path = Path("config.yaml"), data_dir: Path = Path("data")) -> dict:
    cfg = load_config(config_path)
    videos = json.loads((data_dir / "videos.json").read_text())
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    availability = compute_availability(videos)

    attempted = [v for v in videos if v.get("transcript_source") == "captions"]
    successes = [v for v in attempted if v.get("summary")]
    schema_validity = {
        "successes": len(successes),
        "total": len(attempted),
        "rate": (len(successes) / len(attempted)) if attempted else 0,
    }

    from src.transcribe import get_transcript

    faithfulness_per = []
    topic_prec_per = []
    overall_fs = {"supported": 0, "partially_supported": 0, "unsupported": 0}
    overall_tp = {"correct": 0, "partial": 0, "wrong": 0}

    for v in successes:
        transcript, source = get_transcript(v["video_id"])
        if source != "captions" or not transcript:
            continue
        try:
            fs = judge_summary_faithfulness(
                client, cfg.models.judge, transcript, v["summary"]
            )
            for label in fs.per_sentence:
                overall_fs[label] += 1
            faithfulness_per.append(
                {
                    "video_id": v["video_id"],
                    "supported": fs.per_sentence.count("supported"),
                    "partial": fs.per_sentence.count("partially_supported"),
                    "unsupported": fs.per_sentence.count("unsupported"),
                }
            )
        except Exception as e:
            print(f"faithfulness eval failed for {v['video_id']}: {e}")

        try:
            tp = judge_topic_precision(client, cfg.models.judge, transcript, v["topics"])
            for label in tp.labels.values():
                overall_tp[label] = overall_tp.get(label, 0) + 1
            correct = sum(1 for lbl in tp.labels.values() if lbl == "correct")
            partial = sum(1 for lbl in tp.labels.values() if lbl == "partial")
            wrong = sum(1 for lbl in tp.labels.values() if lbl == "wrong")
            topic_prec_per.append(
                {
                    "video_id": v["video_id"],
                    "correct": correct,
                    "partial": partial,
                    "wrong": wrong,
                }
            )
        except Exception as e:
            print(f"topic precision eval failed for {v['video_id']}: {e}")

    fs_total = sum(overall_fs.values())
    tp_total = sum(overall_tp.values())

    eval_out = {
        "schema_validity": schema_validity,
        "caption_availability": availability,
        "summary_faithfulness": {
            "per_video": faithfulness_per,
            "overall": {
                **overall_fs,
                "rate_supported": (overall_fs["supported"] / fs_total) if fs_total else 0,
            },
        },
        "topic_precision": {
            "per_video": topic_prec_per,
            "overall": overall_tp,
            "precision": (overall_tp["correct"] / tp_total) if tp_total else 0,
        },
        "run_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    (data_dir / "eval.json").write_text(json.dumps(eval_out, indent=2) + "\n")
    return eval_out


def main() -> int:
    load_dotenv()
    if not os.environ.get("OPENAI_API_KEY"):
        print("ERROR: OPENAI_API_KEY not set", file=sys.stderr)
        return 1
    result = run_eval()
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
