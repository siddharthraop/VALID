"""Gemini calls: embeddings now, answer generation later. Free tier: be gentle, batch small, retry on 429."""
from __future__ import annotations

import time

import httpx
from google import genai
from google.genai import errors, types

from . import config

_client: genai.Client | None = None


def client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client()          # reads GEMINI_API_KEY from the environment
    return _client


def http_options(timeout_s: int) -> types.HttpOptions:
    """One attempt, short timeout: the SDK's own hidden retries can hang a request for minutes."""
    return types.HttpOptions(timeout=timeout_s * 1000, retry_options=types.HttpRetryOptions(attempts=1))


def is_transient(e: Exception) -> bool:
    """Busy, rate-limited or unreachable: worth a retry or a fallback model."""
    if isinstance(e, errors.APIError):
        return e.code in (429, 500, 502, 503, 504)
    return isinstance(e, (httpx.TransportError, TimeoutError))


def doc_text(heading: str, text: str) -> str:
    """gemini-embedding-2 has no task_type. Documents use this format instead."""
    return f"title: {heading or 'none'} | text: {text}"


def query_text(question: str) -> str:
    return f"task: search result | query: {question}"


def _embed(texts: list[str]) -> list[list[float]]:
    # One Content per text: separate Content objects give separate embeddings.
    contents = [types.Content(parts=[types.Part(text=t)]) for t in texts]
    cfg = types.EmbedContentConfig(output_dimensionality=config.EMBED_DIM, http_options=http_options(20))
    for attempt in range(5):
        try:
            res = client().models.embed_content(model=config.EMBED_MODEL, contents=contents, config=cfg)
            vecs = [list(e.values) for e in res.embeddings]
            if len(vecs) != len(texts) or any(len(v) != config.EMBED_DIM for v in vecs):
                raise RuntimeError(f"embedding shape wrong: got {len(vecs)} vectors "
                                   f"of {sorted({len(v) for v in vecs})}, wanted {len(texts)} x {config.EMBED_DIM}")
            return vecs
        except Exception as e:
            if is_transient(e) and attempt < 4:
                time.sleep(2 ** attempt)
                continue
            raise
    raise RuntimeError("unreachable")


def embed_documents(items: list[tuple[str, str]], batch: int = 8) -> list[list[float]]:
    """items: (heading, text). Small batches, one second apart, to stay inside free-tier limits."""
    out: list[list[float]] = []
    for i in range(0, len(items), batch):
        out += _embed([doc_text(h, t) for h, t in items[i:i + batch]])
        if i + batch < len(items):
            time.sleep(1)
    return out


def embed_query(question: str) -> list[float]:
    return _embed([query_text(question)])[0]
