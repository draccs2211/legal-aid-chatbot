#!/bin/bash
# Render startup script — loads ChromaDB data then starts server

echo "Loading ChromaDB data..."
python scripts/load_chromadb.py

echo "Starting NyayMitra server..."
cd backend && uvicorn main:app --host 0.0.0.0 --port $PORT