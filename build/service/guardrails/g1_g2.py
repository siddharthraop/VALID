import numpy as np
from google import genai
from google.genai.types import EmbedContentConfig, GenerateContentConfig, ThinkingConfig
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

PROJECT_ID = "REMOVED"
GEMINI_LOCATION = "global"
EMBED_LOCATION = "europe-west2"
DIMENSIONALITY = 1536
G2_SCOPE_FLOOR = 0.62
G3_CONFIDENCE_THRESHOLD = 0.70

gemini_client = genai.Client(vertexai=True, project=PROJECT_ID, location=GEMINI_LOCATION)
embed_client = genai.Client(vertexai=True, project=PROJECT_ID, location=EMBED_LOCATION)
db = firestore.Client(project=PROJECT_ID)

G1_SYSTEM_PROMPT = """You clean up voice-transcribed maintenance queries for a manufacturing retrieval system.
Fix disfluencies (uh, um), resolve informal phrasing into the likely intended technical query, and correct
obvious jargon transcription errors. Do not add information that wasn't implied by the original query.
Return only the cleaned query text, nothing else."""

def g1_normalize(raw_query: str) -> str:
    response = gemini_client.models.generate_content(
        model="gemini-3.1-flash-lite",
        contents=raw_query,
        config=GenerateContentConfig(
            system_instruction=G1_SYSTEM_PROMPT,
            temperature=0,
            thinking_config=ThinkingConfig(thinking_level="minimal"),
        ),
    )
    return response.text.strip()

def _embed_query(text: str) -> list[float]:
    import time
    t = time.time()
    response = embed_client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=EmbedContentConfig(task_type="RETRIEVAL_QUERY", output_dimensionality=DIMENSIONALITY),
    )
    raw = response.embeddings[0].values
    norm = np.linalg.norm(raw)
    print(f"  [timing] embed_content call: {round((time.time()-t)*1000)}ms")
    return (np.array(raw) / norm).tolist()


def _find_nearest(query_vector: list[float], k: int) -> list[dict]:
    import time
    t = time.time()
    results = list(db.collection("chunks").find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=k,
        distance_result_field="vector_distance",
    ).get())
    print(f"  [timing] find_nearest call: {round((time.time()-t)*1000)}ms")
    return [r.to_dict() for r in results]

def retrieve_and_gate(normalized_query: str, k: int = 3) -> dict:
    query_vector = _embed_query(normalized_query)
    chunks = _find_nearest(query_vector, k)

    if not chunks:
        return {"top1_similarity": 0.0, "chunks": [], "blocked_at": "G2", "query_vector": query_vector}

    top1_similarity = 1 - chunks[0]["vector_distance"]

    if top1_similarity < G2_SCOPE_FLOOR:
        return {"top1_similarity": top1_similarity, "chunks": [], "blocked_at": "G2", "query_vector": query_vector}
    if top1_similarity < G3_CONFIDENCE_THRESHOLD:
        return {"top1_similarity": top1_similarity, "chunks": chunks, "blocked_at": "G3", "query_vector": query_vector}
    return {"top1_similarity": top1_similarity, "chunks": chunks, "blocked_at": None, "query_vector": query_vector}

if __name__ == "__main__":
    test_queries = [
        "uh lockout the uh press thing before I touch it",
        "E-04 fault on the Haas VF-2SS, Line 3, what do I check?",
        "What's the best pizza place near the facility?",
        "How do I fix the blinking light on machine 4?",
    ]
    # Run each query TWICE to prove determinism, not just get an answer.
    for raw in test_queries:
        print(f"\nRaw: \"{raw}\"")
        for run in (1, 2):
            normalized = g1_normalize(raw)
            result = retrieve_and_gate(normalized)
            status = f"BLOCKED at {result['blocked_at']}" if result["blocked_at"] else "PASS (G2+G3)"
            print(f"  run {run}: G1=\"{normalized}\" sim={result['top1_similarity']:.4f} -> {status}")
