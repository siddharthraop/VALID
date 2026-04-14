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
