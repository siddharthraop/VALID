"""Settings. Everything overridable by environment variable; nothing secret lives here."""
import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Where the DITA corpus is checked out (sibling folder by default).
CORPUS_DIR = Path(os.environ.get("VALID_CORPUS", REPO_ROOT.parent / "dita-corpus")).resolve()
ROOT_MAP = os.environ.get("VALID_ROOT_MAP", "tpu/tpu.ditamap")
SCHEME_MAP = os.environ.get("VALID_SCHEME", "tpu/subjects/tpu-scheme.ditamap")

BUILD_DIR = REPO_ROOT / "build"
DATA_DIR = REPO_ROOT / "data"          # shipped with the service: chunks.jsonl, owned.json

# Models: names come from the design doc. Verified against the API key before use.
ANSWER_MODEL = os.environ.get("VALID_ANSWER_MODEL", "gemini-3.8-flash")
EMBED_MODEL = os.environ.get("VALID_EMBED_MODEL", "gemini-embedding-2")
EMBED_DIM = int(os.environ.get("VALID_EMBED_DIM", "1536"))

# Google Cloud
PROJECT_ID = os.environ.get("VALID_PROJECT", "valid-mvp-8425")
COLLECTION = os.environ.get("VALID_COLLECTION", "chunks")
# The Gemini key is read from the GEMINI_API_KEY environment variable. It is never stored in a file.

# Retrieval and refusal (calibrated on this corpus with scripts/calibrate.py)
RETRIEVE_K = int(os.environ.get("VALID_K", "6"))                    # chunks per generation sent to the model
MAX_DISTANCE = float(os.environ.get("VALID_MAX_DISTANCE", "0.40"))  # best cosine distance above this: refuse
MAX_REVISIONS = 2                                                   # design 5.5

# Resilience on the free tier (Gemini returns 503 "high demand" at busy times)
FALLBACK_MODEL = os.environ.get("VALID_FALLBACK_MODEL", "gemini-3.7-flash")  # tried once if the main model is busy
THINKING_LEVEL = os.environ.get("VALID_THINKING", "LOW")                     # MINIMAL | LOW | MEDIUM | HIGH
CALL_TIMEOUT_S = int(os.environ.get("VALID_CALL_TIMEOUT", "20"))             # per Gemini call, no hidden retries

# Model chain: tried in order. A model that just failed is skipped for COOLDOWN_S, so a dead model costs one slow call, not every call.
FALLBACK_MODEL = os.environ.get("VALID_FALLBACK_MODEL", "gemini-3.6-flash")
EXTRA_FALLBACK_MODEL = os.environ.get("VALID_EXTRA_FALLBACK_MODEL", "gemini-3.5-flash")
MODEL_CHAIN = list(dict.fromkeys([ANSWER_MODEL, FALLBACK_MODEL, EXTRA_FALLBACK_MODEL]))
FIRST_TIMEOUT_S = int(os.environ.get("VALID_FIRST_TIMEOUT", "15"))     # the first model gets less time
COOLDOWN_S = int(os.environ.get("VALID_COOLDOWN", "300"))
