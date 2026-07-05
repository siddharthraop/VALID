from google import genai
from google.genai.types import EmbedContentConfig
import numpy as np

PROJECT_ID = "REMOVED"
REGION = "europe-west2"

client = genai.Client(vertexai=True, project=PROJECT_ID, location=REGION)

response = client.models.embed_content(
    model="gemini-embedding-001",
    contents="E-04 fault on the Haas VF-2SS, Line 3, what do I check?",
    config=EmbedContentConfig(
        task_type="RETRIEVAL_DOCUMENT",
        output_dimensionality=1536,
    ),
)

vector = response.embeddings[0].values
norm = np.linalg.norm(vector)
normalized = (np.array(vector) / norm).tolist()

print(f"Raw dimension: {len(vector)}")
print(f"Norm before normalization: {norm}")
print(f"First 5 normalized values: {normalized[:5]}")
