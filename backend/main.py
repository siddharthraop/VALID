import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import chromadb
from llama_index.core import VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.llms import MockLLM
from llama_index.core import Settings

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

class QueryRequest(BaseModel):
    query: str

# Load index once on startup
print("Loading index...")
embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")
Settings.embed_model = embed_model
Settings.llm = None

chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
chroma_collection = chroma_client.get_or_create_collection("vaultrag")
vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
storage_context = StorageContext.from_defaults(vector_store=vector_store)
index = VectorStoreIndex.from_vector_store(vector_store, embed_model=embed_model)
retriever = index.as_retriever(similarity_top_k=3)
print("Index ready.")

SCOPE_KEYWORDS = ["fault", "error", "procedure", "loto", "lockout", "spindle",
                  "axis", "reset", "maintenance", "haas", "cnc", "e-04", "e-07"]

def check_scope(query: str) -> bool:
    q = query.lower()
    return any(k in q for k in SCOPE_KEYWORDS)

def check_safety(query: str) -> bool:
    safety_terms = ["loto", "lockout", "tagout", "isolat", "maintenance", "cabinet"]
    q = query.lower()
    return any(k in q for k in safety_terms)

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/query")
async def query_endpoint(req: QueryRequest):
    raw = req.query.strip()
    if not raw:
        return {"response": "No query provided.", "citation": None}

    # G1 — Normalise
    normalised = raw.strip().rstrip("?").capitalize()
    if not normalised.endswith("."):
        normalised += "."

    # G2 — Scope check
    if not check_scope(raw):
        return {
            "response": "This query is outside the scope of the indexed documentation. VaultRAG is scoped to equipment fault procedures and maintenance documentation for this facility.",
            "citation": None,
            "guardrail": "G2 — Scope Guard · refused"
        }

    # Retrieve
    nodes = retriever.retrieve(normalised)

    # G3 — Confidence threshold
    if not nodes or nodes[0].score < 0.3:
        return {
            "response": "Insufficient confidence to return a reliable procedure. The query may be too ambiguous or the relevant document may not be indexed. Please rephrase or consult the manual directly.",
            "citation": None,
            "guardrail": "G3 — Confidence Threshold · refused"
        }

    top = nodes[0]
    text = top.node.get_content()
    citation = top.node.metadata.get("file_name", "Haas VF-2SS Manual")

    # G4 — Safety flag
    safety_prefix = ""
    if check_safety(raw):
        safety_prefix = "⚠ SAFETY PROCEDURE — Ensure supervisor is notified and all personnel are clear before proceeding.\n\n"

    # G5 — Citation enforcer
    if not text:
        return {
            "response": "A source document was located but the content could not be extracted. Please consult the manual directly.",
            "citation": None,
            "guardrail": "G5 — Citation Enforcer · refused"
        }

    # Extract citation line if present
    lines = text.split("\n")
    citation_line = next((l for l in lines if l.startswith("Citation:")), None)
    if citation_line:
        citation = citation_line.replace("Citation:", "").strip()

    return {
        "response": safety_prefix + text.strip(),
        "citation": citation,
        "guardrail": "G1–G5 · all passed"
    }


from fastapi.responses import HTMLResponse
import os

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    frontend_path = os.path.join(os.path.dirname(__file__), "frontend", "index.html")
    with open(frontend_path, "r") as f:
        return f.read()
