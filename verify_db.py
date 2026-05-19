import os
import chromadb
from chromadb.utils import embedding_functions

# Connect directly to ChromaDB — does NOT import or boot main.py
CHROMA_DATA_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "chroma_data"))
client = chromadb.PersistentClient(path=CHROMA_DATA_PATH)
try:
    emb_fn = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
    legal_collection = client.get_or_create_collection(name="legal_knowledge", embedding_function=emb_fn)
except Exception:
    legal_collection = client.get_or_create_collection(name="legal_knowledge")

def get_rag_context(country, topic, question, n_results=5):
    where_filter = {"$and": [{"country": country}, {"topic": topic}]} if topic else {"country": country}
    results = legal_collection.query(query_texts=[question], n_results=n_results, where=where_filter)
    if results and results.get("documents") and results["documents"][0]:
        valid = [c for c in results["documents"][0] if len(c.strip()) > 120]
        return "\n\n---\n\n".join(valid) if valid else "(no valid chunks returned)"
    return "(no results)"

def test_db():
    print("Testing Vector DB Querying Logic...")
    print(f"Total documents in DB: {legal_collection.count()}")

    for country, topic, question in [
        ("Australia", "Tenant Rights", "Can a landlord evict me without notice?"),
        ("Pakistan",  "Murder",        "What is the law regarding murder and Qisas?"),
    ]:
        print(f"\n--- QUERY: Country='{country}', Topic='{topic}' ---")
        print(f"    Question: {question}")
        ctx = get_rag_context(country, topic, question)
        print(ctx[:600] + ("..." if len(ctx) > 600 else ""))
        print("--------------------")

if __name__ == "__main__":
    test_db()