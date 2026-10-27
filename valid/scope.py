"""resolve_scope: decide which generation(s) a question is about. No model call.

Matches the question against the subject scheme: generation names, other names such as
Trillium and Ironwood, and identifiers owned by one generation (machine types, version strings).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .scheme import Scheme


@dataclass
class ScopeResult:
    scope: list[str] = field(default_factory=list)                 # generations, in scheme order
    matched: list[tuple[str, str]] = field(default_factory=list)   # (words found in the question, generation)


def _pattern(term: str) -> re.Pattern:
    return re.compile(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])")


def resolve_scope(question: str, scheme: Scheme, owned: dict[str, str]) -> ScopeResult:
    terms: dict[str, str] = {}
    for g in scheme.generations:
        for a in g.aliases:
            terms[a] = g.key
    for ident, g in owned.items():
        terms[ident.lower()] = g
    q = question.lower()
    found: dict[str, str] = {}
    for term in sorted(terms, key=len, reverse=True):          # longest first: "tpu v6e" before "v6e"
        m = _pattern(term).search(q)
        if m:
            found[term] = terms[term]
            q = q[:m.start()] + " " * (m.end() - m.start()) + q[m.end():]   # a span matches once
    scope = [k for k in scheme.keys if k in set(found.values())]
    return ScopeResult(scope, [(t, g) for t, g in found.items()])
