# VALID build progress
GCP project: valid-mvp-8425 (us-central1). Billing linked; budget "valid-guard" 1 SGD.
Firestore (default) created: standard edition, free tier. Gemini key lives in separate project VALID-API (free tier). Never commit keys.
Corpus: ../dita-corpus (4 generations: v5e v5p v6e tpu7x). Scope from @platform + map cascade; subject scheme = tpu/subjects/tpu-scheme.ditamap.
Decisions: UI served from Cloud Run (no Firebase Hosting). Tools are plain Python; ADK wrapper last. Chunks with unscoped/out-of-scope values are quarantined (fail closed).
Done: batch 1 (GCP setup), batch 2 (indexer dry run: resolve_profiles + audit_scope).
Next: embeddings + Firestore vector index, then retrieval, answer, checks, UI, deploy.
