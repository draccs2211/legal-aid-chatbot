
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from backend.rag_pipeline import retrieve_chunks, format_context, get_collection_stats
from backend.intent_detector import analyze_query

TEST_QUERIES = [
    "RTI kaise file karein UP mein?",
    "Police FIR likhne se mana kar rahi hai",
    "Pati maar raha hai ghar mein, kya karoon?",
    "Mera landlord deposit wapas nahi de raha",
    "SC ST act mein kya rights hain?",
    "Challan galat kata hai mera",
    "Online UPI fraud hua hai",
]


def test_query(query: str):
    print(f"\n{'─'*60}")
    print(f"Query: {query}")

    analysis = analyze_query(query)
    print(f"Analysis: domain={analysis['domain']} | intent={analysis['intent']} | "
          f"lang={analysis['language']} | emergency={analysis['is_emergency']}")

    chunks = retrieve_chunks(query, domain=analysis['domain'], top_k=3)
    print(f"Retrieved: {len(chunks)} chunks")

    if chunks:
        for i, c in enumerate(chunks, 1):
            meta = c.get('metadata', {})
            dist = c.get('distance', 'N/A')
            print(f"  Chunk {i}: [{meta.get('domain','?')}] {meta.get('type','?')} "
                  f"— distance: {dist:.4f if isinstance(dist, float) else dist}")
            print(f"    Preview: {c['text'][:100]}...")
    else:
        print("  ⚠️  No chunks found!")


def main():
    print("=" * 60)
    print("  NyayMitra — RAG Pipeline Test")
    print("=" * 60)

    stats = get_collection_stats()
    print(f"\nChromaDB Stats:")
    print(f"  Total chunks: {stats['total_chunks']}")
    print(f"  Collection: {stats['collection_name']}")

    if stats['total_chunks'] == 0:
        print("\n❌ ChromaDB is empty! Run: python scripts/load_chromadb.py first")
        sys.exit(1)

    print(f"\nRunning {len(TEST_QUERIES)} test queries...")

    for query in TEST_QUERIES:
        test_query(query)

    print(f"\n{'='*60}")
    print("✅ RAG pipeline test complete!")


if __name__ == "__main__":
    main()