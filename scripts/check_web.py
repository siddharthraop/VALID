"""Offline checks of the portal API: scripted model, fake search, no Google Cloud, no cost.
  python scripts/check_web.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient

from valid import config
from valid.agent import Agent
from valid.answer import ModelUnavailable
from valid.retrieve import Corpus, Hit
from valid.scheme import load_scheme
from valid.web import Cap, create_app

scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
corpus = Corpus.load(scheme)
IDS = {"tpu7x": ["tpu-create-vm#body-step5", "tpu-software-versions#versions.1"], "v6e": ["tpu-v6e-vm-types#vm-types-table"]}
bad = 0


def expect(name, cond, detail=""):
    global bad
    bad += 0 if cond else 1
    print(("ok   " if cond else "FAIL ") + name + (f"  {detail}" if (detail and not cond) else ""))


def search(q, scope, sch, cor, col, k=6):
    return {g: [Hit(i, corpus.chunks[i]["heading"], corpus.chunks[i]["text"], corpus.chunks[i]["scope"], n, 0.28, n, 0.03)
                for n, i in enumerate(IDS[g], 1)] for g in scope}


GOOD = {"answerable": True, "answer": "No software version is listed for TPU7x.",
        "steps": [{"generation": "tpu7x", "cite": "tpu-software-versions#versions.1", "text": "The Cloud TPU API is not supported on TPU7x."}]}
mode = {"v": "good"}


def gen(q, scope, hits, prior=None, failures=None):
    if mode["v"] == "busy":
        raise ModelUnavailable("503", [])
    return GOOD, {"tokens_in": 10, "tokens_out": 5, "model": "fake"}


app = create_app(Agent(scheme, corpus, None, retriever=search, generator=gen), Cap(3))
c = TestClient(app)

expect("page is served", c.get("/").status_code == 200 and "VALID" in c.get("/").text)
expect("security headers set", "default-src 'none'" in c.get("/").headers["content-security-policy"])
cfg = c.get("/api/config").json()
expect("config lists four generations and the cap", len(cfg["generations"]) == 4 and cfg["left_today"] == 3, cfg)

r = c.post("/api/ask", json={"question": "How do I create a VM?"}).json()
expect("no generation: asks the reader, not counted", r["outcome"] == "ask" and r["left_today"] == 3 and len(r["ask"]["options"]) == 4)
r = c.post("/api/ask", json={"question": "How do I create a VM?", "generations": ["tpu7x"]}).json()
expect("reader picks a generation: answer, counted", r["outcome"] == "answer" and r["left_today"] == 2 and r["answer"]["steps"][0]["source"]["line"])
r = c.post("/api/ask", json={"question": "Ironwood version?"}).json()
expect("scope resolved from the question", r["outcome"] == "answer" and r["scope"] == ["tpu7x"])
bad_gen = c.post("/api/ask", json={"question": "hello there", "generations": ["v9"]})
expect("unknown generation is a 400, not counted", bad_gen.status_code == 400 and app.state.cap.left() == 1)
expect("too long a question is a 400", c.post("/api/ask", json={"question": "x" * 401}).status_code == 400)
mode["v"] = "busy"
r = c.post("/api/ask", json={"question": "Ironwood version?"}).json()
expect("busy model: unavailable, not counted", r["outcome"] == "unavailable" and r["left_today"] == 1)
mode["v"] = "good"
c.post("/api/ask", json={"question": "Ironwood version?"})
res = c.post("/api/ask", json={"question": "Ironwood version?"})
expect("cap reached: 429 with a plain message", res.status_code == 429 and "limit" in res.json()["detail"])
expect("no docs or openapi exposed", c.get("/docs").status_code == 404 and c.get("/openapi.json").status_code == 404)
# ---- access code
app2 = create_app(Agent(scheme, corpus, None, retriever=search, generator=gen), Cap(50), access_code="s3cret-code")
c2 = TestClient(app2)
expect("config says a code is needed", c2.get("/api/config").json()["needs_code"] is True)
expect("no code: 401", c2.post("/api/ask", json={"question": "Ironwood version?"}).status_code == 401)
expect("wrong code: 401, nothing counted", c2.post("/api/ask", json={"question": "Ironwood version?"}, headers={"X-Access-Code": "nope"}).status_code == 401 and app2.state.cap.left() == 50)
ok = c2.post("/api/ask", json={"question": "Ironwood version?"}, headers={"X-Access-Code": "s3cret-code"})
expect("right code: answered", ok.status_code == 200 and ok.json()["outcome"] == "answer")
for _ in range(8):
    c2.post("/api/ask", json={"question": "Ironwood version?"}, headers={"X-Access-Code": "guess"})
locked = c2.post("/api/ask", json={"question": "Ironwood version?"}, headers={"X-Access-Code": "s3cret-code"})
expect("too many wrong codes: that address is locked out", locked.status_code == 429, locked.status_code)
print("web checks passed" if not bad else f"{bad} FAILED")
sys.exit(1 if bad else 0)
