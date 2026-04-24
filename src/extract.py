import os
import re
from openai import OpenAI
from src.models import ExtractionResult


SYSTEM_PROMPT = """You extract structured metadata from YouTube video transcripts about large language models. Be precise. Only use facts supported by the transcript. Prefer canonical topic names from this list when applicable: RLHF, RLAIF, fine-tuning, LoRA, QLoRA, quantization, tokenization, scaling laws, mixture of experts, transformers, attention, context length, retrieval augmented generation, agents, tool use, function calling, reasoning, chain of thought, test-time compute, reinforcement learning, alignment, interpretability, benchmarks, evals, multimodal, vision language models, code generation, open source models, closed models, MCP, synthetic data. For topics outside this list, use a short noun phrase in lowercase. Return 3-5 key_claims that are concrete statements made in the video. Summary should be 2-4 sentences."""


def chunk_transcript(text: str, max_chars: int) -> list[str]:
    """Split on sentence boundaries so no chunk exceeds max_chars."""
    if len(text) <= max_chars:
        return [text]
    # Split on ". " to preserve rough sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks: list[str] = []
    current = ""
    for sent in sentences:
        if len(current) + len(sent) + 1 > max_chars and current:
            chunks.append(current.strip())
            current = sent
        else:
            current = (current + " " + sent) if current else sent
    if current:
        chunks.append(current.strip())
    return chunks


def _call(
    client: OpenAI,
    model: str,
    transcript: str,
    title: str,
    channel_name: str,
    is_synthesis: bool = False,
) -> tuple[ExtractionResult, int]:
    user_prefix = (
        "Synthesize across the prior chunks.\n"
        if is_synthesis
        else ""
    )
    user = (
        f"{user_prefix}Channel: {channel_name}\nTitle: {title}\n\nTranscript:\n{transcript}"
    )
    completion = client.beta.chat.completions.parse(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user},
        ],
        response_format=ExtractionResult,
        temperature=0,
    )
    result = completion.choices[0].message.parsed
    tokens = completion.usage.total_tokens if completion.usage else 0
    return result, tokens


def extract(
    transcript: str,
    title: str,
    channel_name: str,
    model: str,
    max_chars: int,
    long_video_seconds: int,
    duration_seconds: int,
) -> tuple[ExtractionResult, int]:
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    total_tokens = 0

    if duration_seconds < long_video_seconds and len(transcript) <= max_chars:
        result, tokens = _call(client, model, transcript, title, channel_name)
        return result, tokens

    # Long path: chunk, extract per chunk, then synthesize
    chunks = chunk_transcript(transcript, max_chars=max_chars)
    partials: list[ExtractionResult] = []
    for chunk in chunks:
        partial, tokens = _call(client, model, chunk, title, channel_name)
        partials.append(partial)
        total_tokens += tokens

    # Synthesize: feed the concatenated summaries + all topics + all claims
    synthesis_input = "\n\n".join(
        f"Chunk {i+1} summary: {p.summary}\nTopics: {', '.join(p.topics)}\nClaims: " +
        "; ".join(p.key_claims)
        for i, p in enumerate(partials)
    )
    final, tokens = _call(client, model, synthesis_input, title, channel_name, is_synthesis=True)
    total_tokens += tokens
    return final, total_tokens
