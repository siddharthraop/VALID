"""Offline checks of check_answer and the agent loop, with a scripted Gemini and a fake search.
No Google Cloud, no Gemini, no cost.  python scripts/check_agent.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config
from valid.agent import Agent
from valid.checks import check_answer
from valid.retrieve import Corpus, Hit
from valid.scheme import load_scheme

scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
corpus = Corpus.load(scheme)
bad = 0


def expect(name, cond, detail=""):
    global bad
    if not cond:
        bad += 1
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if (detail and not cond) else ""))


IDS = {
    "tpu7x": ["tpu-create-vm#body-step5", "tpu-software-versions#versions.1",
              "tpu-software-versions#versions-table.3", "tpu7x-vm-types#vm-types-table"],
    "v6e": ["tpu-create-vm#body-step4", "tpu-v6e-vm-types#vm-types-table"],
}


def fake_search(distance=0.28):
    def f(question, scope, scheme_, corpus_, col, k=6):
        out = {}
        for g in scope:
            out[g] = []
            for rank, cid in enumerate(IDS[g], 1):
                c = corpus.chunks[cid]
                out[g].append(Hit(cid, c["heading"], c["text"], c["scope"], rank, distance, rank, 0.03 - rank * 0.001))
        return out
    return f


def scripted(*answers):
    q = list(answers)

    def gen(question, scope, hits, prior=None, failures=None):
        a = q.pop(0)
        if isinstance(a, Exception):
            raise a
        return a, {"tokens_in": 1000, "tokens_out": 100}
    gen.left = q
    return gen


GOOD = {"answerable": True, "answer": "The Cloud TPU API doesn't support TPU7x, so no software version is listed for it.",
        "steps": [{"generation": "tpu7x", "cite": "tpu-create-vm#body-step5",
                   "text": "Create TPU7x capacity with GKE or Compute Engine, using the tpu7x-standard-4t machine type."},
                  {"generation": "tpu7x", "cite": "tpu-software-versions#versions.1",
                   "text": "The Cloud TPU API is not supported on TPU7x."}]}
INVENTED = {"answerable": True, "answer": "Pass the v6e version.",
            "steps": [{"generation": "tpu7x", "cite": "tpu-create-vm#body-step5",
                       "text": "Pass --version=v2-alpha-tpuv6e when you create the VM."}]}
retrieved7 = {"tpu7x": IDS["tpu7x"]}


def run(ans, scope=("tpu7x",), retrieved=None):
    return check_answer(ans, list(scope), retrieved or retrieved7, corpus.chunks, corpus.owned)


# ---- check_answer
r = run(GOOD)
expect("good TPU7x answer passes", r.ok, r.failures)
r = run(INVENTED)
kinds = {f.check for f in r.failures}
expect("invented --version flag fails grounding", "grounding" in kinds)
expect("v6e version string fails as out-of-scope value", "out_of_scope" in kinds)
r = run({**GOOD, "steps": [{"generation": "tpu7x", "cite": "tpu-v6e-vm-types#vm-types-table", "text": "Each VM has 4 chips."}]})
expect("citation to a chunk not retrieved for the generation fails", any(f.check == "citation" for f in r.failures))
r = run({"answerable": True, "answer": "ok", "steps": [{"generation": "tpu7x", "cite": "tpu7x-vm-types#vm-types-table", "text": "Each TPU7x VM has 8 chips."}]})
expect("a number that is not in the cited chunk fails", any(f.check == "grounding" and "8" in f.reason for f in r.failures))
r = run({"answerable": True, "answer": "ok", "steps": [{"generation": "tpu7x", "cite": "tpu7x-vm-types#vm-types-table", "text": "Each TPU7x VM has 4 chips and 224 vCPUs."}]})
expect("correct numbers pass", r.ok, r.failures)
r6 = {"v6e": IDS["v6e"]}
cmd = "gcloud compute tpus tpu-vm create TPU_NAME --zone=ZONE --accelerator-type=ACCELERATOR_TYPE --version=v2-alpha-tpuv6e"
a = {"answerable": True, "answer": "ok", "steps": [{"generation": "v6e", "cite": "tpu-create-vm#body-step4", "text": "Create the VM:", "command": cmd}]}
expect("verbatim command (line breaks normalised) passes", run(a, ("v6e",), r6).ok, run(a, ("v6e",), r6).failures)
a["steps"][0]["command"] = cmd.replace("tpuv6e", "tpuv5")
expect("altered command fails", not run(a, ("v6e",), r6).ok)
expect("empty steps fail", not run({"answerable": True, "answer": "x", "steps": []}).ok)

# ---- agent loop
def agent(gen, search=None):
    return Agent(scheme, corpus, None, retriever=search or fake_search(), generator=gen)


def no_search(*a, **k):
    raise AssertionError("search must not run without a scope")


r = agent(scripted(), no_search).ask("How many chips are in one host?")
expect("no generation: asks the reader, runs no search", r["outcome"] == "ask" and len(r["ask"]["options"]) == 4)
expect("asking costs no model calls", r["run"]["calls"] == 0)

g = scripted()
r = agent(g, fake_search(0.5)).ask("What is the capital of France? on Ironwood")
expect("beyond the distance floor: refuses before any model call", r["outcome"] == "refuse" and r["run"]["calls"] == 0)

r = agent(scripted(GOOD)).ask("I'm on Ironwood. Which --version do I pass?")
expect("clean answer in one call", r["outcome"] == "answer" and r["run"]["calls"] == 1 and r["scope"] == ["tpu7x"], r)
expect("answer carries citations with sources", r["answer"]["steps"][0]["source"]["path"].endswith(".dita"))

g = scripted(INVENTED, GOOD)
r = agent(g).ask("I'm on Ironwood. Which --version do I pass?")
expect("invented flag: revised once, then answered", r["outcome"] == "answer" and r["run"]["calls"] == 2, r["outcome"])
expect("the failed check is visible in the trace", any(t["step"] == "Check the answer" and t["detail"]["passed"] is False for t in r["trace"]))

r = agent(scripted(INVENTED, INVENTED, INVENTED)).ask("I'm on Ironwood. Which --version do I pass?")
expect("still failing after two revisions: refuses", r["outcome"] == "refuse" and r["run"]["calls"] == 3)

r = agent(scripted({"answerable": False, "answer": "", "steps": [], "missing": "No pricing is documented."})).ask("price of Ironwood?")
expect("model says it is not answerable: refuses and says what is missing", r["outcome"] == "refuse" and "pricing" in r["refusal"]["missing"])

r = agent(scripted(ValueError("model did not return valid JSON"), GOOD)).ask("Ironwood version?")
expect("invalid JSON from the model: retried", r["outcome"] == "answer" and r["run"]["calls"] == 2)

two = {"answerable": True, "answer": "TPU7x VMs have 4 chips; the largest v6e VM has 8.",
       "steps": [{"generation": "tpu7x", "cite": "tpu7x-vm-types#vm-types-table", "text": "Each TPU7x VM has 4 chips."},
                 {"generation": "v6e", "cite": "tpu-v6e-vm-types#vm-types-table", "text": "The largest v6e VM has 8 chips."}]}
r = agent(scripted(two)).ask("chips per VM", ["tpu7x", "v6e"])
expect("two generations: one cited answer for each", r["outcome"] == "answer" and sorted(r["scope"]) == ["tpu7x", "v6e"], r["outcome"])
cross = {**two, "steps": [two["steps"][0], {**two["steps"][1], "cite": "tpu7x-vm-types#vm-types-table"}]}
expect("a v6e step citing a tpu7x chunk is rejected", not check_answer(cross, ["tpu7x", "v6e"], {g_: IDS[g_] for g_ in IDS}, corpus.chunks, corpus.owned).ok)
try:
    agent(scripted()).ask("x", ["v9z"])
    expect("unknown generation rejected", False)
except ValueError:
    expect("unknown generation rejected", True)

print("agent checks passed" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
