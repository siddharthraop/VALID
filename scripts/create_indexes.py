"""Create one Firestore composite vector index per generation in the subject scheme (equality on in_<gen> + vector).
Safe to re-run: an index that already exists is skipped.  python scripts/create_indexes.py"""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from valid import config
from valid.scheme import load_scheme


def main() -> int:
    scheme = load_scheme(config.CORPUS_DIR / config.SCHEME_MAP)
    vec = '{"dimension":"%d", "flat": "{}"}' % config.EMBED_DIM
    for g in scheme.keys:
        cmd = ["gcloud", "firestore", "indexes", "composite", "create",
               f"--collection-group={config.COLLECTION}", "--query-scope=COLLECTION",
               f"--field-config=order=ASCENDING,field-path=in_{g}",
               f"--field-config=field-path=embedding,vector-config={vec}",
               f"--project={config.PROJECT_ID}", "--database=(default)", "--quiet"]
        r = subprocess.run(cmd, capture_output=True, text=True)
        msg = (r.stdout + r.stderr).strip().splitlines()
        if r.returncode == 0:
            print(f"in_{g}: created")
        elif "already exists" in (r.stdout + r.stderr).lower():
            print(f"in_{g}: already exists")
        else:
            print(f"in_{g}: FAILED\n  " + "\n  ".join(msg[-6:]))
            return 1
    subprocess.run(["gcloud", "firestore", "indexes", "composite", "list", f"--project={config.PROJECT_ID}",
                    "--format=table(name.basename():label=ID,fields[0].fieldPath:label=FIELD,state)"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
