"""Hybrid search inside the scope: vector + BM25 fused.
  python scripts/try_search.py "question"             # scope from the question
  python scripts/try_search.py "question" tpu7x       # force one generation"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config, store
from valid.retrieve import Corpus, retrieve_in_scope
from valid.scheme import load_scheme
from valid.scope import resolve_scope


def main() -> int:
    if len(sys.argv) not in (2, 3):
        print('usage: python scripts/try_search.py "<question>" [generation]')
        return 2
    question = sys.argv[1]
    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    corpus = Corpus.load(scheme)
    if len(sys.argv) == 3:
        gens, matched = [sys.argv[2]], "forced"
    else:
        r = resolve_scope(question, scheme, corpus.owned)
        gens, matched = r.scope, r.matched
    print(f"scope: {gens or 'none'}   matched: {matched}")
    if not gens:
        print("no generation in the question: VALID would ask the reader to choose one")
        return 0
    col = store.db().collection(config.COLLECTION)
    for g, hits in retrieve_in_scope(question, gens, scheme, corpus, col).items():
        print(f"\n[{g}] fused top {len(hits)}   (vec = vector rank/distance, bm25 = keyword rank)")
        for h in hits:
            vec = f"{h.vec_rank}/{h.vec_distance:.3f}" if h.vec_rank else "-"
            print(f"  rrf {h.rrf:.4f}  vec {vec:<10} bm25 {h.bm25_rank or '-':<3} {h.id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
