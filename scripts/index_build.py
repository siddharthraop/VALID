"""embed_chunks: build chunks, audit scope, embed only changed chunks, sync Firestore.
  python scripts/index_build.py --dry   # plan only: no Gemini calls, no writes
  python scripts/index_build.py         # embed changed chunks and write them"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config, gemini, store
from valid.audit import audit_scope
from valid.dita import ProfileError, build_chunks
from valid.scheme import load_scheme


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry", action="store_true")
    args = ap.parse_args()

    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    try:
        res = build_chunks(config.CORPUS_DIR, config.ROOT_MAP, scheme)
    except ProfileError as e:
        print(f"BUILD FAILED: {e}")
        return 1
    findings = audit_scope(res.chunks, res.keys, scheme)
    col = store.db().collection(config.COLLECTION)
    changed, unchanged, stale = store.plan_sync(col, res.chunks)
    print(f"{len(res.chunks)} chunks · {sum(c.quarantined for c in res.chunks)} quarantined ({len(findings)} findings) · "
          f"to embed: {len(changed)} · unchanged: {unchanged} · to delete: {len(stale)}")
    if args.dry:
        print("dry run: nothing sent to Gemini, nothing written")
        return 0
    if changed:
        vecs = gemini.embed_documents([(c.heading, c.text) for c in changed])
        store.write_chunks(col, changed, vecs, scheme.keys)
        print(f"embedded and wrote {len(changed)} chunks")
    if stale:
        store.delete_ids(col, stale)
        print(f"deleted {len(stale)} stale chunks")
    print("done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
