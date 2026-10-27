"""generate_answer: Gemini fills an answer schema. Citations are an enum of the retrieved chunk ids,
and generation is an enum of the resolved scope, so the model cannot cite a chunk it was not given."""
from __future__ import annotations

import json
import time

from google.genai import errors, types

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


class ModelUnavailable(Exception):
    """Every model in the chain was busy, rate-limited, missing or unreachable."""

    def __init__(self, msg: str, attempts: list[dict] | None = None):
        super().__init__(msg)
        self.attempts = attempts or []


_down: dict[str, float] = {}      # model -> time until which it is skipped (it just failed)


def _call(model: str, contents: str, schema: dict, thinking: bool, timeout_s: int):
    cfg = types.GenerateContentConfig(
        system_instruction=SYSTEM, response_mime_type="application/json", response_json_schema=schema,
        http_options=gemini.http_options(timeout_s),
        thinking_config=types.ThinkingConfig(thinking_level=config.THINKING_LEVEL) if thinking else None)
    return gemini.client().models.generate_content(model=model, contents=contents, config=cfg)


def _skippable(e: Exception) -> bool:
    """Try the next model: busy, rate-limited, unreachable, or this model does not exist for the key."""
    return gemini.is_transient(e) or (isinstance(e, errors.APIError) and e.code == 404)


def generate_answer(question: str, scope: list[str], hits: dict[str, list[Hit]],
                    prior: dict | None = None, failures: list[dict] | None = None) -> tuple[dict, dict]:
    """Returns (answer_json, usage). Walks the model chain. Raises ModelUnavailable if every model fails,
    and ValueError if a model returns something that is not JSON."""
    ids = sorted({h.id for g in scope for h in hits[g]})
    schema = build_schema(scope, ids)
    contents = build_prompt(question, scope, hits, prior, failures)
    now = time.time()
    chain = [m for m in config.MODEL_CHAIN if _down.get(m, 0) <= now] or list(config.MODEL_CHAIN)
    attempts = [{"model": m, "result": "skipped: failed a moment ago"} for m in config.MODEL_CHAIN if m not in chain]
    last: Exception | None = None
    for model in chain:
        timeout = config.FIRST_TIMEOUT_S if model == config.MODEL_CHAIN[0] else config.CALL_TIMEOUT_S
        thinking, resp, t = bool(config.THINKING_LEVEL), None, time.time()
        for _ in range(2):
            try:
                resp = _call(model, contents, schema, thinking, timeout)
                break
            except Exception as e:
                if thinking and isinstance(e, errors.APIError) and e.code == 400 and "think" in str(e).lower():
                    thinking = False                       # this model does not take a thinking level: retry without
                    continue
                if _skippable(e):
                    last = e
                    break
                raise
        ms = int((time.time() - t) * 1000)
        if resp is None:
            _down[model] = time.time() + config.COOLDOWN_S
            attempts.append({"model": model, "result": f"{type(last).__name__}: {str(last)[:70]}", "ms": ms})
            continue
        attempts.append({"model": model, "result": "ok", "ms": ms})
        u = resp.usage_metadata
        out_tok = (getattr(u, "candidates_token_count", None) or getattr(u, "response_token_count", None) or 0) \
            + (getattr(u, "thoughts_token_count", None) or 0)
        usage = {"tokens_in": getattr(u, "prompt_token_count", 0) or 0, "tokens_out": out_tok,
                 "model": model, "attempts": attempts}
        try:
            return json.loads(resp.text), usage
        except (ValueError, TypeError) as e:
            raise ValueError(f"model did not return valid JSON: {e}") from e
    raise ModelUnavailable(f"{type(last).__name__}: {str(last)[:160]}" if last else "no model available", attempts)
