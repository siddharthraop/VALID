import re
import os

NUMBERED_SUBSECTION = re.compile(r'^\d+\.\d+\s+\S.*$')  # "18.4 Fault Code E-04..."
LABEL_HEADING = re.compile(r'^[A-Z][A-Za-z\- /]+:$')     # "Root Cause:" / "Description of Non-Conformance:"
MAX_HEADING_LEN = 55  # section titles are short; list items are sentences

def is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if NUMBERED_SUBSECTION.match(stripped):
        return True
    if LABEL_HEADING.match(stripped):
        return True
    # Numbered section titles ("3. Isolation Procedure") vs list items
    # ("1. Retraining scheduled for..."): titles are short, list items aren't.
    if re.match(r'^\d+\.\s+\S.*$', stripped) and len(stripped) <= MAX_HEADING_LEN:
        return True
    return False

def procedural_chunk(text: str, doc_title: str) -> list[dict]:
    lines = text.splitlines()
    chunks = []
    current_heading = doc_title
    current_lines = []

    for line in lines:
        if is_heading(line):
            if current_lines:
                chunks.append({
                    "doc_title": doc_title,
                    "section": current_heading,
                    "content": "\n".join(current_lines).strip(),
                })
            current_heading = line.strip()
            current_lines = [line]
        else:
            current_lines.append(line)

    if current_lines:
        chunks.append({
            "doc_title": doc_title,
            "section": current_heading,
            "content": "\n".join(current_lines).strip(),
        })

    return [c for c in chunks if c["content"]]

if __name__ == "__main__":
    seed_dir = "data/seed_corpus"
    for filename in sorted(os.listdir(seed_dir)):
        path = os.path.join(seed_dir, filename)
        with open(path, "r") as f:
            text = f.read()
        chunks = procedural_chunk(text, doc_title=filename)
        print(f"\n=== {filename}: {len(chunks)} chunks ===")
        for c in chunks:
            first_line = c["content"].splitlines()[0][:60]
            print(f"  [{c['section'][:40]}] {len(c['content'])} chars — starts: {first_line}")
