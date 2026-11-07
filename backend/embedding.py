"""Optional multilingual embedder (sentence-transformers), used only when
EMBEDDING_BACKEND=sentence_transformers. See docs/embedding-migration.md.

The default backend (Chroma's built-in English MiniLM) is untouched.

Why embeddings are computed here and handed to Chroma: E5 models need
"query: " in front of questions and "passage: " in front of documents. A Chroma
embedding function cannot tell the two apart, so we embed ourselves.
"""
import threading

from config import EMBEDDING_BACKEND, EMBEDDING_MODEL

_lock = threading.Lock()
_embedder = None


def model_prefixes(model_name):
    """(query_prefix, passage_prefix). E5 models require them, even for
    non-English text (see the model card)."""
    if "e5" in model_name.lower():
        return "query: ", "passage: "
    return "", ""


def uses_external_embedder():
    return EMBEDDING_BACKEND == "sentence_transformers"


class SentenceTransformerEmbedder:
    def __init__(self, model_name):
        from sentence_transformers import SentenceTransformer  # heavy import, on demand

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.query_prefix, self.passage_prefix = model_prefixes(model_name)

    def embed_documents(self, texts):
        return self.model.encode(
            [self.passage_prefix + t for t in texts], normalize_embeddings=True
        ).tolist()

    def embed_query(self, text):
        return self.model.encode(
            [self.query_prefix + text], normalize_embeddings=True
        )[0].tolist()

    def info(self):
        return {
            "model": self.model_name,
            "max_seq_length": getattr(self.model, "max_seq_length", None),
            "query_prefix": self.query_prefix,
            "passage_prefix": self.passage_prefix,
        }


def get_embedder():
    """Process-wide singleton. Loading takes seconds and hundreds of MB of RAM."""
    global _embedder
    if not uses_external_embedder():
        raise RuntimeError("get_embedder() called but EMBEDDING_BACKEND is not 'sentence_transformers'")
    with _lock:
        if _embedder is None:
            _embedder = SentenceTransformerEmbedder(EMBEDDING_MODEL)
        return _embedder
