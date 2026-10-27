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
