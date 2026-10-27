"""Dry run of the index build: resolve_profiles + audit_scope. No Google Cloud, no model calls.

  python scripts/index_report.py                 # summary report
  python scripts/index_report.py --show create   # print chunks whose id contains 'create'
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config
from valid.audit import audit_scope
from valid.dita import ProfileError, build_chunks
from valid.scheme import load_scheme


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", help="print full text of chunks whose id contains this string")
    args = ap.parse_args()

    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    try:
        res = build_chunks(config.CORPUS_DIR, config.ROOT_MAP, scheme)
    except ProfileError as e:
        print(f"BUILD FAILED: {e}")
        return 1
    findings = audit_scope(res.chunks, res.keys, scheme)

    config.BUILD_DIR.mkdir(exist_ok=True)
    with open(config.BUILD_DIR / "chunks.jsonl", "w") as f:
        for c in res.chunks:
            f.write(json.dumps(c.to_dict()) + "\n")
    (config.BUILD_DIR / "findings.json").write_text(json.dumps([x.to_dict() for x in findings], indent=2))

    if args.show:
        for c in res.chunks:
            if args.show in c.id:
                print(f"--- {c.id}  scope={c.scope}  origin={c.origin}  quarantined={c.quarantined}\n{c.text}\n")
        return 0

    origin = Counter(c.origin for c in res.chunks)
    per_gen = {g: sum(1 for c in res.chunks if g in c.scope and not c.quarantined) for g in scheme.keys}
    print(f"Index dry run · {res.topics} topics · {len(res.keys)} keys")
    print(f"  {len(res.chunks)} chunks · generations in scheme: {', '.join(scheme.keys)}")
    print(f"  Cascaded from map: {origin['map']} · narrowed by element: {origin['element']} · shared, no attribute: {origin['shared']}")
    print(f"  Retrievable per generation: {per_gen}")
    print(f"  Quarantined: {sum(c.quarantined for c in res.chunks)} · scope findings: {len(findings)}")
    for x in findings:
        print(f"  FINDING {x.path}:{x.line} [{x.chunk_id}] {x.detail}")
    for w in res.warnings:
        print(f"  WARNING {w}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
