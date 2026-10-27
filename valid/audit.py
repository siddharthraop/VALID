"""audit_scope: find chunks that hold a value owned by a generation outside the chunk's scope.

DITA treats content with no @platform as shared, which is right for a build and dangerous
for an answer. A shared chunk that states a one-generation value (a version string, a machine
type, a spec from a generation key) is reported, and the chunk is quarantined so retrieval
never returns it. Quarantine fails closed: the answer is withheld until a writer fixes the profiling.

Known limit (design section 5.9): this finds values it can recognise (key values and
identifiers), not a plain-language sentence that is wrong for one generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .dita import Chunk, key_gen
from .scheme import Scheme

IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{4,}$")


@dataclass
class Finding:
    chunk_id: str
    path: str
    line: int
    kind: str      # unscoped-value | out-of-scope-value
    detail: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


def owned_identifiers(keys: dict[str, str], scheme: Scheme) -> dict[str, str]:
    """Identifier-like key values (version strings, machine types, slice shapes) owned by exactly one generation."""
    seen: dict[str, set[str]] = {}
    for k, v in keys.items():
        g = key_gen(k, scheme.keys)
        if g and IDENT.match(v) and re.search(r"[A-Za-z]", v) and re.search(r"[\d-]", v):
            seen.setdefault(v, set()).add(g)
    return {v: next(iter(gs)) for v, gs in seen.items() if len(gs) == 1}


def _find(text: str, ident: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9._-]){re.escape(ident)}(?![A-Za-z0-9._-])", text) is not None


def audit_scope(chunks: list[Chunk], keys: dict[str, str], scheme: Scheme) -> list[Finding]:
    owned = owned_identifiers(keys, scheme)
    everything = set(scheme.keys)
    findings: list[Finding] = []
    for c in chunks:
        scope = set(c.scope)
        found: dict[str, list[str]] = {g: [] for g in c.key_gens}
        for g in c.key_gens:
            found[g].append("key value")
        for ident, g in owned.items():
            if _find(c.text, ident):
                found.setdefault(g, []).append(ident)
        if not found:
            continue
        if scope == everything:
            who = ", ".join(f"{g} ({'; '.join(sorted(set(v)))})" for g, v in sorted(found.items()))
            findings.append(Finding(c.id, c.path, c.line, "unscoped-value",
                                    f"chunk is in scope for every generation but holds values owned by: {who}"))
            c.quarantined = True
        else:
            leak = {g: v for g, v in found.items() if g not in scope}
            if leak:
                who = ", ".join(f"{g} ({'; '.join(sorted(set(v)))})" for g, v in sorted(leak.items()))
                findings.append(Finding(c.id, c.path, c.line, "out-of-scope-value",
                                        f"chunk scoped to {sorted(scope)} holds values owned by: {who}"))
                c.quarantined = True
    return findings
