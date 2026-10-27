"""Write data/chunks.jsonl: the retrievable (non-quarantined) chunks, no vectors. The runtime loads this
file for BM25 and for the chunk text, so it never needs Firestore reads at start-up.
Re-run it whenever the corpus changes.  python scripts/export_data.py"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config
from valid.audit import audit_scope
from valid.dita import ProfileError, build_chunks
from valid.scheme import load_scheme


def main() -> int:
    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    try:
        res = build_chunks(config.CORPUS_DIR, config.ROOT_MAP, scheme)
    except ProfileError as e:
        print(f"BUILD FAILED: {e}")
        return 1
    findings = audit_scope(res.chunks, res.keys, scheme)
    out = config.DATA_DIR
    out.mkdir(exist_ok=True)
    keep = [c for c in res.chunks if not c.quarantined]
    with open(out / "chunks.jsonl", "w") as f:
        for c in keep:
            f.write(json.dumps(c.to_dict()) + "\n")
    # Values owned by exactly one generation (identifiers, from the keys): used by check_answer.
    from valid.audit import owned_identifiers
    (out / "owned.json").write_text(json.dumps(owned_identifiers(res.keys, scheme), indent=1, sort_keys=True))
    print(f"wrote {len(keep)} chunks ({len(findings)} findings, {len(res.chunks) - len(keep)} quarantined) to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
