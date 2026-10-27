"""Subject scheme reader: the single list of generations (and their other names) VALID uses.

The scheme is owned by the information architect. Nothing in VALID hard-codes a generation.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

PARSER = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)


@dataclass
class Generation:
    key: str                      # e.g. "tpu7x" -- the @platform value
    name: str                     # e.g. "TPU7x (Ironwood)"
    aliases: list[str] = field(default_factory=list)  # lower-case names used to match questions


@dataclass
class Scheme:
    generations: list[Generation]

    @property
    def keys(self) -> list[str]:
        return [g.key for g in self.generations]


def _aliases(key: str, name: str) -> list[str]:
    out = {key.lower(), name.lower()}
    m = re.match(r"^(.*?)\s*\((.*?)\)\s*$", name)
    if m:                                     # "TPU v6e (Trillium)" -> "tpu v6e", "trillium"
        out.add(m.group(1).lower())
        out.add(m.group(2).lower())
    out.add(("tpu " + key).lower() if not key.lower().startswith("tpu") else "tpu " + key.lower()[3:])
    if not key.lower().startswith("tpu"):
        out.add(("tpu" + key).lower())
    return sorted(a.strip() for a in out if a.strip())


def load_scheme(path: Path) -> Scheme:
    tree = etree.parse(str(path), PARSER)
    by_key = {sd.get("keys"): sd for sd in tree.iter("subjectdef") if sd.get("keys")}
    for enum in tree.iter("enumerationdef"):
        att = enum.find("attributedef")
        if att is None or att.get("name") != "platform":
            continue
        ref = enum.find("subjectdef").get("keyref")
        root_def = by_key[ref]
        gens = []
        for d in root_def.iter("subjectdef"):
            if d is root_def or not d.get("keys"):
                continue
            name = (d.findtext("topicmeta/navtitle") or d.get("keys")).strip()
            gens.append(Generation(d.get("keys"), name, _aliases(d.get("keys"), name)))
        if gens:
            return Scheme(gens)
    raise ValueError(f"{path}: no enumerationdef for @platform")
