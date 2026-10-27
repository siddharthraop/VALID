# VALID: progress

## Status
MVP complete: a portal where the reader asks a question, gets a checked answer with sources, and sees the reasoning.
Cloud Run service `valid` (us-central1), private by access code. Free tier throughout.

## Where things live
- Google Cloud project `valid-mvp-8425` (number 335536436651), region us-central1
- Firestore (Standard, free tier): collection `chunks`, one composite vector index per generation
- Cloud Run service `valid`: max 1 instance, scales to zero, 512 Mi, concurrency 4, timeout 90 s
- Secret Manager: `gemini-key` (free-tier key from the VALID-API project), `valid-access-code`
- Service account `valid-run` (role: Datastore User; access to the two secrets only)
- Daily question cap: 50 per UTC day, in memory (resets on restart)
- Source deploy: `gcloud run deploy valid --source .` (see Dockerfile)

## What is built (design doc section)
- Scope from the source, not a model: valid/scheme.py, valid/scope.py
- Profile resolution, chunking and scope audit with quarantine: valid/dita.py, valid/audit.py
- Embeddings and Firestore sync with change detection: valid/gemini.py, valid/store.py
- Filter first, then search: pre-filtered vector search plus SQLite FTS5 keyword search, fused (k=60): valid/retrieve.py, valid/bm25.py
- The model answers, the checks decide: valid/answer.py (structured output, citation enum), valid/checks.py
- Refusal as a designed outcome, at most 2 revisions: valid/agent.py
- Portal with reasoning panel, access code, daily cap: valid/web.py, valid/static/index.html

## Known limits (honest)
- Free-tier Gemini is often busy: replies take 5-30 s and sometimes fail. Fallback chain 3.8 -> 3.6 -> 3.5 with a cooldown and one quick retry. The design's under-5-second median is not met on the free tier.
- Retrieval refusal floor (distance 0.40) cannot separate in-domain-but-absent questions from on-topic ones; the model's answerable flag covers that.
- "Per VM" is never treated as "per host": a question that needs the second returns a stated gap.

## Not built yet
- BigQuery question log and gap issues on GitHub (would need billing-enabled writes; deferred)
- ADK wrapper
- Trap-set evaluation against the design's section 7 metrics
- Automatic index build on corpus change (GitHub Actions)

## Working rules
Free tier only; keep a budget alert; never put the Gemini key or access code in a file; run `git diff --cached | grep -c AIza` before each commit.
