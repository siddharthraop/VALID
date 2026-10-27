"""generate_answer: Gemini fills an answer schema. Citations are an enum of the retrieved chunk ids,
and generation is an enum of the resolved scope, so the model cannot cite a chunk it was not given."""
from __future__ import annotations

import json

from google.genai import types

from . import config, gemini
from .retrieve import Hit

SYSTEM = """You answer questions about Cloud TPU documentation using ONLY the context chunks provided.
Each chunk has an id and the generations it applies to.

Rules:
- Use only facts stated in the chunks. Never use your own knowledge. Never add a value that is not in a chunk.
- Copy every number, unit, flag, command and version string exactly as written in the chunk you cite.
- Each step states one fact or action and cites exactly one chunk id that contains it. Do not number the steps.
- Put a command in the "command" field only if the cited chunk contains that exact command; otherwise leave it out.
- If a chunk says something is not supported or that nothing is listed for the reader's generation, that is the answer: say so.
- If the chunks do not answer the question, set answerable to false, leave steps empty, and say in "missing" what the documentation does not provide.
- Answer only for the generations named in the question. When the question names two generations, give separate steps for each, labelled with the generation field.
- Do not mention or compare other generations. Keep the answer short: at most six steps."""


def build_schema(scope: list[str], chunk_ids: list[str]) -> dict:
    return {
        "type": "object",
        "properties": {
            "answerable": {"type": "boolean"},
            "answer": {"type": "string", "description": "One or two sentences that answer the question."},
            "steps": {"type": "array", "items": {"type": "object", "properties": {
                "generation": {"type": "string", "enum": scope},
                "text": {"type": "string"},
                "command": {"type": "string"},
                "cite": {"type": "string", "enum": chunk_ids},
            }, "required": ["generation", "text", "cite"]}},
            "missing": {"type": "string"},
        },
        "required": ["answerable", "answer", "steps"],
    }


def build_prompt(question: str, scope: list[str], hits: dict[str, list[Hit]],
                 prior: dict | None = None, failures: list[dict] | None = None) -> str:
    parts = [f"Question: {question}", f"Generation(s) in scope: {', '.join(scope)}", "", "Context:"]
    for g in scope:
        parts.append(f"\n## Chunks retrieved for {g}")
        for h in hits[g]:
            parts.append(f"[{h.id}] (applies to: {', '.join(h.scope)})\n{h.text}")
    if prior is not None and failures:
        parts += ["", "Your previous answer was rejected by automatic checks:", json.dumps(prior, indent=1),
                  "Failed checks:"] + [f"- step {f['step'] + 1 if f['step'] >= 0 else 'summary'}: {f['reason']}" for f in failures]
        parts.append("Write a corrected answer. Fix the failed items, copy values exactly from the cited chunk, "
                     "and remove anything the chunks do not state.")
    return "\n".join(parts)


def generate_answer(question: str, scope: list[str], hits: dict[str, list[Hit]],
                    prior: dict | None = None, failures: list[dict] | None = None) -> tuple[dict, dict]:
    """Returns (answer_json, usage). Raises ValueError if the model returns something that is not JSON."""
    ids = sorted({h.id for g in scope for h in hits[g]})
    cfg = types.GenerateContentConfig(system_instruction=SYSTEM, response_mime_type="application/json",
                                      response_json_schema=build_schema(scope, ids))
    resp = gemini.client().models.generate_content(
        model=config.ANSWER_MODEL, contents=build_prompt(question, scope, hits, prior, failures), config=cfg)
    u = resp.usage_metadata
    out_tok = (getattr(u, "candidates_token_count", None) or getattr(u, "response_token_count", None) or 0) \
        + (getattr(u, "thoughts_token_count", None) or 0)
    usage = {"tokens_in": getattr(u, "prompt_token_count", 0) or 0, "tokens_out": out_tok}
    try:
        return json.loads(resp.text), usage
    except (ValueError, TypeError) as e:
        raise ValueError(f"model did not return valid JSON: {e}") from e
