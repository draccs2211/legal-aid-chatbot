import os
import json
import chromadb

from backend.config import CHROMADB_PATH, COLLECTION_NAME, TOP_K_RESULTS, DATA_DIR, DOMAINS

# ─── Initialize ChromaDB client ───
_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        _client = chromadb.PersistentClient(path=CHROMADB_PATH)
    return _client


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        # Use ChromaDB default embedding (no external download needed)
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}
        )
    return _collection


def load_all_data():
    """Load all domain ChromaDB chunks into ChromaDB collection."""
    collection = get_collection()

    total_loaded = 0
    total_skipped = 0

    for domain in DOMAINS:
        chunks_file = os.path.join(DATA_DIR, domain, f"{domain}_chromadb_chunks.json")

        if not os.path.exists(chunks_file):
            print(f"  ⚠️  Skipping {domain} — chunks file not found")
            continue

        with open(chunks_file, "r", encoding="utf-8") as f:
            chunks = json.load(f)

        # Check existing IDs to avoid duplicates
        existing = collection.get(ids=[c["id"] for c in chunks])
        existing_ids = set(existing["ids"])

        new_chunks = [c for c in chunks if c["id"] not in existing_ids]

        if not new_chunks:
            print(f"  ✅ {domain} — already loaded ({len(chunks)} chunks)")
            total_skipped += len(chunks)
            continue

        # Load new chunks
        collection.add(
            ids=[c["id"] for c in new_chunks],
            documents=[c["text"] for c in new_chunks],
            metadatas=[c["metadata"] for c in new_chunks]
        )

        print(f"  ✅ {domain} — loaded {len(new_chunks)} new chunks")
        total_loaded += len(new_chunks)

    print(f"\n📦 Total loaded: {total_loaded} | Skipped (already exist): {total_skipped}")
    return total_loaded


def retrieve_chunks(query: str, domain: str = None, top_k: int = TOP_K_RESULTS) -> list:
    """Retrieve relevant chunks for a query."""
    collection = get_collection()

    # Build filter
    where_filter = None
    if domain and domain != "general":
        where_filter = {"domain": domain}

    results = collection.query(
        query_texts=[query],
        n_results=top_k,
        where=where_filter
    )

    chunks = []
    if results and results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            chunks.append({
                "text": doc,
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i] if results.get("distances") else None
            })

    return chunks


def retrieve_multi_domain(query: str, domains: list, top_k: int = 3) -> list:
    """Retrieve chunks across multiple domains."""
    all_chunks = []
    for domain in domains:
        chunks = retrieve_chunks(query, domain=domain, top_k=top_k)
        all_chunks.extend(chunks)

    # Sort by distance (lower = more relevant)
    all_chunks.sort(key=lambda x: x.get("distance") or 1.0)
    return all_chunks[:top_k * 2]


def format_context(chunks: list) -> str:
    """Format retrieved chunks into context string for LLM."""
    if not chunks:
        return "No specific legal information found for this query."

    context_parts = []
    for i, chunk in enumerate(chunks, 1):
        meta = chunk.get("metadata", {})
        source = meta.get("source", "")
        domain = meta.get("domain", "")
        context_parts.append(
            f"[Source {i} — Domain: {domain}, Law: {source}]\n{chunk['text']}"
        )

    return "\n\n---\n\n".join(context_parts)


def get_collection_stats() -> dict:
    """Get stats about the ChromaDB collection."""
    collection = get_collection()
    count = collection.count()
    return {
        "total_chunks": count,
        "collection_name": COLLECTION_NAME,
        "chromadb_path": CHROMADB_PATH
    }
