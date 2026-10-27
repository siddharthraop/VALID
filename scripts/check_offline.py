"""Offline checks (no Google Cloud, no Gemini): scope resolution and scope isolation of the BM25 search.
  python scripts/check_offline.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config
from valid.retrieve import Corpus
from valid.scheme import load_scheme
from valid.scope import resolve_scope

scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
corpus = Corpus.load(scheme)

CASES = [
    ("I'm on Ironwood. Which --version do I pass when I create the VM?", ["tpu7x"]),
    ("How many chips are in one host?", []),
    ("Compare chips per host for v5p and TPU v6e", ["v5p", "v6e"]),
    ("Is ct5p-hightpu-4t right for Trillium?", ["v5p", "v6e"]),
    ("What about tpu 7x memory?", ["tpu7x"]),
    ("how many v5 chips", []),
]
bad = 0
for q, want in CASES:
    got = resolve_scope(q, scheme, corpus.owned).scope
    if got != want:
        bad += 1
        print(f"FAIL scope: {q!r} -> {got}, wanted {want}")

QUERIES = ["Which --version do I pass for Ironwood", "chips per host", "HBM capacity per chip",
           "create a VM", "tpu7x-standard-4t machine type", "v2-alpha-tpuv6e", "TensorFlow support"]
for g in scheme.keys:
    for q in QUERIES:
        for cid, _ in corpus.bm25.search(g, q, limit=20):
            if g not in corpus.chunks[cid]["scope"]:
                bad += 1
                print(f"FAIL isolation: {g} search returned {cid} (scope {corpus.chunks[cid]['scope']})")

print("offline checks passed" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
