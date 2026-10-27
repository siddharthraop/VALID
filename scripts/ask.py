"""Ask VALID a question from the terminal.
  python scripts/ask.py "question"            # scope from the question
  python scripts/ask.py "question" tpu7x      # reader picks a generation (comma-separate for two)
  add --trace to see every step"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config, store
from valid.agent import Agent
from valid.retrieve import Corpus
from valid.scheme import load_scheme


def main() -> int:
    args = [a for a in sys.argv[1:] if a != "--trace"]
    if not args:
        print('usage: python scripts/ask.py "<question>" [generation[,generation]] [--trace]')
        return 2
    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    agent = Agent(scheme, Corpus.load(scheme), store.db().collection(config.COLLECTION))
    r = agent.ask(args[0], args[1].split(",") if len(args) > 1 else None)
    print(f"outcome: {r['outcome'].upper()}   scope: {r['scope'] or '-'}")
    if r["outcome"] == "answer":
        a = r["answer"]
        print(f"\n{a['text']}\n")
        for s in a["steps"]:
            print(f"  [{s['generation']}] {s['text']}")
            if s.get("command"):
                print(f"      $ {s['command']}")
            print(f"      cite: {s['source']['id']}  ({s['source']['path']}:{s['source']['line']})")
        print(f"\nchecks: {a['checks']}\n{a['not_used']}")
    elif r["outcome"] == "unavailable":
        print(r["error"]["reason"], r["error"]["action"])
    elif r["outcome"] == "ask":
        print(r["ask"]["message"], [o["key"] for o in r["ask"]["options"]])
    else:
        print(r["refusal"]["reason"], "\n  missing:", r["refusal"]["missing"])
    print(f"\nrun: {r['run']}")
    for t in r["trace"]:
        att = t["detail"].get("attempts") if isinstance(t["detail"], dict) else None
        if att:
            print("models: " + "; ".join(f"{a['model']} {a['result']}" + (f" {a['ms']}ms" if 'ms' in a else "") for a in att))
    if "--trace" in sys.argv:
        print(json.dumps(r["trace"], indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
