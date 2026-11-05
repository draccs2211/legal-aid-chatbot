"""Build throw-away in-memory Chroma indexes with a chosen embedding model.

Used to compare embedding models on the labelled queries WITHOUT touching the
production database (`chromadb_store/`). The index is created in memory, filled
from data/*/*_chromadb_chunks.json, and discarded afterwards.

Embeddings are computed here and handed to Chroma, so Chroma never downloads
or runs a model of its own. Vectors are L2-normalised and Chroma's default
`l2` space is kept, so distances are on the same scale as the baseline's.
"""
import glob
import json
import os
import uuid


def model_prefixes(model_name):
    """(query_prefix, passage_prefix). E5 models need 'query: ' / 'passage: '
    on both sides, even for non-English text (see the model card)."""
    if "e5" in model_name.lower():
        return "query: ", "passage: "
    return "", ""


def load_chunks(data_dir):
    chunks = []
    for path in sorted(glob.glob(os.path.join(data_dir, "*", "*_chromadb_chunks.json"))):
        with open(path, encoding="utf-8") as f:
            chunks.extend(json.load(f))
    return chunks


def build_index(chunks, embed_docs, client=None):
    """Create an in-memory collection holding `chunks` embedded with `embed_docs`.

    embed_docs: function(list[str]) -> list[list[float]]
    """
    if client is None:
        import chromadb
        client = chromadb.EphemeralClient()
    collection = client.create_collection(f"eval_{uuid.uuid4().hex[:12]}")
    batch = 64
    for i in range(0, len(chunks), batch):
        part = chunks[i:i + batch]
        collection.add(
            ids=[c["id"] for c in part],
            documents=[c["text"] for c in part],
            metadatas=[c["metadata"] for c in part],
            embeddings=embed_docs([c["text"] for c in part]),
        )
    return collection


def make_index_retriever(collection, embed_query, domain_value):
    """retriever(query, domain, k) -> chunks sorted by distance (lower = closer).

    domain None or "general" means no filter. `domain_value` maps the router's
    domain name to the value stored in the metadata (cyber -> cyber_law).
    """
    def retriever(query, domain, k):
        where = None
        if domain and domain != "general":
            where = {"domain": domain_value(domain)}
        res = collection.query(
            query_embeddings=[embed_query(query)],
            n_results=k,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        out = []
        for i, cid in enumerate(res["ids"][0]):
            out.append({
                "id": cid,
                "text": res["documents"][0][i],
                "metadata": res["metadatas"][0][i],
                "distance": res["distances"][0][i],
            })
        return out

    return retriever


def sentence_transformer_embedders(model_name):
    """Load a sentence-transformers model. Returns (embed_docs, embed_query, info).

    Needs `sentence-transformers` and downloads the model from Hugging Face on
    first use. Sequences longer than the model's max_seq_length are truncated,
    so the loaded value is reported in `info`.
    """
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer(model_name)
    q_prefix, d_prefix = model_prefixes(model_name)

    def embed_docs(texts):
        return model.encode([d_prefix + t for t in texts], normalize_embeddings=True).tolist()

    def embed_query(text):
        return model.encode([q_prefix + text], normalize_embeddings=True)[0].tolist()

    info = {
        "model": model_name,
        "dimension": model.get_sentence_embedding_dimension(),
        "max_seq_length": getattr(model, "max_seq_length", None),
        "query_prefix": q_prefix, "passage_prefix": d_prefix,
    }
    return embed_docs, embed_query, info
