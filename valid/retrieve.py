"""retrieve_in_scope: Firestore vector search + BM25, both inside the scope, fused with reciprocal rank fusion.

For two generations it runs once per generation and keeps the lists apart. It never searches without a scope.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from . import config, gemini, store
from .bm25 import Bm25Index
from .scheme import Scheme

RRF_K = 60


@dataclass
class Hit:
    id: str
    heading: str
    text: str
    scope: list[str]
    vec_rank: int | None = None
    vec_distance: float | None = None
    bm25_rank: int | None = None
    rrf: float = 0.0


@dataclass
class Corpus:
    chunks: dict[str, dict]
    bm25: Bm25Index
    owned: dict[str, str]

    @classmethod
    def load(cls, scheme: Scheme) -> "Corpus":
        rows = [json.loads(line) for line in open(config.DATA_DIR / "chunks.jsonl")]
        owned = json.loads((config.DATA_DIR / "owned.json").read_text())
        return cls({r["id"]: r for r in rows}, Bm25Index(rows, scheme.keys), owned)


def retrieve_in_scope(question: str, generations: list[str], scheme: Scheme, corpus: Corpus, col,
                      k: int = 5, pool: int = 8) -> dict[str, list[Hit]]:
    if not generations:
        raise ValueError("retrieve_in_scope needs at least one generation; it never searches without a scope")
    qvec = gemini.embed_query(question)                      # one embedding call serves every generation
    out: dict[str, list[Hit]] = {}
    for g in generations:
        hits: dict[str, Hit] = {}
        for rank, row in enumerate(store.search(col, g, qvec, scheme.keys, limit=pool), 1):
            c = corpus.chunks.get(row["id"])
            if c is None or g not in c["scope"]:             # stale or out-of-scope: never use it
                continue
            h = hits.setdefault(c["id"], Hit(c["id"], c["heading"], c["text"], c["scope"]))
            h.vec_rank, h.vec_distance = rank, row["distance"]
        for rank, (cid, _score) in enumerate(corpus.bm25.search(g, question, limit=pool), 1):
            c = corpus.chunks[cid]
            h = hits.setdefault(cid, Hit(cid, c["heading"], c["text"], c["scope"]))
            h.bm25_rank = rank
        for h in hits.values():
            h.rrf = sum(1.0 / (RRF_K + r) for r in (h.vec_rank, h.bm25_rank) if r)
        out[g] = sorted(hits.values(), key=lambda h: -h.rrf)[:k]
    return out
