# VaultRAG — On-Premises RAG for Manufacturing Knowledge Retrieval

> **EA Portfolio Prototype.** This project documents an architectural design study for a voice-enabled, on-premises retrieval-augmented generation system targeting constrained manufacturing environments. It is a portfolio artifact, not a commercial product.

[![Portfolio](https://img.shields.io/badge/Portfolio-Live%20Demo-f59e0b?style=flat-square)](https://raosiddharthp.github.io/VaultRAG/)
[![Architecture](https://img.shields.io/badge/Architecture-6%20Pages-3b82f6?style=flat-square)](https://raosiddharthp.github.io/VaultRAG/page-03.html)
[![Simulator](https://img.shields.io/badge/Simulator-Live-10b981?style=flat-square)](https://raosiddharthp.github.io/VaultRAG/page-04.html)
[![License](https://img.shields.io/badge/License-Apache%202.0-8b5cf6?style=flat-square)](LICENSE)

---

## About This Project

VaultRAG is an enterprise architecture portfolio prototype demonstrating a design solution for knowledge retrieval in manufacturing environments where cloud services are architecturally excluded. The scenario under study involves a factory floor technician who needs to query equipment manuals, SOPs, and incident reports by voice, from the floor, without document content leaving the facility network.

The design is structured around three architectural constraints that characterise the target production environment:

1. **No cloud services at inference time** — NDA clauses, ITAR restrictions, and ISO 27001 data governance policies in precision manufacturing commonly prohibit transmitting controlled technical documents to third-party cloud infrastructure.
2. **On-premises inference** — the LLM, embedding model, and vector store must all run on hardware inside the plant.
3. **Data sovereignty** — no document content, query text, or response data may be transmitted outside the facility network boundary under normal operating conditions.

The design scenario is built around a constructed client — **FlexForm Precision** — a fictional Tier-2 precision machining supplier. FlexForm is not a real organisation. It is a designed scenario used to ground the architectural constraints in a representative business context. See the Glossary entry for "Design scenario."

---

## Demo vs Production — Important Distinction

> ⚠️ **The portfolio demo does not enforce the data sovereignty constraint.**

| | Demo Environment | Target Production Deployment |
|---|---|---|
| **Backend host** | HuggingFace Spaces (cloud) | On-prem server inside plant LAN |
| **Voice input** | Web Speech API (routes audio to Google/Apple backends) | Local Whisper STT — no external network call |
| **Data boundary** | No enforcement — data transits external infrastructure | Zero egress after initial model download |
| **Purpose** | Portfolio demonstration | Documented design target |

The data sovereignty and air-gap claims in this portfolio apply **only** to the production deployment model documented in [page-03.html](https://raosiddharthp.github.io/VaultRAG/page-03.html). The demo is provided so that reviewers can interact with the RAG pipeline and guardrail behaviour. It is not a representation of what a production deployment would look like operationally.

The v0.1 implementation has four known production gaps that are not resolved in the current prototype. These are documented in the CHANGELOG under "Known issues — v0.1" and are addressed in the v1.0 roadmap.

---

## The Problem Being Addressed

Maintenance technicians on factory floors frequently need to locate specific procedures within large technical document corpora — equipment manuals, SOPs, and incident reports — under time pressure. In environments where production downtime carries significant cost, search latency has measurable economic impact.

Cloud-based RAG systems represent a technically straightforward solution to this retrieval problem, but are architecturally excluded from many manufacturing environments by contractual and regulatory constraints. The design question this project addresses is: what does a RAG system look like when cloud infrastructure is not available as a design option?

---

## Architecture
Voice Input (Web Speech API)
│
▼
G1 · Query Normaliser       ← denoise voice transcription
│
G2 · Scope Guard            ← refuse if no corpus relevance
│
ChromaDB Retrieval          ← top-k=3 · nomic-embed-text · cosine similarity
│
G3 · Confidence Threshold   ← refuse if best score < 0.70
│
G4 · Safety Flag            ← warn on LOTO / hazard keywords
│
Llama 3.2 3B (Ollama)       ← local inference · step-by-step · citation required
│
G5 · Citation Enforcer      ← block response if no source reference
│
▼
Cited response → technician's phone

**Full architecture documentation:** [page-03.html](https://raosiddharthp.github.io/VaultRAG/page-03.html)

---

## Tech Stack

| Layer | Component | Notes |
|---|---|---|
| LLM | Llama 3.2 3B via Ollama | Local inference · Apache 2.0 |
| Embeddings | nomic-embed-text via Ollama | Same process as LLM · no extra service |
| Vector Store | ChromaDB | Embedded · persistent to disk |
| RAG Framework | LlamaIndex | Orchestration + ingestion pipeline |
| Document Parsing | PyMuPDF | Procedural section chunking |
| Guardrails | Custom prompt-based (G1–G5) | No extra model · auditable refusals |
| Voice Input | Web Speech API | Browser-native · zero install |
| Backend | FastAPI | HTTP server + static file serving |
| Frontend | HTML / CSS / JS | Single mobile-responsive page |
| Containerisation | Docker + Compose | One command to run anywhere |

**Stack decision rationale (ADR-001 through ADR-008):** [page-03.html](https://raosiddharthp.github.io/VaultRAG/page-03.html)

---

## Demo

The live portfolio demo runs on HuggingFace Spaces (free tier). The frontend is hosted on GitHub Pages.

**Four scenarios are available in the simulator:**

| Scenario | What it demonstrates |
|---|---|
| Happy path | All 5 guardrails pass · procedure retrieved and cited |
| Out of scope | G2 fires · query blocked before retrieval |
| Safety flag | G4 fires · LOTO prefix prepended to response |
| Low confidence | G3 fires · retrieval runs but scores insufficient |

[**→ Run the simulator**](https://raosiddharthp.github.io/VaultRAG/page-04.html)

---

## Local Setup

### Prerequisites

- [Docker](https://www.docker.com/) and Docker Compose
- [Ollama](https://ollama.com/) (or use the Docker Compose setup which includes it)
- 8GB RAM minimum (16GB recommended)
- 10GB disk space for models and indexes

### Run locally

```bash
# 1. Clone the repo
git clone https://github.com/raosiddharthp/VaultRAG.git
cd VaultRAG

# 2. Pull the required models
ollama pull llama3.2:3b
ollama pull nomic-embed-text

# 3. Start the stack
docker-compose up

# 4. Open on your phone (same WiFi)
# Navigate to http://<your-machine-ip>:8000
```

### Ingest your documents

```bash
# Place PDF or TXT files in /docs
# Run the ingestion pipeline
python ingest.py --docs ./docs
```

The ingestion pipeline chunks documents by section boundary (not token window), embeds with nomic-embed-text, and persists to ChromaDB. Re-run whenever documents are updated.

---

## Supported Document Formats

| Format | Status | Notes |
|---|---|---|
| PDF (`.pdf`) | ✅ v0.1 | PyMuPDF · section-boundary chunking |
| Plain text (`.txt`) | ✅ v0.1 | Heading-aware chunking |
| Word (`.docx`) | 🔜 v1.0 | python-docx · in roadmap |
| PowerPoint (`.pptx`) | 🔜 v1.0 | python-pptx · slide-title chunking |
| Markdown (`.md`) | 🔜 v1.0 | Heading-based chunking |

---

## Guardrail Reference

| Layer | Position | Mechanism | Triggered response |
|---|---|---|---|
| G1 · Query Normaliser | Pre-retrieval | LLM prompt · structured reformat | Query cleaned before retrieval |
| G2 · Scope Guard | Pre-retrieval | Top-1 similarity < 0.30 | "Query outside document scope" |
| G3 · Confidence Threshold | Post-retrieval | Best chunk score < 0.70 | "Insufficient information" |
| G4 · Safety Flag | Pre-generation | Keyword + semantic scan | Mandatory safety prefix prepended |
| G5 · Citation Enforcer | Post-generation | Source reference validation | Response blocked · retry once |

---

## Portfolio Context

VaultRAG is part of a broader enterprise AI architecture portfolio demonstrating end-to-end design capability across EA, MLE, and Cloud Architecture disciplines.

**The full portfolio:**

| Project | Vertical | Stack |
|---|---|---|
| [The Autonomous Enterprise](https://raosiddharthp.github.io/The-Autonomous-Enterprise/) | Medical Devices (ClaraVis) | GCP · ADK · Vertex AI · TOGAF |
| [The Autonomous HR](https://raosiddharthp.github.io/The-Autonomous-HR/) | Deskless Workforce | GCP · WhatsApp · Whisper · pgvector |
| **VaultRAG** | **Manufacturing** | **Ollama · LlamaIndex · ChromaDB · FastAPI** |

Each project targets a different vertical to demonstrate cross-domain architectural thinking.

---

## Roadmap

**v0.1 — MVP (current)**
- [x] 5-layer guardrail pipeline
- [x] Voice input via Web Speech API
- [x] PDF and TXT ingestion with procedural chunking
- [x] Llama 3.2 3B local inference via Ollama
- [x] Mobile-responsive chat UI
- [x] Docker deployment

**v1.0 — Production path**
- [ ] JWT authentication + role-based access
- [ ] Department-level document namespacing
- [ ] Immutable audit log (ISO 9001 ready)
- [ ] LlamaGuard on G4 trigger (conditional)
- [ ] Whisper local STT for air-gapped facilities
- [ ] Word and PowerPoint ingestion
- [ ] Text-to-speech response readback
- [ ] Document version management + auto re-index

**Full roadmap with justifications:** [page-06.html](https://raosiddharthp.github.io/VaultRAG/page-06.html)

---

## Cost Model

| Component | Monthly cost | Notes |
|---|---|---|
| LLM inference (Ollama) | £0.00 | Local · no API fees |
| Vector store (ChromaDB) | £0.00 | Embedded · Apache 2.0 |
| RAG framework (LlamaIndex) | £0.00 | MIT licence |
| Backend + frontend | £0.00 | Open source · self-hosted |
| Server hardware (amortised) | ~£50 | Shared with existing IT infrastructure |
| IT maintenance | ~£70 | ~2 hrs/month re-indexing |
| **Total** | **~£120/month** | **£1,440/year · all software £0** |

**Full cost model with sources:** [page-05.html](https://raosiddharthp.github.io/VaultRAG/page-05.html)

---

## Licence

Apache 2.0 — see [LICENSE](LICENSE).

Component licences: Llama 3.2 (Meta Llama 3.2 Community Licence), LlamaIndex (MIT), ChromaDB (Apache 2.0), Ollama (MIT), FastAPI (MIT).

---

## Author

**Siddharth Rao** · Enterprise AI Architecture Portfolio · 2026

[Portfolio](https://raosiddharthp.github.io/The-Autonomous-Enterprise/) · [LinkedIn](#) · [GitHub](https://github.com/raosiddharthp)
