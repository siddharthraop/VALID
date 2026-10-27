"""The agent loop (design 5.5): resolve scope, search inside it, let Gemini phrase the answer, let the checks decide.

Three ways out and only one is an answer: ask the reader which generation, refuse and say what is missing,
or send a checked answer. A failed step goes back to Gemini with its reason, up to twice, with the same
in-scope chunks. The search is never widened to fix a failure.
"""
from __future__ import annotations

import time

from . import config
from .answer import ModelUnavailable, generate_answer
from .checks import check_answer
from .retrieve import Corpus, Hit, retrieve_in_scope
from .scheme import Scheme
from .scope import resolve_scope

# Paid-tier list prices per 1M tokens (in, out) while on the free tier the real cost is 0. Informational.
PRICE_IN, PRICE_OUT = 0.75, 3.75


class Agent:
    def __init__(self, scheme: Scheme, corpus: Corpus, col, retriever=retrieve_in_scope, generator=generate_answer):
        self.scheme, self.corpus, self.col = scheme, corpus, col
        self.retriever, self.generator = retriever, generator
        self.names = {g.key: g.name for g in scheme.generations}

    # ------------------------------------------------------------------
    def ask(self, question: str, generations: list[str] | None = None) -> dict:
        t0 = time.time()
        trace: list[dict] = []
        run = {"model": config.ANSWER_MODEL, "calls": 0, "tokens_in": 0, "tokens_out": 0}

        def step(title: str, detail, t_start: float) -> None:
            trace.append({"step": title, "ms": int((time.time() - t_start) * 1000), "detail": detail})

        def done(outcome: str, **extra) -> dict:
            run["ms"] = int((time.time() - t0) * 1000)
            run["est_cost_usd_if_paid"] = round((run["tokens_in"] * PRICE_IN + run["tokens_out"] * PRICE_OUT) / 1e6, 5)
            return {"outcome": outcome, "question": question, "scope": scope, "matched": matched,
                    "trace": trace, "run": run, **extra}

        # 1. decide the scope (no model call)
        t = time.time()
        if generations:
            bad = [g for g in generations if g not in self.scheme.keys]
            if bad:
                raise ValueError(f"unknown generation(s): {bad}")
            scope, matched = [g for g in self.scheme.keys if g in generations], [("chosen by the reader", g) for g in generations]
        else:
            r = resolve_scope(question, self.scheme, self.corpus.owned)
            scope, matched = r.scope, [list(m) for m in r.matched]
        step("Decide the scope", {"scope": scope or None, "matched words": matched or None,
                                  "how": "subject scheme match, no model call"}, t)

        # 2. no scope: ask the reader
        if not scope:
            return done("ask", ask={"message": "Which TPU generation do you mean? The answer differs between generations.",
                                    "options": [{"key": g.key, "name": g.name} for g in self.scheme.generations]})

        # 3. search inside the scope only
        t = time.time()
        hits = self.retriever(question, scope, self.scheme, self.corpus, self.col, k=config.RETRIEVE_K)
        best = min([h.vec_distance for g in scope for h in hits[g] if h.vec_distance is not None], default=None)
        step("Search inside the scope", {
            "filter": "in_" + " / in_".join(scope) + " == true, applied before the vector search",
            "best vector distance": None if best is None else round(best, 3),
            "refusal floor": config.MAX_DISTANCE,
            "retrieved": {g: [self._hit(h) for h in hits[g]] for g in scope}}, t)
        if best is None or best > config.MAX_DISTANCE:
            return done("refuse", refusal={
                "reason": "No content for this scope is close enough to the question.",
                "missing": "The documentation set has nothing on this topic for " + ", ".join(self.names[g] for g in scope) + "."})

        retrieved_ids = {g: [h.id for h in hits[g]] for g in scope}
        prior, failures = None, None
        for attempt in range(config.MAX_REVISIONS + 1):
            t = time.time()
            try:
                ans, usage = self.generator(question, scope, hits, prior, failures)
            except ModelUnavailable as e:
                step(f"Gemini call {attempt + 1}", {"error": str(e), "attempts": e.attempts}, t)
                run["calls"] += 1
                return done("unavailable", error={
                    "reason": "The answer model is busy right now (free-tier capacity). Nothing was answered.",
                    "action": "Try again in a minute."})
            except ValueError as e:
                step(f"Gemini call {attempt + 1}", {"error": str(e)}, t)
                prior, failures = None, [{"step": -1, "reason": str(e)}]
                run["calls"] += 1
                continue
            run["calls"] += 1
            run["tokens_in"] += usage["tokens_in"]
            run["tokens_out"] += usage["tokens_out"]
            run["model"] = usage.get("model", run["model"])
            step(f"Gemini call {attempt + 1}" + (" (revision)" if attempt else ""),
                 {"model": usage.get("model"), "attempts": usage.get("attempts"),
                  "answerable": ans.get("answerable"), "steps drafted": len(ans.get("steps") or [])}, t)

            if not ans.get("answerable", False):
                return done("refuse", refusal={
                    "reason": "The in-scope documentation does not answer this question.",
                    "missing": ans.get("missing") or "The retrieved content does not cover it."})

            t = time.time()
            chk = check_answer(ans, scope, retrieved_ids, self.corpus.chunks, self.corpus.owned)
            step("Check the answer", {"passed": chk.ok, **chk.summary(),
                                      "failed": [f.to_dict() for f in chk.failures] or None}, t)
            if chk.ok:
                steps = []
                for s in ans["steps"]:
                    c = self.corpus.chunks[s["cite"]]
                    steps.append({**s, "source": {"id": c["id"], "heading": c["heading"], "path": c["path"], "line": c["line"]}})
                others = [self.names[g] for g in self.scheme.keys if g not in scope]
                return done("answer", answer={
                    "text": ans["answer"], "steps": steps, "checks": chk.summary(),
                    "not_used": f"Content for {', '.join(others)} was excluded on purpose: out of scope for this question."})
            prior, failures = ans, [f.to_dict() for f in chk.failures]

        return done("refuse", refusal={
            "reason": "A draft answer could not be verified against the in-scope documentation after "
                      f"{config.MAX_REVISIONS} revisions, so nothing is sent.",
            "missing": "; ".join(f["reason"] for f in (failures or [])[:3])})

    @staticmethod
    def _hit(h: Hit) -> dict:
        return {"id": h.id, "heading": h.heading, "applies_to": h.scope,
                "vector": None if h.vec_rank is None else {"rank": h.vec_rank, "distance": round(h.vec_distance, 3)},
                "keyword_rank": h.bm25_rank, "fused_score": round(h.rrf, 4)}
