# VaultRAG — Glossary

Definitions of technical and domain-specific terms used across the VaultRAG portfolio. Terms are organised by category. Where a term has a specific meaning in the VaultRAG context that differs from its general usage, the VaultRAG-specific definition is stated.

---

## RAG & AI Architecture

**RAG (Retrieval-Augmented Generation)**
A technique that combines a vector retrieval system with a language model. Rather than generating a response from training data alone, the model first retrieves relevant passages from a document corpus and uses those passages as context for generation. VaultRAG uses LlamaIndex as the RAG orchestration framework.

**LLM (Large Language Model)**
A neural network trained on large text corpora capable of generating, summarising, and reasoning over natural language. In VaultRAG, the LLM is Llama 3.2 3B, served locally via Ollama. It is used for query normalisation (G1), response generation, and citation validation (G5).

**Embedding**
A numerical vector representation of a piece of text that captures its semantic meaning. Similar texts produce embeddings that are close together in vector space. VaultRAG uses `nomic-embed-text` via Ollama to embed both documents (at ingestion) and queries (at runtime).

**Vector Store**
A database optimised for storing and searching embedding vectors. VaultRAG uses ChromaDB as an embedded, persistent, local vector store. It stores chunk embeddings indexed with metadata (document title, section, page range).

**Cosine Similarity**
A measure of similarity between two vectors, ranging from -1 to 1. A score of 1 means the vectors are identical in direction. VaultRAG uses cosine similarity to compare query embeddings against chunk embeddings during retrieval. The G3 Confidence Threshold requires a minimum score of 0.70.

**Chunk / Chunking**
The process of splitting a document into smaller, retrievable units before embedding. VaultRAG uses procedural section chunking — splitting at heading and procedure boundaries rather than arbitrary token windows — to preserve complete procedures as single retrievable units.

**Top-k Retrieval**
The retrieval strategy of returning the k most similar chunks for a given query. VaultRAG uses k=3, returning the three most relevant chunks from ChromaDB to ground the LLM response.

**Hallucination**
A failure mode in LLM generation where the model produces a plausible-sounding but factually incorrect or ungrounded response. In a manufacturing context, a hallucinated procedure is a safety risk. VaultRAG's guardrail pipeline is designed to reduce the likelihood of hallucination by refusing to generate when retrieval confidence is insufficient. The guardrail design does not eliminate the possibility of hallucination, but adds multiple checkpoints intended to catch the conditions most likely to produce it.

**Context Window**
The maximum amount of text a language model can process in a single inference call. Llama 3.2 3B has a 128K token context window. VaultRAG's top-3 retrieved chunks are injected into the context window alongside the system prompt and query.

**Inference**
The act of running a trained model to generate output for a given input. In VaultRAG, inference is performed locally by Ollama — no external API call is made at inference time.

**System Prompt**
A set of instructions prepended to every LLM call that governs the model's behaviour. VaultRAG's system prompt enforces: step-by-step format, maximum 5 steps, mandatory citation, and safety prefix on G4 trigger. It is a first-class design artifact, not an afterthought.

**Semantic Search**
Search based on meaning rather than keyword matching. A query for "spindle fault" will retrieve chunks about "spindle bearing failure" even if the exact words don't match, because the embeddings are semantically close.

**Procedural Chunking**
VaultRAG's specific chunking strategy: splitting documents at section headings and numbered procedure boundaries, keeping each complete procedure as a single chunk. Contrasted with token-window chunking, which splits at arbitrary character counts regardless of content structure.

---

## Guardrail Pipeline

**G1 — Query Normaliser**
The first guardrail layer. Runs before retrieval. Takes the raw voice transcription (which may include filler words, mishearing, jargon, or incomplete sentences) and uses a structured LLM prompt to produce a clean, well-formed query. Position: pre-retrieval.

**G2 — Scope Guard**
The second guardrail layer. Runs before retrieval. Checks whether the normalised query has any meaningful semantic overlap with the indexed document corpus. Uses the top-1 similarity score as a proxy: if it is below a minimum floor (0.30), the query is refused immediately without spending retrieval budget. Position: pre-retrieval.

**G3 — Confidence Threshold**
The third guardrail layer. Runs after retrieval. Checks whether the best chunk returned by ChromaDB meets the minimum similarity threshold of 0.70. If no chunk reaches this threshold, the system refuses rather than generating a response from weakly-matched context. Position: post-retrieval.

**G4 — Safety Flag**
The fourth guardrail layer. Runs after retrieval, before generation. Scans the retrieved chunks for safety-critical keywords: LOTO, lockout, tagout, high voltage, pressure vessel, hazardous material, isolation, and equivalents. If triggered, a mandatory safety warning prefix is prepended to the response and the citation must include the full procedure reference. Position: pre-generation.

**G5 — Citation Enforcer**
The fifth guardrail layer. Runs after generation. Validates that the LLM output contains at least one source reference (document title, section, page range). If absent, the response is retried once with a stricter prompt. If the retry also fails, the response is blocked and a refusal is returned. Position: post-generation.

**Fail Closed**
A design principle where a system defaults to refusal rather than partial or uncertain action when it cannot operate correctly. VaultRAG's guardrail pipeline is designed to fail closed: when confidence is insufficient, when scope is violated, when a citation cannot be produced, the system refuses with a clear explanation rather than generating a potentially incorrect answer.

**Confidence Threshold**
In VaultRAG, the minimum cosine similarity score (0.70) required for the best retrieved chunk before the system will proceed to generation. A configurable parameter. Below this threshold, the system refuses. See G3.

---

## Manufacturing Domain

**SOP (Standard Operating Procedure)**
A documented, step-by-step procedure for performing a specific task consistently and correctly. In manufacturing, SOPs are typically ISO-controlled documents — they have version numbers, approval workflows, and change histories. VaultRAG is designed to query SOPs as a primary document type.

**NCR (Non-Conformance Report)**
A formal document raised when a product, process, or procedure does not meet the required standard. NCRs trigger investigation, corrective action, and in regulated environments, customer notification. VaultRAG's use case is partly motivated by the fact that 9 of FlexForm's 14 annual NCRs were traced to incorrect procedure application. Note that FlexForm is a constructed design scenario, not a real organisation.

**LOTO (Lockout/Tagout)**
A safety procedure (OSHA 29 CFR 1910.147) requiring the isolation and locking of energy sources before maintenance work begins on equipment. A LOTO violation is a serious safety incident. G4 Safety Flag specifically detects LOTO references in retrieved chunks and triggers a mandatory warning prefix.

**ISO 9001**
An international standard for quality management systems. ISO 9001-certified manufacturers must maintain documented procedures, evidence of process control, and audit trails for corrective actions. VaultRAG's audit log (v1.0 roadmap) is designed specifically to satisfy ISO 9001 documentation requirements.

**OEM (Original Equipment Manufacturer)**
The manufacturer of the original equipment. In a Tier-2 supply chain context, FlexForm supplies components to a Tier-1 OEM. OEM equipment manuals are the primary source documents in VaultRAG's corpus.

**CNC (Computer Numerical Control)**
A type of precision machining equipment controlled by computer programs. The Haas VF-2SS referenced throughout the portfolio is a CNC vertical machining centre. E-04 is a spindle fault code on this machine.

**Torque Specification**
The precise amount of rotational force required to tighten a fastener correctly. Torque specs are safety-critical in manufacturing — too loose causes failure; too tight causes damage. The 45 Nm torque spec for the Haas VF-2SS spindle bearing housing is a concrete example of the type of specific, precise information VaultRAG is designed to retrieve accurately.

**ITAR (International Traffic in Arms Regulations)**
US export control regulations that govern the manufacturing, sale, and distribution of defence-related articles and services. ITAR-adjacent manufacturers prohibit sending controlled technical data to third-party cloud services — a key driver of the on-prem, zero-exfiltration architecture.

**Tier-2 Supplier**
A company that supplies components or services to a Tier-1 supplier, who in turn supplies to an OEM. Tier-2 suppliers like FlexForm operate under NDA clauses and data governance requirements that flow down from the OEM through the Tier-1. These constraints typically prohibit cloud data sharing.

**Downtime**
Any period when production equipment is not operating as intended. Unplanned downtime — caused by unexpected equipment failure — is the most costly. The average cost of unplanned downtime in general manufacturing is $260,000/hour (Aberdeen Group, 2024).

---

## Infrastructure & Deployment

**Ollama**
An open-source tool for running large language models locally. Ollama handles model downloading, serving, and API access via a local HTTP endpoint (default: port 11434). VaultRAG uses Ollama to serve both Llama 3.2 3B (LLM) and nomic-embed-text (embeddings) from a single local process.

**ChromaDB**
An open-source embedding database (vector store) that runs embedded within the application process and persists to local disk. No external service required. Apache 2.0 licence. VaultRAG uses ChromaDB as the sole vector retrieval backend.

**LlamaIndex**
An open-source Python framework for building LLM-powered applications over external data. Provides the document ingestion pipeline, query engine, retrieval orchestration, and response synthesis in VaultRAG. MIT licence.

**FastAPI**
A modern Python web framework for building APIs. VaultRAG uses FastAPI as the backend HTTP server — handling API requests from the frontend, orchestrating the guardrail pipeline, and serving the static HTML frontend. MIT licence.

**Docker / Docker Compose**
A containerisation platform that packages an application and its dependencies into a portable, reproducible unit. VaultRAG's entire stack (Ollama + ChromaDB + FastAPI + frontend) is containerised with Docker Compose. One command (`docker-compose up`) starts the complete stack on any machine.

**Plant WiFi / Plant LAN**
The internal network infrastructure within a manufacturing facility. In VaultRAG's production deployment model, the backend server is on the plant LAN and technicians access it via plant WiFi from their phones. No internet connection is required or used after initial model download.

**Air-Gapped**
A security configuration in which a system has no connection to external networks. VaultRAG's on-prem deployment is designed to operate in air-gapped or near-air-gapped environments: after the initial model download, zero network egress is required. Note that the portfolio demo does not operate under this constraint — see "Production deployment" below.

**HuggingFace Spaces**
A platform by HuggingFace for hosting ML applications and demos. VaultRAG uses HuggingFace Spaces free tier to host the portfolio demo backend (Docker container with Ollama + ChromaDB + FastAPI). This is a demo environment only — not representative of the production deployment model.

**GitHub Pages**
A static site hosting service provided by GitHub, free for public repositories. VaultRAG's portfolio frontend (the six HTML pages) is hosted on GitHub Pages. No server required — GitHub Pages serves static files directly.

**Web Speech API**
A browser-native JavaScript API that provides speech recognition and speech synthesis capabilities. VaultRAG uses the speech recognition component for voice input in the demo. The browser captures audio from the device microphone and returns a text transcription via Google or Apple backends. Because audio is routed externally, this API is not compatible with the air-gap requirement in strict production deployments. Local Whisper STT is the documented replacement in the v1.0 roadmap.

**PyMuPDF (fitz)**
A Python library for parsing PDF files. VaultRAG uses PyMuPDF to extract text from PDF documents during ingestion, with custom logic to detect section headings and procedure boundaries for procedural chunking.

**nomic-embed-text**
An open-source text embedding model by Nomic AI. VaultRAG uses nomic-embed-text via Ollama for generating document and query embeddings. 768-dimensional embeddings. No external API call required.

---

## Architecture & Design

**ADR (Architecture Decision Record)**
A document that records a significant architectural decision, the context in which it was made, the alternatives considered, and the reasoning for the choice. VaultRAG documents eight ADRs covering every major stack decision. The format is borrowed from Michael Nygard's original ADR proposal.

**Data Sovereignty**
The principle that data remains under the control of the organisation that owns it, subject to that organisation's laws and governance policies. In VaultRAG, data sovereignty is an architectural invariant in the production deployment model: no document content, query text, or response data is transmitted outside the facility network. This invariant is not enforced in the portfolio demo environment, which runs on HuggingFace Spaces.

**On-Prem (On-Premises)**
A deployment model where software runs on hardware physically located at the user's facility, rather than in a cloud data centre. VaultRAG's production deployment is on-prem by design — the LLM, vector store, and application server all run on a server inside the plant.

**Zero Exfiltration**
The property of a system in which no data exits the defined trust boundary under any normal operating condition. In VaultRAG's target production deployment, zero exfiltration means that no document content, query, embedding, or response is transmitted to an external network after initial model download. This property does not apply to the demo environment.

**TOGAF ADM**
The Architecture Development Method defined by The Open Group Architecture Framework (TOGAF). A structured approach to enterprise architecture design. Referenced in the broader portfolio context (The Autonomous Enterprise uses TOGAF ADM across six phases).

**HITL (Human-in-the-Loop)**
A design pattern in which a human reviewer is required to approve or validate an AI decision before it takes effect. Not implemented in VaultRAG v0.1 (the system either answers or refuses), but referenced as a production upgrade path in the v1.0 roadmap for escalation scenarios.

**Design Scenario**
In EA practice, a design scenario is a constructed business context used to ground an architectural design in realistic constraints without requiring a real client engagement. A design scenario defines the organisation type, operational environment, regulatory context, and forcing functions that shape the architecture. FlexForm Precision is the design scenario for VaultRAG — it is a fictional Tier-2 precision machining supplier constructed to represent the class of manufacturing environments where the on-prem, data-sovereign RAG architecture is relevant. FlexForm is not a real organisation.

**Production Deployment**
In this portfolio, "production deployment" refers to the target deployment model documented in page-03.html: an on-premises server inside the plant LAN, running local Llama 3.2 3B inference via Ollama, ChromaDB persisted to local disk, and a local Whisper STT model replacing Web Speech API — with no external network calls at inference time. This is distinct from the portfolio demo environment, which runs on HuggingFace Spaces (cloud-hosted) and uses Web Speech API (which routes audio to external backends). The demo is provided for portfolio review purposes and does not enforce the data sovereignty constraint.

**Design Validation**
In this portfolio, design validation refers to the offline guardrail evaluation table documented on page-03.html. That table records the result of manually triggering each of the five guardrail conditions (G1–G5) against the implemented system and confirming that each guardrail fires in its designed condition and returns the expected response. This is a functional validation — it confirms that the guardrails behave as designed under controlled test conditions. It is not a statistical performance benchmark, does not characterise recall or precision at scale, and does not constitute a production readiness assessment.

**Fail Closed**
See Guardrail Pipeline section above.

---

*Last updated: April 2026 · VaultRAG v0.1*
