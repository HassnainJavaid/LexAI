import os
import argparse
import chromadb
from chromadb.utils import embedding_functions
from logger import logger

# Minimal setup to point to the exact same DB used by LexAI
CHROMA_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_data"))
client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
try:
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    collection = client.get_or_create_collection(name="legal_knowledge", embedding_function=emb_fn)
except Exception as e:
    logger.warning(f"Using default embedding function due to: {e}")
    collection = client.get_or_create_collection(name="legal_knowledge")

def chunk_text(text, max_length=400):
    """Splits text into chunks by line — identical logic to batch_ingest.py."""
    lines = text.split("\n")
    chunks = []
    current = []
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

def extract_text_from_pdf(pdf_path):
    # To handle PDFs, use PyMuPDF or pypdf but fallback to text reading if failed
    try:
        import PyPDF2
        text = ""
        with open(pdf_path, "rb") as f:
            reader = PyPDF2.PdfReader(f)
            for page in reader.pages:
                text += page.extract_text() + "\n"
        return text
    except ImportError:
        logger.error("PyPDF2 is not installed. Please run: pip install PyPDF2")
        return ""
    except Exception as e:
        logger.error(f"Failed to read PDF {pdf_path}: {e}")
        return ""

def ingest_file(file_path, country="Global", topic="Case Study"):
    logger.info(f"Processing File: {file_path}")
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == ".pdf":
        text = extract_text_from_pdf(file_path)
    else:
        with open(file_path, "r", encoding="utf-8") as f:
            text = f.read()

    if not text.strip():
        logger.warning("No text found. Skipping.")
        return

    chunks = chunk_text(text)
    docs, metadatas, ids = [], [], []
    base_id = os.path.basename(file_path).replace(' ', '_').replace('.', '_')
    
    for i, c in enumerate(chunks):
        docs.append(c)
        metadatas.append({"country": country, "topic": topic, "source": os.path.basename(file_path)})
        ids.append(f"custom_{base_id}_{i}")

    if docs:
        collection.upsert(documents=docs, metadatas=metadatas, ids=ids)
        logger.info(f"Successfully upserted '{file_path}' into {len(docs)} data blocks.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest legal documents into LexAI Vector DB.")
    parser.add_argument("file_path", help="Path to the PDF or TXT file to ingest")
    parser.add_argument("--country", default="Pakistan", help="Country metadata for the record")
    parser.add_argument("--topic", default="Court Record", help="Topic metadata for the record")
    args = parser.parse_args()
    
    if os.path.exists(args.file_path):
        ingest_file(args.file_path, args.country, args.topic)
    else:
        logger.error(f"File not found: {args.file_path}")