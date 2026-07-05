import time
from fastapi import FastAPI, Depends, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import firebase_admin
from firebase_admin import auth as firebase_auth
from g1_g2 import g1_normalize, retrieve_and_gate, _find_nearest, G2_SCOPE_FLOOR, G3_CONFIDENCE_THRESHOLD
from g4_generate import g4_safety_flag, EXPANDED_K_ON_SAFETY_FLAG
from g5_citation import generate_with_citation_enforcement

firebase_admin.initialize_app()

app = FastAPI(title="VaultRAG Guardrail Pipeline")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://REMOVED.web.app",
        "https://REMOVED.firebaseapp.com",
        "http://localhost:8000",
    ],
    allow_methods=["POST"],
    allow_headers=["Authorization", "Content-Type"],
)

def verify_token(authorization: str = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or malformed Authorization header")
    token = authorization.removeprefix("Bearer ").strip()
    try:
        decoded = firebase_auth.verify_id_token(token)
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid ID token: {e}")
    return decoded

class QueryRequest(BaseModel):
    raw_query: str

@app.post("/query")
def query(req: QueryRequest, user: dict = Depends(verify_token)):
    t0 = time.time()
    stages = []

    def stage(name, status, detail, elapsed_ms=None):
        stages.append({"name": name, "status": status, "detail": detail, "elapsed_ms": elapsed_ms})

    stage("voice_input", "done", req.raw_query)

    t1 = time.time()
    normalized = g1_normalize(req.raw_query)
    stage("g1_normalize", "done", normalized, round((time.time()-t1)*1000))

    t2 = time.time()
    result = retrieve_and_gate(normalized, k=3)
    retrieval_ms = round((time.time()-t2)*1000)
    sim = round(result["top1_similarity"], 4)

    if result["blocked_at"] == "G2":
        stage("g2_scope_guard", "blocked", f"sim={sim} < {G2_SCOPE_FLOOR}")
        for s in ["retrieval", "g3_confidence", "g4_safety", "generation", "g5_citation"]:
            stage(s, "skip", "skipped — blocked at G2")
        return {"stages": stages, "blocked_at": "G2", "answer": None,
                "refusal_reason": "Query outside document scope",
                "total_time_ms": round((time.time() - t0) * 1000)}

    stage("g2_scope_guard", "done", f"sim={sim} >= {G2_SCOPE_FLOOR}")
    stage("retrieval", "done", f"{len(result['chunks'])} chunks retrieved", retrieval_ms)

    if result["blocked_at"] == "G3":
        stage("g3_confidence", "blocked", f"sim={sim} < {G3_CONFIDENCE_THRESHOLD}")
        for s in ["g4_safety", "generation", "g5_citation"]:
            stage(s, "skip", "skipped — blocked at G3")
        return {"stages": stages, "blocked_at": "G3", "answer": None,
                "refusal_reason": "Insufficient confidence in retrieved context",
                "total_time_ms": round((time.time() - t0) * 1000)}

    stage("g3_confidence", "done", f"sim={sim} >= {G3_CONFIDENCE_THRESHOLD}")

    chunks = result["chunks"]
    flagged = g4_safety_flag(chunks)
    if flagged:
        chunks = _find_nearest(result["query_vector"], EXPANDED_K_ON_SAFETY_FLAG)
        stage("g4_safety", "flagged", f"hazard keywords detected — expanded to k={EXPANDED_K_ON_SAFETY_FLAG}")
    else:
        stage("g4_safety", "done", "no hazard keywords")

    t3 = time.time()
    final = generate_with_citation_enforcement(normalized, chunks, flagged)
    stage("generation", "done", "gemini-3-flash-preview", round((time.time()-t3)*1000))
    stage("g5_citation", "done" if final["citation_ok"] else "blocked", f"retried={final['retried']}")

    if not final["citation_ok"]:
        return {"stages": stages, "blocked_at": "G5", "answer": None,
                "refusal_reason": final["refusal"],
                "total_time_ms": round((time.time() - t0) * 1000)}

    return {"stages": stages, "blocked_at": None, "answer": final["answer"],
            "safety_flagged": flagged, "retried_citation": final["retried"],
            "total_time_ms": round((time.time() - t0) * 1000)}

@app.get("/health")
def health():
    return {"status": "ok"}
