"""BM25 over the same scope fields (SQLite FTS5). Exact terms (flags, machine types, versions) that dense vectors blur."""
from __future__ import annotations

import re
import sqlite3

STOP = set("a an the is are was were be do does did i my me we our you your it its of to in on for with and or "
           "what which how when where why can should would that this these those there than then".split())


class Bm25Index:
    def __init__(self, chunks: list[dict], gens: list[str]):
        for g in gens:
            if not re.fullmatch(r"[a-z0-9]+", g):
                raise ValueError(f"generation key not safe for SQL column: {g!r}")
        self.gens = list(gens)
        self.con = sqlite3.connect(":memory:", check_same_thread=False)
        cols = ", ".join(f"in_{g} INTEGER" for g in gens)
        self.con.execute("CREATE VIRTUAL TABLE fts USING fts5(body)")
        self.con.execute(f"CREATE TABLE meta(rowid INTEGER PRIMARY KEY, id TEXT, {cols})")
        for i, c in enumerate(chunks, 1):
            self.con.execute("INSERT INTO fts(rowid, body) VALUES (?, ?)", (i, f"{c['heading']}\n{c['text']}"))
            flags = [1 if g in c["scope"] else 0 for g in gens]
            self.con.execute(f"INSERT INTO meta VALUES (?, ?, {', '.join('?' * len(gens))})", (i, c["id"], *flags))
        self.con.commit()

    @staticmethod
    def match_query(question: str) -> str:
        toks = [t for t in re.findall(r"[a-z0-9]+", question.lower()) if t not in STOP]
        return " OR ".join(f'"{t}"' for t in dict.fromkeys(toks))

    def search(self, generation: str, question: str, limit: int = 8) -> list[tuple[str, float]]:
        """Chunk ids and bm25 scores (lower is better) inside one generation. The scope filter is always applied."""
        if generation not in self.gens:
            raise ValueError(f"unknown generation {generation!r}")
        q = self.match_query(question)
        if not q:
            return []
        rows = self.con.execute(
            f"SELECT meta.id, bm25(fts) AS s FROM fts JOIN meta ON meta.rowid = fts.rowid "
            f"WHERE fts MATCH ? AND meta.in_{generation} = 1 ORDER BY s LIMIT ?", (q, limit)).fetchall()
        return [(r[0], r[1]) for r in rows]
