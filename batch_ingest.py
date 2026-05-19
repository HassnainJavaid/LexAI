"""
LexAI — Batch PDF Ingestor
Reads PDF files from the law-files/ directory and upserts them into the
same ChromaDB collection used by main.py.

Fixes applied vs original:
  1. Uses the SAME chunk_text() logic as main.py (split on "\n", max 400 chars)
     — previously the two chunkers were inconsistent, producing different
       semantic units for the same content.
  2. Stores consistent metadata: {country, topic, source_file}
     — previously topic was missing, which broke topic-filtered RAG queries.
  3. Derives topic from filename suffix after the country prefix, e.g.
       "Pakistan_Murder_Homicide.pdf"  →  topic="Murder Homicide"
       "Australia_Tenant_Rights.pdf"   →  topic="Tenant Rights"
     Falls back to "General" when no topic suffix is present.
  4. Uses upsert (not add) to safely re-run without duplicate-ID errors.
  5. CHROMA_DATA_PATH resolved relative to this script, matching main.py.

Usage:
    python batch_ingest.py
    python batch_ingest.py --dir /path/to/custom/pdf/folder
"""

import os
import glob
import argparse
from typing import List

import PyPDF2
import chromadb
from chromadb.utils import embedding_functions

# ──────────────────────────────────────────────────
#  ChromaDB — same path as main.py
# ──────────────────────────────────────────────────
CHROMA_DATA_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "chroma_data")
)
client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)

try:
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
        model_name="all-MiniLM-L6-v2"
    )
    collection = client.get_or_create_collection(
        name="legal_knowledge", embedding_function=emb_fn
    )
    print("✓ SentenceTransformer embedding loaded (all-MiniLM-L6-v2)")
except Exception as e:
    print(f"⚠ SentenceTransformer unavailable ({e}), using default embeddings.")
    emb_fn = None
    collection = client.get_or_create_collection(name="legal_knowledge")


# ──────────────────────────────────────────────────
#  Shared chunker — identical logic to main.py
# ──────────────────────────────────────────────────
def chunk_text(text: str, max_length: int = 400) -> List[str]:
    """
    Split legal text into focused chunks by line.
    Splits on single newlines (legal KB content is line-structured).
    Keeps each chunk under max_length characters.
    Intentionally identical to chunk_text() in main.py.
    """
    lines = text.split("\n")
    chunks: List[str] = []
    current: List[str] = []
    current_len = 0

    for line in lines:
        line = line.strip()
        if not line:
            continue
        if current_len + len(line) > max_length and current:
            chunks.append("\n".join(current))
            current = [line]
            current_len = len(line)
        else:
            current.append(line)
            current_len += len(line)

    if current:
        chunks.append("\n".join(current))
    return chunks


# ──────────────────────────────────────────────────
#  Metadata derivation from filename
# ──────────────────────────────────────────────────
def parse_filename_metadata(basename: str):
    """
    Derive (country, topic) from a PDF filename.

    Naming convention (recommended):
        <Country>_<Topic_With_Underscores>.pdf
        e.g. Pakistan_Murder_Homicide.pdf  ->  ("Pakistan", "Murder Homicide")
             Australia_Tenant_Rights.pdf   ->  ("Australia", "Tenant Rights")
             data_global.pdf               ->  ("Global", "General")

    Files that start with "data" are treated as Global/General.
    Files with no underscore are treated as country=name, topic="General".
    """
    name, _ = os.path.splitext(basename)

    if name.lower().startswith("data"):
        return "Global", "General"

    parts = name.split("_", 1)
    country = parts[0].replace("-", " ").strip()
    topic = parts[1].replace("_", " ").strip() if len(parts) > 1 else "General"
    return country, topic


# ──────────────────────────────────────────────────
#  PDF text extraction
# ──────────────────────────────────────────────────
def extract_text_from_pdf(pdf_path: str) -> str:
    try:
        text = ""
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
        return text
    except Exception as e:
        print(f"  Failed to read {pdf_path}: {e}")
        return ""


# ──────────────────────────────────────────────────
#  Per-file processor
# ──────────────────────────────────────────────────
def process_file(file_path: str) -> int:
    """Chunk and upsert a single PDF. Returns number of chunks upserted."""
    basename = os.path.basename(file_path)
    country, topic = parse_filename_metadata(basename)
    safe_base = basename.replace(" ", "_").replace(".", "_")

    print(f"  Processing '{basename}'")
    print(f"    -> country: {country!r}, topic: {topic!r}")

    text = extract_text_from_pdf(file_path)
    if not text.strip():
        print(f"    No text extracted. Skipping.")
        return 0

    docs, metadatas, ids = [], [], []
    for i, chunk in enumerate(chunk_text(text, max_length=400)):
        if len(chunk.strip()) < 80:
            continue
        docs.append(chunk)
        metadatas.append({
            "country": country,
            "topic": topic,
            "source_file": safe_base,
        })
        ids.append(f"batch_{safe_base}_{i}")

    if not docs:
        print(f"    All chunks were too short. Skipping.")
        return 0

    try:
        batch_size = 100
        for i in range(0, len(docs), batch_size):
            collection.upsert(
                documents=docs[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )
        print(f"    Upserted {len(docs)} chunks.")
        return len(docs)
    except Exception as e:
        print(f"    Error ingesting '{basename}': {e}")
        return 0


# ──────────────────────────────────────────────────
#  Entry point
# ──────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="LexAI PDF batch ingestor")
    parser.add_argument(
        "--dir",
        default=os.path.abspath(os.path.join(os.path.dirname(__file__), "law-files")),
        help="Directory containing PDF files to ingest (default: ./law-files/)",
    )
    args = parser.parse_args()

    pdf_files = glob.glob(os.path.join(args.dir, "*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in: {args.dir}")
        return

    print(f"\nFound {len(pdf_files)} PDF file(s) in '{args.dir}'")
    print(f"ChromaDB path: {CHROMA_DATA_PATH}\n")

    total_chunks = 0
    for pdf in sorted(pdf_files):
        total_chunks += process_file(pdf)

    stored = collection.count()
    print(f"\nDone. Upserted {total_chunks} new chunks this run.")
    print(f"Total documents in collection: {stored}")


if __name__ == "__main__":
    main()
