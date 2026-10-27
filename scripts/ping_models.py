"""Which Gemini models answer quickly on your key right now? Ten tiny calls in parallel, 45 s limit each.
  python scripts/ping_models.py"""
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from google.genai import types

from valid import gemini

MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.5-flash", "gemini-3.5-flash-lite",
          "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-flash", "gemini-2.5-flash-lite", "gemini-flash-latest"]
# (model, thinking level or None, json output)
CASES = [(m, None, False) for m in MODELS] + [("gemini-3.8-flash", "LOW", False), ("gemini-3.8-flash", "MINIMAL", False),
                                             ("gemini-3.8-flash", "LOW", True), ("gemini-3.7-flash", "LOW", True)]


def one(case):
    model, think, js = case
    cfg = types.GenerateContentConfig(
        http_options=gemini.http_options(45),
        thinking_config=types.ThinkingConfig(thinking_level=think) if think else None,
        response_mime_type="application/json" if js else None)
    prompt = 'Return JSON {"ok": true}' if js else "Reply with the single word OK."
    t = time.time()
    try:
        r = gemini.client().models.generate_content(model=model, contents=prompt, config=cfg)
        u = r.usage_metadata
        return case, time.time() - t, f"ok  out={getattr(u, 'candidates_token_count', None)} thoughts={getattr(u, 'thoughts_token_count', None)}"
    except Exception as e:
        return case, time.time() - t, f"{type(e).__name__}: {str(e)[:90]}"


with ThreadPoolExecutor(max_workers=len(CASES)) as ex:
    rows = list(ex.map(one, CASES))
print(f"{'model':<26}{'think':<9}{'json':<6}{'secs':>6}  result")
for (m, th, js), secs, res in rows:
    print(f"{m:<26}{th or '-':<9}{'yes' if js else '-':<6}{secs:>6.1f}  {res}")
