#!/usr/bin/env bash
set -e
 
echo "=== NyayMitra Startup ==="
echo "PORT: $PORT"
 
# Load ChromaDB data
echo "Loading ChromaDB..."
python scripts/load_chromadb.py
 
# Start FastAPI server — must bind to $PORT
echo "Starting server on port $PORT..."
cd backend
exec uvicorn main:app --host 0.0.0.0 --port "${PORT:-8000}"
 
