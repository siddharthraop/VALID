"""Firestore: write chunks with scope fields and vectors, and search with the scope pre-filter.

Design rule (5.3): the scope filter is part of every query and no code path removes it.
`search` is the only query function in this file and it cannot be called without a generation.
"""
from __future__ import annotations

from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure
from google.cloud.firestore_v1.vector import Vector

from . import config
from .dita import Chunk


def db() -> firestore.Client:
    return firestore.Client(project=config.PROJECT_ID)


def _sig(c: Chunk) -> str:
    return f"{c.hash}|{config.EMBED_MODEL}|{config.EMBED_DIM}"


def plan_sync(col, chunks: list[Chunk]):
    """Which chunks need embedding, which are unchanged, and which stored ids must go.
    Quarantined chunks are never stored; if one was stored before, it is deleted (fail closed)."""
    keep = [c for c in chunks if not c.quarantined]
    existing = {d.id: d.get("sig") for d in col.select(["sig"]).stream()}
    changed = [c for c in keep if existing.get(c.id) != _sig(c)]
    keep_ids = {c.id for c in keep}
    stale = sorted(i for i in existing if i not in keep_ids)
    return changed, len(keep) - len(changed), stale


def write_chunks(col, chunks: list[Chunk], vectors: list[list[float]], all_gens: list[str]) -> None:
    client = col._client
    batch = client.batch()
    n = 0
    for c, v in zip(chunks, vectors):
        doc = {
            "id": c.id, "topic_id": c.topic_id, "path": c.path, "line": c.line, "heading": c.heading,
            "text": c.text, "scope": c.scope, "origin": c.origin, "kind": c.kind, "sig": _sig(c),
            "embedding": Vector(v),
        }
        for g in all_gens:
            doc[f"in_{g}"] = g in c.scope
        batch.set(col.document(c.id), doc)
        n += 1
        if n % 400 == 0:
            batch.commit()
            batch = client.batch()
    batch.commit()


def delete_ids(col, ids: list[str]) -> None:
    client = col._client
    batch = client.batch()
    for i in ids:
        batch.delete(col.document(i))
    batch.commit()


def search(col, generation: str, query_vector: list[float], valid_generations: list[str], limit: int = 5) -> list[dict]:
    """Nearest chunks inside one generation. The equality pre-filter runs before the vector search."""
    if generation not in valid_generations:
        raise ValueError(f"unknown generation {generation!r}")
    q = col.where(filter=FieldFilter(f"in_{generation}", "==", True)).find_nearest(
        vector_field="embedding", query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE, limit=limit, distance_result_field="distance")
    out = []
    for d in q.stream():
        row = d.to_dict()
        if row.get(f"in_{generation}") is not True:       # belt and braces: never return out-of-scope text
            raise RuntimeError(f"out-of-scope chunk returned for {generation}: {d.id}")
        row.pop("embedding", None)
        out.append(row)
    return out
