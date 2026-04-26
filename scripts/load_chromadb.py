
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'backend'))
from backend.rag_pipeline import load_all_data, get_collection_stats
from backend.config import DOMAINS, DATA_DIR


def check_data_files():
    """Check which domain files are available."""
    print("📂 Checking data files...\n")
    available = []
    missing = []

    for domain in DOMAINS:
        chunks_file = os.path.join(DATA_DIR, domain, f"{domain}_chromadb_chunks.json")
        structured_file = os.path.join(DATA_DIR, domain, f"{domain}_structured.json")

        chunks_ok = os.path.exists(chunks_file)
        structured_ok = os.path.exists(structured_file)

        if chunks_ok:
            available.append(domain)
            print(f"  ✅ {domain:20} — chunks: ✅  structured: {'✅' if structured_ok else '⚠️ missing'}")
        else:
            missing.append(domain)
            print(f"  ❌ {domain:20} — chunks: ❌  structured: {'✅' if structured_ok else '❌'}")

    print(f"\nAvailable: {len(available)}/{len(DOMAINS)} domains")
    if missing:
        print(f"Missing:   {missing}")
    return available, missing


def main():
    print("=" * 60)
    print("  NyayMitra — ChromaDB Data Loader")
    print("=" * 60)
    print()

    # Check files
    available, missing = check_data_files()

    if not available:
        print("\n❌ No data files found! Please add domain data files first.")
        print(f"   Expected location: data/<domain>/<domain>_chromadb_chunks.json")
        sys.exit(1)

    print(f"\n📦 Loading {len(available)} domains into ChromaDB...\n")

    # Load data
    total = load_all_data()

    # Final stats
    stats = get_collection_stats()
    print(f"\n{'='*60}")
    print(f" ChromaDB loaded successfully!")
    print(f"   Total chunks: {stats['total_chunks']}")
    print(f"   Collection: {stats['collection_name']}")
    print(f"   Path: {stats['chromadb_path']}")
    print(f"{'='*60}")
    print(f"\n Now start the server:")
    print(f"   cd backend && uvicorn main:app --reload")


if __name__ == "__main__":
    main()