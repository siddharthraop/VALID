from google import genai
from google.genai.types import GenerateContentConfig
from g1_g2 import g1_normalize, retrieve_and_gate, _find_nearest

PROJECT_ID = "REMOVED"
GEMINI_LOCATION = "global"

gemini_client = genai.Client(vertexai=True, project=PROJECT_ID, location=GEMINI_LOCATION)

SAFETY_KEYWORDS = ["lockout", "tagout", "loto", "high voltage", "480v", "pressure vessel", "de-energise", "disconnect switch"]
EXPANDED_K_ON_SAFETY_FLAG = 5

def g4_safety_flag(chunks: list[dict]) -> bool:
    combined_text = " ".join(c["content"].lower() for c in chunks)
    return any(kw in combined_text for kw in SAFETY_KEYWORDS)

GENERATION_SYSTEM_PROMPT = """You are a maintenance assistant for a manufacturing facility. Answer the
technician's question using ONLY the provided document excerpts. You MUST cite the exact section name
for any procedure you describe (e.g. "per Section 18.4"). If the excerpts do not fully answer the
question, say so rather than guessing. Be concise and step-by-step where the source material is."""

def generate_response(query: str, chunks: list[dict], safety_flagged: bool) -> str:
    context = "\n\n".join(f"[{c['section']}]\n{c['content']}" for c in chunks)
    prompt = f"Technician question: {query}\n\nRetrieved excerpts:\n{context}"

    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=GenerateContentConfig(system_instruction=GENERATION_SYSTEM_PROMPT, temperature=0),
    )
    answer = response.text.strip()

    if safety_flagged:
        answer = "⚠ LOCKOUT/TAGOUT OR HIGH-VOLTAGE HAZARD — verify isolation before proceeding.\n\n" + answer

    return answer

def run_pipeline(raw_query: str):
    normalized = g1_normalize(raw_query)
    result = retrieve_and_gate(normalized, k=3)
    print(f"\nQuery: \"{normalized}\"")

    if result["blocked_at"]:
        print(f"Blocked at {result['blocked_at']}, sim={result['top1_similarity']:.4f}")
        return

    chunks = result["chunks"]
    flagged = g4_safety_flag(chunks)
    print(f"G4 safety flag (k=3): {flagged}")

    if flagged:
        expanded_chunks = _find_nearest(result["query_vector"], EXPANDED_K_ON_SAFETY_FLAG)
        added = len(expanded_chunks) - len(chunks)
        print(f"G4 fired -> re-querying at k={EXPANDED_K_ON_SAFETY_FLAG} ({added} additional chunk(s) surfaced)")
        chunks = expanded_chunks

    answer = generate_response(normalized, chunks, flagged)
    print(f"Response:\n{answer}")

if __name__ == "__main__":
    run_pipeline("E-04 fault on the Haas VF-2SS, Line 3, what do I check?")
    run_pipeline("Fuse replacement procedure, Line 5 electrical panel")
