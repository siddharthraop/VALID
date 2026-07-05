import re
from google import genai
from google.genai.types import GenerateContentConfig
from g4_generate import gemini_client, GENERATION_SYSTEM_PROMPT
from google.genai.types import ThinkingConfig

CITATION_PATTERN = re.compile(r'Section\s+\d+(\.\d+)?', re.IGNORECASE)

def has_citation(text: str) -> bool:
    return bool(CITATION_PATTERN.search(text))

STRICT_RETRY_SUFFIX = "\n\nIMPORTANT: Your previous response did not include a section citation. You MUST cite the exact section (e.g. 'per Section 18.4') for every procedure step you describe."

def generate_with_citation_enforcement(query: str, chunks: list[dict], safety_flagged: bool) -> dict:
    context = "\n\n".join(f"[{c['section']}]\n{c['content']}" for c in chunks)
    prompt = f"Technician question: {query}\n\nRetrieved excerpts:\n{context}"

    response = gemini_client.models.generate_content(
        model="gemini-3-flash-preview",
        contents=prompt,
        config=GenerateContentConfig(system_instruction=GENERATION_SYSTEM_PROMPT, temperature=0, thinking_config=ThinkingConfig(thinking_level="low")),
    )
    answer = response.text.strip()

    if has_citation(answer):
        result = {"answer": answer, "citation_ok": True, "retried": False}
    else:
        retry_response = gemini_client.models.generate_content(
            model="gemini-3-flash-preview",
            contents=prompt + STRICT_RETRY_SUFFIX,
            config=GenerateContentConfig(system_instruction=GENERATION_SYSTEM_PROMPT, temperature=0, thinking_config=ThinkingConfig(thinking_level="low")),
        )
        retry_answer = retry_response.text.strip()
        if has_citation(retry_answer):
            result = {"answer": retry_answer, "citation_ok": True, "retried": True}
        else:
            result = {"answer": None, "citation_ok": False, "retried": True,
                       "refusal": "Unable to produce a cited response after retry — refusing rather than answering without a source reference."}

    if result["citation_ok"] and safety_flagged:
        result["answer"] = "⚠ LOCKOUT/TAGOUT OR HIGH-VOLTAGE HAZARD — verify isolation before proceeding.\n\n" + result["answer"]

    return result

if __name__ == "__main__":
    print("=== Unit test: has_citation() in isolation, no API call ===")
    with_citation = "Torque the nut to 45 Nm per Section 18.4."
    without_citation = "Torque the nut to 45 Nm as documented."
    print(f"With citation:    {has_citation(with_citation)}  (expect True)")
    print(f"Without citation: {has_citation(without_citation)}  (expect False)")

    print("\n=== End-to-end test against real pipeline ===")
    from g1_g2 import g1_normalize, retrieve_and_gate
    from g4_generate import g4_safety_flag, EXPANDED_K_ON_SAFETY_FLAG
    from g1_g2 import _find_nearest

    for raw in ["E-04 fault on the Haas VF-2SS, Line 3, what do I check?"]:
        normalized = g1_normalize(raw)
        result = retrieve_and_gate(normalized, k=3)
        chunks = result["chunks"]
        flagged = g4_safety_flag(chunks)
        if flagged:
            chunks = _find_nearest(result["query_vector"], EXPANDED_K_ON_SAFETY_FLAG)
        final = generate_with_citation_enforcement(normalized, chunks, flagged)
        print(f"\nQuery: \"{normalized}\"")
        print(f"citation_ok={final['citation_ok']} retried={final['retried']}")
        print(f"Answer:\n{final.get('answer') or final.get('refusal')}")
