import numpy as np
from google import genai
from google.genai.types import EmbedContentConfig
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from google.cloud.firestore_v1.base_vector_query import DistanceMeasure

PROJECT_ID = "REMOVED"
REGION = "europe-west2"
DIMENSIONALITY = 1536

client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
db = firestore.Client(project=PROJECT_ID)

def embed_query(text: str) -> list[float]:
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=EmbedContentConfig(
            task_type="RETRIEVAL_QUERY",
            output_dimensionality=DIMENSIONALITY,
        ),
    )
    raw = response.embeddings[0].values
    norm = np.linalg.norm(raw)
    return (np.array(raw) / norm).tolist()

def search(query_text: str, k: int = 3):
    query_vector = embed_query(query_text)
    results = db.collection("chunks").find_nearest(
        vector_field="embedding",
        query_vector=Vector(query_vector),
        distance_measure=DistanceMeasure.COSINE,
        limit=k,
        distance_result_field="vector_distance",
    ).get()

    print(f"\nQuery: \"{query_text}\"")
    for i, doc in enumerate(results):
        d = doc.to_dict()
        distance = d.get("vector_distance")
        similarity = 1 - distance if distance is not None else None
        print(f"  rank {i+1}: sim={similarity:.4f} [{d['section'][:40]}] — {d['content'][:60]}...")

if __name__ == "__main__":
    search("E-04 fault on the Haas VF-2SS, Line 3, what do I check?")
    search("Fuse replacement procedure, Line 5 electrical panel")
    search("What's the best pizza place near the facility?")
