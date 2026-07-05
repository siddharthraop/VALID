import os
import numpy as np
from google import genai
from google.genai.types import EmbedContentConfig
from google.cloud import firestore
from google.cloud.firestore_v1.vector import Vector
from chunker import procedural_chunk

PROJECT_ID = "REMOVED"
REGION = "europe-west2"
SEED_DIR = "data/seed_corpus"
DIMENSIONALITY = 1536

client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)
db = firestore.Client(project=PROJECT_ID)

def embed_and_normalize(text: str) -> list[float]:
    response = client.models.embed_content(
        model="gemini-embedding-001",
        contents=text,
        config=EmbedContentConfig(
            task_type="RETRIEVAL_DOCUMENT",
            output_dimensionality=DIMENSIONALITY,
        ),
    )
    raw = response.embeddings[0].values
    norm = np.linalg.norm(raw)
    return (np.array(raw) / norm).tolist()

def main():
    total_written = 0
    for filename in sorted(os.listdir(SEED_DIR)):
        path = os.path.join(SEED_DIR, filename)
        with open(path, "r") as f:
            text = f.read()

        chunks = procedural_chunk(text, doc_title=filename)
        print(f"\n{filename}: {len(chunks)} chunks to embed")

        for i, chunk in enumerate(chunks):
            vector = embed_and_normalize(chunk["content"])
            doc_id = f"{filename.replace('.txt', '')}_{i:02d}"

            db.collection("chunks").document(doc_id).set({
                "doc_title": chunk["doc_title"],
                "section": chunk["section"],
                "content": chunk["content"],
                "embedding": Vector(vector),
            })
            print(f"  wrote {doc_id} — section: {chunk['section'][:40]}")
            total_written += 1

    print(f"\nTotal chunks written to Firestore: {total_written}")

if __name__ == "__main__":
    main()
