# VaultRAG

**Voice-first retrieval for manufacturing floors that can't send their documentation to the cloud.**

A technician with a fault code, 85–95dB of ambient noise, and one hand on the machine asks a question out loud. VaultRAG answers with a cited procedure in under 10 seconds — or refuses outright rather than guess, because a wrong answer on a lockout procedure isn't a UX problem, it's a safety incident.

**[→ Live app](https://REMOVED.web.app)** — sign in with Google, ask a real question, get a real answer from the live backend.
**[→ Full architecture design doc](https://raosiddharthp.github.io/VaultRAG/)** — problem statement, pipeline design, cost analysis, ADRs, design validation.

---

## What this actually is

Not a chatbot wrapper. A five-layer guardrail pipeline (query normalisation → scope guard → retrieval → confidence threshold → safety flagging → citation enforcement) built to **fail closed** — every refusal is a designed outcome, not an error state. Retrieval and generation run on Vertex AI and Firestore; the demo is deployed and live, not a local-only proof of concept.

| | |
|---|---|
| **Backend** | FastAPI on Cloud Run, `europe-west2` |
| **LLM** | `gemini-3.1-flash-lite` (query normalisation) + `gemini-3-flash-preview` (generation), both at `location=global` |
| **Embeddings** | `gemini-embedding-001`, truncated to 1536-dim (Firestore's vector field cap is 2048) |
| **Retrieval** | Firestore Vector Search (GA), KNN, cosine similarity |
| **Auth** | Firebase Authentication, Google Sign-In only |
| **Frontend** | Static HTML/JS, Firebase Hosting, real `SpeechRecognition` voice input with text fallback |
| **Cost** | $0/month target — Always-Free tiers across Cloud Run, Firestore, Firebase Hosting; Blaze billing with a budget alert, not a real spend |

## Real evidence, not claims

- **17/20 on a 20-query guardrail evaluation**, with the 3 non-passes analysed individually — including one explicitly documented as *correct behaviour, not a failure*, rather than reclassified to inflate the score.
- **A real retrieval gap found and fixed during build**: a safety-flagged query for fuse replacement never retrieved the actual isolation procedure it depended on, because "fuse replacement" and "isolation procedure" share almost no vocabulary despite being sequential steps in the same SOP. Fixed by expanding retrieval to k=5 specifically when G4 fires.
- **A real non-determinism bug found and fixed**: the query-normalisation model had no `temperature` set, so identical inputs produced different guardrail outcomes across runs. Fixed, then re-verified with back-to-back identical-output tests, not just a single passing run.
- **A real deployment bug found and fixed**: local Docker builds on Apple Silicon default to `arm64`; Cloud Run requires `amd64`. Builds now go through `buildx --platform linux/amd64` explicitly, every time, not as a one-off patch.
- Full measurement tables, cost breakdowns, and six architecture decision records — each with rejected alternatives, not just the chosen path — are in the [design doc](https://raosiddharthp.github.io/VaultRAG/).

## Run it locally

```bash
cd build/service
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

gcloud auth application-default login
gcloud auth application-default set-quota-project REMOVED

cd guardrails
python3 -m uvicorn main:app --port 8080
```

```bash
curl -X POST http://localhost:8080/query \
  -H "Content-Type: application/json" \
  -d '{"raw_query": "E-04 fault on the Haas VF-2SS, Line 3, what do I check?"}'
```

Requires a GCP project with Vertex AI, Firestore, and Firebase enabled, and IAM roles `aiplatform.user` + `datastore.user` granted to whichever identity runs it. The seed corpus (`build/service/data/seed_corpus/`) needs re-embedding into Firestore via `build/service/ingestion/ingest.py` before queries will return anything.

## Repo structure

```
index.html              # architecture design doc (GitHub Pages)
build/
  frontend/              # production app (Firebase Hosting) — index.html + 404.html
  service/
    guardrails/           # G1–G5 pipeline + FastAPI entrypoint (main.py)
    retrieval/             # Firestore Vector Search test harness
    ingestion/              # chunking + embedding pipeline
    data/seed_corpus/       # synthetic FlexForm Precision documents
    Dockerfile
    requirements.txt
```

## Production path

The live demo runs on Vertex AI over the public internet — a documented, honest exception to the system's actual sovereignty claim, not the default. The real production target is **Gemini on Google Distributed Cloud, air-gapped**: same application code, same guardrail logic, zero network egress after deployment. That path is designed, costed as far as it can honestly be (GDC pricing isn't publicly listed — a real enterprise quote, not a number to fabricate), and documented in the design doc's deployment architecture section.

---

Built by Siddharth Rao. [Design doc](https://raosiddharthp.github.io/VaultRAG/) · [Live app](https://REMOVED.web.app)
