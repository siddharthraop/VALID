"""resolve_profiles: read the DITA maps and topics and produce scoped chunks.

Order of work (design 5.2):
  1. Map cascading: @platform on a <topicref> applies to every topic under it.
  2. Element profiling: @platform on a step, row, section or block narrows that chunk.
  3. No attribute: in scope for every generation (and checked later by audit_scope).
  4. Subject scheme: any @platform value not in the scheme fails the build.

Keys and conrefs are resolved first, so chunk text holds the real values, not key names.
No model is involved anywhere in this file.
"""
from __future__ import annotations

import copy
import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

from .scheme import Scheme

PARSER = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False,
                         remove_comments=True, remove_pis=True)

INLINE = {"keyword", "ph", "codeph", "varname", "b", "i", "u", "xref", "term", "cite", "uicontrol",
          "filepath", "option", "parmname", "systemoutput", "userinput", "q", "tm", "sub", "sup",
          "apiname", "cmdname", "msgph", "menucascade"}
SKIP = {"prolog", "title", "shortdesc", "abstract", "titlealts", "data", "indexterm", "related-links",
        "draft-comment", "required-cleanup", "alt", "desc"}
UNIT_TAGS = {"section", "example", "prereq", "context", "result", "postreq", "stepresult", "info"}
META_TAGS = {"title", "shortdesc", "abstract", "prolog", "titlealts", "related-links"}


class ProfileError(Exception):
    """Raised when the build must fail (e.g. a profiling value not in the subject scheme)."""


@dataclass
class Chunk:
    id: str
    topic_id: str
    path: str              # source file, relative to the corpus root
    line: int
    heading: str
    text: str
    scope: list[str]       # generations this chunk applies to
    origin: str            # "map" | "element" | "shared"
    key_gens: list[str]    # generations whose key values appear in the text
    kind: str              # intro | section | steps | table | body
    hash: str = ""
    quarantined: bool = False

    def to_dict(self) -> dict:
        return self.__dict__.copy()


@dataclass
class Result:
    chunks: list[Chunk] = field(default_factory=list)
    keys: dict[str, str] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    topics: int = 0


# ---------------------------------------------------------------- parsing helpers
def _parse(path: Path, corpus: Path) -> etree._Element:
    root = etree.parse(str(path), PARSER).getroot()
    rel = str(path.resolve().relative_to(corpus))
    for el in root.iter():
        if isinstance(el.tag, str):
            el.set("_ln", str(el.sourceline))
            el.set("_f", rel)
    return root


def key_gen(key: str, gens: list[str]) -> str | None:
    """Which generation owns a key, from its name: 'v6e-runtime' -> v6e. 'product-*' names are not values."""
    if key.startswith("product-"):
        return None
    for g in gens:
        if key.startswith(g + "-") or key.endswith("-" + g):
            return g
    return None


def load_keys(map_path: Path, corpus: Path) -> dict[str, str]:
    """All keydefs from key maps referenced by the root map (mapref, not the subject scheme)."""
    root = _parse(map_path, corpus)
    keys: dict[str, str] = {}
    for mr in root.iter("mapref"):
        if mr.get("type") == "subjectScheme":
            continue
        kp = (map_path.parent / mr.get("href")).resolve()
        for kd in _parse(kp, corpus).iter("keydef"):
            val = " ".join("".join(kd.itertext()).split())
            for k in kd.get("keys", "").split():
                keys[k] = val
    return keys


def _norm(s: str) -> str:
    return " ".join(s.split())


# ---------------------------------------------------------------- conref and keyref
def _resolve_conrefs(root: etree._Element, corpus: Path, cache: dict) -> None:
    for _ in range(6):
        pending = [e for e in root.iter() if isinstance(e.tag, str) and e.get("conref")]
        if not pending:
            return
        for el in pending:
            href = el.get("conref")
            fpart, _, frag = href.partition("#")
            base = corpus / el.get("_f")
            tpath = (base.parent / fpart).resolve() if fpart else base
            if tpath not in cache:
                cache[tpath] = _parse(tpath, corpus)
            troot = cache[tpath]
            elem_id = frag.split("/")[-1] if frag else None
            target = troot if (not elem_id or "/" not in frag and troot.get("id") == elem_id) else None
            if target is None:
                hits = troot.xpath(f"//*[@id='{elem_id}']")
                if not hits:
                    raise ProfileError(f"{el.get('_f')}:{el.get('_ln')}: conref target not found: {href}")
                target = hits[0]
            new = copy.deepcopy(target)
            new.attrib.pop("id", None)
            for k, v in el.attrib.items():          # the referencing element's attributes win
                if k != "conref" and k != "id":
                    new.set(k, v)
            new.tail = el.tail
            el.getparent().replace(el, new)
    raise ProfileError(f"{root.get('_f')}: conref nesting deeper than 6")


def _resolve_keyrefs(root: etree._Element, keys: dict[str, str], gens: list[str], warnings: list[str]) -> None:
    for el in root.iter():
        if not isinstance(el.tag, str):
            continue
        kr = el.get("keyref")
        if not kr or el.tag == "xref":
            continue
        if kr not in keys:
            warnings.append(f"{el.get('_f')}:{el.get('_ln')}: keyref '{kr}' is not defined")
            continue
        if len(el) == 0 and not (el.text or "").strip():
            el.text = keys[kr]
        g = key_gen(kr, gens)
        if g:
            el.set("_kg", g)


# ---------------------------------------------------------------- scope
def _narrow(parent: frozenset, el: etree._Element, allowed: frozenset, where: str) -> frozenset:
    v = el.get("platform")
    if not v:
        return parent
    vals = set(v.split())
    bad = vals - allowed
    if bad:
        raise ProfileError(f"{where}:{el.get('_ln', '?')}: platform value(s) {sorted(bad)} "
                           f"are not in the subject scheme {sorted(allowed)}")
    return frozenset(parent & vals)


def _topic_scopes(map_path: Path, corpus: Path, allowed: frozenset) -> dict[Path, frozenset]:
    """Map cascading. Reltables and resource-only entries are not content."""
    out: dict[Path, frozenset] = {}
    root = _parse(map_path, corpus)

    def walk(node: etree._Element, scope: frozenset) -> None:
        for ch in node:
            if not isinstance(ch.tag, str) or ch.tag in ("reltable", "topicmeta", "mapref", "title"):
                continue
            if ch.get("processing-role") == "resource-only":
                continue
            sc = _narrow(scope, ch, allowed, str(map_path.name))
            href = ch.get("href", "")
            if ch.tag == "topicref" and href.endswith(".dita"):
                p = (map_path.parent / href.partition("#")[0]).resolve()
                out.setdefault(p, sc)
            walk(ch, sc)

    walk(root, allowed)
    return out


# ---------------------------------------------------------------- rendering
def _text(el) -> str:
    return _norm("".join(el.itertext()))


def render(el: etree._Element) -> str:
    t = el.tag
    if t in SKIP:
        return ""
    if t == "codeblock":
        return "```\n" + "".join(el.itertext()).strip("\n") + "\n```"
    if t in ("ul", "ol", "sl"):
        lines = []
        for i, li in enumerate((c for c in el if isinstance(c.tag, str) and c.tag in ("li", "sli")), 1):
            lines.append(("- " if t != "ol" else f"{i}. ") + _norm(render(li).replace("\n", " ")))
        return "\n".join(lines)
    if t == "note":
        return f"{(el.get('type') or 'note').capitalize()}: " + _norm(_container(el))
    if t == "image":
        if "pdf" in (el.get("deliveryTarget") or ""):
            return ""
        alt = el.findtext("alt")
        return f"[Image: {_norm(alt)}]" if alt else ""
    if t == "object":
        return ""
    if t == "table":
        return "\n".join(line for _, rows, _e in _table_groups(el, frozenset(), frozenset(), "") for line in rows)
    return _container(el)


def _container(el: etree._Element) -> str:
    pieces, buf = [], el.text or ""
    for ch in el:
        if not isinstance(ch.tag, str):
            buf += ch.tail or ""
            continue
        if ch.tag in INLINE:
            buf += "".join(ch.itertext()) + (ch.tail or "")
            continue
        if _norm(buf):
            pieces.append(_norm(buf))
        r = render(ch)
        if r:
            pieces.append(r)
        buf = ch.tail or ""
    if _norm(buf):
        pieces.append(_norm(buf))
    return "\n".join(pieces)


def _step_text(step: etree._Element) -> str:
    parts = []
    for ch in step:
        if not isinstance(ch.tag, str):
            continue
        r = render(ch)
        if r:
            parts.append(r)
    opt = " (optional)" if step.get("importance") == "optional" else ""
    return "Step" + opt + ": " + "\n".join(parts)


def _table_groups(tbl, parent_scope, allowed, where):
    """Rows grouped by effective scope. Each row becomes 'Header: value; Header: value'."""
    tg = tbl.find("tgroup")
    heads = [_text(e) for e in tg.findall("thead/row/entry")] if tg is not None else []
    groups: dict[frozenset, list] = {}
    for row in (tg.findall("tbody/row") if tg is not None else []):
        sc = _narrow(parent_scope, row, allowed, where) if allowed else parent_scope
        cells = []
        for i, e in enumerate(row.findall("entry")):
            c = _text(e)
            if c:
                h = heads[i] if i < len(heads) and heads[i] else f"column {i + 1}"
                cells.append(f"{h}: {c}")
        if cells:
            groups.setdefault(sc, []).append(("; ".join(cells), row))
    return [(sc, [t for t, _ in v], [r for _, r in v]) for sc, v in groups.items()]


# ---------------------------------------------------------------- chunking
def _chunk_topic(root: etree._Element, topic_scope: frozenset, allowed: frozenset, res: Result) -> None:
    path = root.get("_f")
    tid = root.get("id") or Path(path).stem
    title = _text(root.find("title")) if root.find("title") is not None else tid
    counters: dict[str, int] = {}
    scope0 = _narrow(topic_scope, root, allowed, path)

    def emit(unit_key, heading, scope, elems, text, kind, line):
        text = text.strip()
        if not text or not scope:
            if text and not scope:
                res.warnings.append(f"{path}:{line}: empty scope (profiling conflicts with the map), chunk dropped")
            return
        n = counters.get(unit_key, 0)
        counters[unit_key] = n + 1
        cid = f"{tid}#{unit_key}" + (f".{n}" if n else "")
        kg = sorted({e.get("_kg") for x in elems for e in x.iter() if isinstance(e.tag, str) and e.get("_kg")})
        full = f"{title} > {heading}\n{text}" if heading and heading != title else f"{title}\n{text}"
        origin = "element" if scope != topic_scope else ("map" if topic_scope != allowed else "shared")
        ordered = [g for g in sorted(scope)]
        h = hashlib.sha256((full + "|" + ",".join(ordered)).encode()).hexdigest()[:16]
        res.chunks.append(Chunk(cid, tid, path, line, heading or title, full, ordered, origin, kg, kind, h))

    def blocks(unit_key, heading, unit_scope, container, kind="section"):
        group: list[etree._Element] = []
        gscope = None

        def flush():
            nonlocal group, gscope
            if group:
                emit(unit_key, heading, gscope, group, "\n".join(r for r in (render(b) for b in group) if r),
                     kind, int(group[0].get("_ln", 0)))
            group, gscope = [], None

        for b in container:
            if not isinstance(b.tag, str) or b.tag in SKIP:
                continue
            bs = _narrow(unit_scope, b, allowed, path)
            if b.tag == "table":
                flush()
                for sc, rows, row_els in _table_groups(b, unit_scope, allowed, path):
                    tt = b.get("id") or "table"
                    emit(f"{unit_key}-{tt}" if unit_key != tt else unit_key, heading, sc, row_els, "\n".join(rows),
                         "table", int(b.get("_ln", 0)))
                continue
            if b.tag == "steps":
                flush()
                for i, st in enumerate((s for s in b if isinstance(s.tag, str) and s.tag == "step"), 1):
                    ss = _narrow(unit_scope, st, allowed, path)
                    emit(f"{unit_key}-step{i}", heading, ss, [st], _step_text(st), "steps", int(st.get("_ln", 0)))
                continue
            if b.tag in UNIT_TAGS:
                flush()
                sub = (b.findtext("title") or b.tag).strip()
                blocks(b.get("id") or b.tag, sub, bs, b, "section")
                continue
            if gscope is not None and bs != gscope:
                flush()
            gscope = bs
            group.append(b)
        flush()

    # intro: title + shortdesc
    sd = root.find("shortdesc")
    intro = _norm(" ".join(x for x in (_text(sd) if sd is not None else "",) if x))
    emit("intro", title, scope0, [root.find("title")] + ([sd] if sd is not None else []), intro, "intro",
         int(root.get("_ln", 0)))

    for body in root:
        if not isinstance(body.tag, str) or body.tag in META_TAGS:
            continue
        blocks("body", title, scope0, body, "body")


# ---------------------------------------------------------------- entry point
def build_chunks(corpus: Path, root_map: str, scheme: Scheme) -> Result:
    res = Result()
    allowed = frozenset(scheme.keys)
    map_path = (corpus / root_map).resolve()
    res.keys = load_keys(map_path, corpus)
    scopes = _topic_scopes(map_path, corpus, allowed)
    cache: dict = {}
    for p, scope in scopes.items():
        root = _parse(p, corpus)
        _resolve_conrefs(root, corpus, cache)
        _resolve_keyrefs(root, res.keys, scheme.keys, res.warnings)
        _chunk_topic(root, scope, allowed, res)
        res.topics += 1
    return res
