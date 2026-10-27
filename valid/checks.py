"""check_answer: plain Python checks that decide pass or fail. The model cannot override them.

1. Every citation is in scope: the cited chunk was retrieved for the step's generation and applies to it.
2. Every number, unit, flag, version string, code span and command appears in the cited chunk.
3. No value owned by a generation outside the scope appears anywhere in the answer.

Known limit (design 5.9): numbers are checked against the cited chunk, but only identifiers
(version strings, machine types) are known to belong to one generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

FLAG = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")
IDENT = re.compile(r"(?<![A-Za-z0-9._-])[A-Za-z][A-Za-z0-9]*(?:[-._][A-Za-z0-9]+)+(?![A-Za-z0-9_-])")
SHAPE = re.compile(r"(?<![A-Za-z0-9])\d+(?:x\d+)+(?![A-Za-z0-9])")
NUM = re.compile(r"(?<![A-Za-z0-9._-])\d+(?:[.,]\d+)*(?![A-Za-z0-9])")
UNIT = re.compile(r"\d[\d.,]*\s*(GiB|GB|MiB|MB|TiB|TB/s|TB|GBps|Gbps|TFLOPs|PFLOPs|vCPUs?)(?![A-Za-z])")
CODE = re.compile(r"`([^`]+)`")


@dataclass
class Failure:
    step: int            # -1 = the summary answer
    check: str           # citation | grounding | out_of_scope | format
    reason: str

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class CheckResult:
    failures: list[Failure] = field(default_factory=list)
    citations: tuple[int, int] = (0, 0)
    values: tuple[int, int] = (0, 0)
    out_of_scope: int = 0

    @property
    def ok(self) -> bool:
        return not self.failures

    def summary(self) -> dict:
        return {"citations_in_scope": f"{self.citations[0]}/{self.citations[1]}",
                "values_grounded": f"{self.values[0]}/{self.values[1]}",
                "out_of_scope_values": self.out_of_scope}


def _norm(s: str) -> str:
    return " ".join(re.sub(r"\\\s*\n", " ", s).split())


def _nums(s: str) -> set[str]:
    return {n.replace(",", "") for n in NUM.findall(s)}


def extract_values(text: str) -> list[tuple[str, str]]:
    """(kind, value) for everything in the text that must be traceable to a source."""
    out: list[tuple[str, str]] = []
    out += [("flag", v) for v in FLAG.findall(text)]
    out += [("version/identifier", v) for v in IDENT.findall(text) if re.search(r"\d", v)]
    out += [("slice shape", v) for v in SHAPE.findall(text)]
    out += [("number", v.replace(",", "")) for v in NUM.findall(text)]
    out += [("unit", m) for m in UNIT.findall(text)]
    out += [("code", v) for v in CODE.findall(text)]
    return list(dict.fromkeys(out))


def _has(value_kind: str, value: str, chunk_text: str, chunk_nums: set[str]) -> bool:
    if value_kind == "number":
        return value in chunk_nums
    if value_kind == "code":
        return _norm(value) in _norm(chunk_text)
    return value in chunk_text


def _owned_hit(text: str, ident: str) -> bool:
    return re.search(rf"(?<![A-Za-z0-9._-]){re.escape(ident)}(?![A-Za-z0-9._-])", text) is not None


def check_answer(answer: dict, scope: list[str], retrieved: dict[str, list[str]],
                 chunks: dict[str, dict], owned: dict[str, str]) -> CheckResult:
    """answer: {"answer": str, "steps": [{"generation","text","cite","command"?}]}.
    retrieved: generation -> chunk ids that were retrieved for it."""
    res = CheckResult()
    steps = answer.get("steps") or []
    if not steps:
        res.failures.append(Failure(-1, "format", "an answer needs at least one cited step"))
    cited_texts: list[str] = []
    v_ok = v_total = c_ok = 0

    for i, st in enumerate(steps):
        gen, cite = st.get("generation"), st.get("cite")
        # 1. citation in scope
        chunk = chunks.get(cite)
        if gen not in scope:
            res.failures.append(Failure(i, "citation", f"generation {gen!r} is not in the question's scope {scope}"))
        elif cite not in retrieved.get(gen, []) or chunk is None or gen not in chunk["scope"]:
            res.failures.append(Failure(i, "citation", f"{cite!r} was not retrieved for {gen} or does not apply to {gen}"))
        else:
            c_ok += 1
        if chunk is None:
            continue
        cited_texts.append(chunk["text"])
        cn = _nums(chunk["text"])
        # 2. values grounded in the cited chunk
        vals = extract_values(st.get("text", ""))
        cmd = (st.get("command") or "").strip()
        if cmd:
            vals.append(("command", cmd))
        for kind, v in vals:
            v_total += 1
            ok = (_norm(cmd) in _norm(chunk["text"])) if kind == "command" else _has(kind, v, chunk["text"], cn)
            if ok:
                v_ok += 1
            else:
                res.failures.append(Failure(i, "grounding", f"{kind} {v!r} does not appear in the cited chunk {cite}"))

    # summary answer: grounded in the union of the cited chunks
    union = "\n".join(cited_texts)
    un = _nums(union)
    for kind, v in extract_values(answer.get("answer", "")):
        v_total += 1
        if _has(kind, v, union, un):
            v_ok += 1
        else:
            res.failures.append(Failure(-1, "grounding", f"{kind} {v!r} in the summary does not appear in any cited chunk"))

    # 3. no value owned by an out-of-scope generation, anywhere
    blob = [("answer", answer.get("answer", ""))] + \
           [(f"step {i + 1}", f"{s.get('text', '')} {s.get('command', '')}") for i, s in enumerate(steps)]
    for where, text in blob:
        for ident, g in owned.items():
            if g not in scope and _owned_hit(text, ident):
                res.out_of_scope += 1
                res.failures.append(Failure(-1 if where == "answer" else int(where.split()[1]) - 1, "out_of_scope",
                                            f"{ident!r} belongs to {g}, which is outside this question's scope"))
    res.citations = (c_ok, len(steps))
    res.values = (v_ok, v_total)
    return res
