"""Try the scope-filtered search.  python scripts/try_retrieve.py tpu7x "Which --version do I pass?" """
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config, gemini, store
from valid.scheme import load_scheme


def main() -> int:
    if len(sys.argv) != 3:
        print('usage: python scripts/try_retrieve.py <generation> "<question>"')
        return 2
    gen, question = sys.argv[1], sys.argv[2]
    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    col = store.db().collection(config.COLLECTION)
    rows = store.search(col, gen, gemini.embed_query(question), scheme.keys, limit=5)
    print(f"scope={gen} · {len(rows)} results (every one has in_{gen}=true)")
    for r in rows:
        print(f"  {r['distance']:.3f}  {r['id']:<48} scope={','.join(r['scope'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
