"""Calibrate the refusal floor: best vector distance for on-topic and off-topic questions (about 11 embedding calls).
  python scripts/calibrate.py"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config, gemini, store
from valid.scheme import load_scheme

ON = [("tpu7x", "How many chips are in one TPU7x VM?"), ("v6e", "How many chips are in one v6e host?"),
      ("v5p", "What is the HBM capacity per chip?"), ("v5e", "Which software version do I use to create a VM?"),
      ("tpu7x", "Does TPU7x support TensorFlow?"), ("v6e", "Which machine type do I use?")]
OFF = [("tpu7x", "What is the capital of France?"), ("v6e", "How do I bake sourdough bread?"),
       ("v5p", "Who won the 2024 World Series?"), ("tpu7x", "How do I configure Cloud NAT timeouts?"),
       ("v6e", "What is the hourly price of a v6e chip?")]


def main() -> int:
    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    col = store.db().collection(config.COLLECTION)
    for label, qs in (("ON-TOPIC", ON), ("OFF-TOPIC", OFF)):
        print(label)
        for g, q in qs:
            best = store.search(col, g, gemini.embed_query(q), scheme.keys, limit=1)[0]
            print(f"  {best['distance']:.3f}  [{g}] {q}  ->  {best['id']}")
            time.sleep(0.5)
    return 0


if __name__ == "__main__":
    sys.exit(main())
