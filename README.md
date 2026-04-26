# NyayMitra — AI Legal Aid Chatbot 🏛️

AI-powered bilingual legal aid chatbot for Uttar Pradesh citizens.

## Tech Stack
| Layer | Technology |
|---|---|
| Backend | FastAPI (Python) |
| LLM | Sarvam-M (primary) + Groq Llama 3.3 (fallback) |
| Vector DB | ChromaDB |
| Embeddings | Sentence Transformers |
| Translation | Sarvam Translate API |
| App | WebView Android APK |

## Project Structure
```
legal-aid-chatbot/
├── backend/
│   ├── main.py              # FastAPI app + all routes
│   ├── rag_pipeline.py      # ChromaDB + RAG logic
│   ├── sarvam_client.py     # Sarvam-M + Groq LLM calls
│   ├── intent_detector.py   # Domain + intent detection
│   └── config.py            # All configuration
├── data/
│   └── <domain>/
│       ├── <domain>_structured.json
│       └── <domain>_chromadb_chunks.json
├── scripts/
│   ├── load_chromadb.py     # One-time data loader
│   └── test_rag.py          # Test RAG pipeline
└── frontend/
    ├── index.html
    ├── style.css
    └── app.js
```

## Setup

### 1. Clone and install
```bash
git clone https://github.com/your-repo/legal-aid-chatbot
cd legal-aid-chatbot
pip install -r requirements.txt
```

### 2. Setup environment
```bash
cp .env.example .env
# Edit .env and add your API keys
```

### 3. Load data into ChromaDB
```bash
python scripts/load_chromadb.py
```

### 4. Test RAG pipeline
```bash
python scripts/test_rag.py
```

### 5. Start server
```bash
cd backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

### 6. API Docs
Visit: http://localhost:8000/docs

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| POST | `/chat` | Main chat endpoint |
| POST | `/translate` | Translate text |
| GET | `/domains` | List all domains |
| GET | `/stats` | ChromaDB stats |
| GET | `/health` | Health check |
| DELETE | `/session/{id}` | Clear session |

## Team
| Member | Role |
|---|---|
| Divyansh Maurya | AI/Backend Lead |
| Akshay Pratap Singh | Data Engineering |
| Trishya Gupta | Data Engineering |
| Anup Kumar | Frontend/APK |
| Mayank Kumar Singh | Frontend/APK |

**Guide:** Er. Maruti Maurya
**University:** University of Lucknow, B.Tech CS/AI 2025-26
