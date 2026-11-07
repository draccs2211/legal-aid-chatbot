import os
import re
import json
import chromadb

from config import (CHROMADB_PATH, COLLECTION_NAME, TOP_K_RESULTS, DATA_DIR, DOMAINS, DOMAIN_METADATA,
                    EMBEDDING_BACKEND, EMBEDDING_MODEL)
from embedding import get_embedder

# ─── Initialize ChromaDB client ───
_client = None
_collection = None


def get_client():
    global _client
    if _client is None:
        # Printed once so a wrong CHROMADB_PATH is visible in the logs instead of
        # silently producing a second, empty database.
        print(f"[rag] ChromaDB path: {CHROMADB_PATH} (exists: {os.path.isdir(CHROMADB_PATH)})")
        _client = chromadb.PersistentClient(path=CHROMADB_PATH)
    return _client


def _external():
    return EMBEDDING_BACKEND == "sentence_transformers"


def active_collection_name():
    """The default collection keeps its name. A multilingual model gets its own
    collection so both can coexist and rollback is just an env var."""
    if not _external():
        return COLLECTION_NAME
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", EMBEDDING_MODEL).strip("_").lower()
    return f"{COLLECTION_NAME}__{slug}"[:200]


def get_collection():
    global _collection
    if _collection is None:
        client = get_client()
        metadata = {"hnsw:space": "cosine"}
        if _external():
            metadata.update({"embedding_backend": EMBEDDING_BACKEND, "embedding_model": EMBEDDING_MODEL})
        collection = client.get_or_create_collection(name=active_collection_name(), metadata=metadata)
        if _external():
            built_with = (collection.metadata or {}).get("embedding_model")
            if built_with != EMBEDDING_MODEL:
                raise RuntimeError(
                    f"Collection {collection.name!r} was built with embedding model {built_with!r} but "
                    f"EMBEDDING_MODEL is {EMBEDDING_MODEL!r}. Mixing models silently ruins retrieval; "
                    "re-ingest into a fresh collection.")
        _collection = collection
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
        add_kwargs = {}
        if _external():
            add_kwargs["embeddings"] = get_embedder().embed_documents([c["text"] for c in new_chunks])
        collection.add(
            ids=[c["id"] for c in new_chunks],
            documents=[c["text"] for c in new_chunks],
            metadatas=[c["metadata"] for c in new_chunks],
            **add_kwargs
        )

        print(f"  ✅ {domain} — loaded {len(new_chunks)} new chunks")
        total_loaded += len(new_chunks)

    print(f"\n📦 Total loaded: {total_loaded} | Skipped (already exist): {total_skipped}")
    return total_loaded


def chroma_domain_value(domain: str) -> str:
    """Translate a detector domain name into the value stored in the metadata."""
    return DOMAIN_METADATA.get(domain, domain)


def retrieve_chunks(query: str, domain: str = None, top_k: int = TOP_K_RESULTS) -> list:
    """Retrieve relevant chunks for a query."""
    collection = get_collection()

    # Build filter
    where_filter = None
    if domain and domain != "general":
        where_filter = {"domain": chroma_domain_value(domain)}

    if _external():
        query_args = {"query_embeddings": [get_embedder().embed_query(query)]}
    else:
        query_args = {"query_texts": [query]}
    results = collection.query(
        n_results=top_k,
        where=where_filter,
        **query_args
    )

    chunks = []
    ids = (results.get("ids") or [[]])[0] if results else []
    if results and results["documents"] and results["documents"][0]:
        for i, doc in enumerate(results["documents"][0]):
            chunks.append({
                "id": ids[i] if i < len(ids) else None,
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
        "collection_name": active_collection_name(),
        "chromadb_path": CHROMADB_PATH,
        "embedding_backend": EMBEDDING_BACKEND,
        "embedding_model": EMBEDDING_MODEL if _external() else "chroma default (all-MiniLM-L6-v2)",
    }
