from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
import uvicorn

from backend.intent_detector import analyze_query
from backend.rag_pipeline import retrieve_chunks, format_context, get_collection_stats
from backend.sarvam_client import generate_response, translate_text
from backend.config import DEEP_DOMAINS, BASIC_DOMAINS
import re
from backend.rag_pipeline import load_all_data

db_loaded = False

def ensure_db_loaded():
    global db_loaded
    if not db_loaded:
        print("🔄 Loading ChromaDB...")
        load_all_data()   # ✅ correct function
        db_loaded = True

def clean_reply(text: str) -> str:
    """Remove <think> reasoning tags from Sarvam-M output."""
    text = re.sub(r'<think>.*?</think>', '', text, flags=re.DOTALL)
    return text.strip()
# ─── FastAPI App ───
app = FastAPI(
    title="NyayMitra API",
    description="AI-powered Legal Aid Chatbot for UP Citizens",
    version="1.0.0"
)

# ─── CORS — allow frontend/APK access ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Request/Response Models ───
class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = "default"
    conversation_history: Optional[List[dict]] = []


class ChatResponse(BaseModel):
    reply: str
    domain: str
    intent: str
    language: str
    is_emergency: bool
    session_id: str
    quick_actions: List[str] = []


class HealthResponse(BaseModel):
    status: str
    message: str
    chromadb_stats: dict


# ─── In-memory session store ───
sessions: dict = {}


# ─── Helper: get quick actions based on domain ───
def get_quick_actions(domain: str, intent: str) -> List[str]:
    actions_map = {
        "rti": ["RTI template chahiye", "RTI fees kitni hai?", "UP mein RTI kaise karein?", "Appeal process batao"],
        "fir": ["FIR template chahiye", "Police FIR nahi likh rahi", "Zero FIR kya hai?", "UP 112 kab call karein?"],
        "women_safety": ["Emergency helpline chahiye", "Protection Order kaise lein?", "1090 kya hai?", "DV Act kya hai?"],
        "property": ["Land record kaise dekhein?", "UP Bhulekh portal", "Encroachment complaint", "RERA complaint"],
        "traffic": ["Challan check karna hai", "Galat challan ka appeal", "License suspend hua", "Vehicle seized"],
        "sc_st": ["FIR kaise karein?", "14566 helpline", "Compensation kaise milega?", "Special Court kahan hai?"],
        "tenant": ["Eviction se bachav", "Deposit wapas chahiye", "Rent Court kahan hai?", "Legal notice bhejo"],
        "consumer": ["Consumer Forum complaint", "Online fraud complaint", "Refund nahi mila", "edaakhil.nic.in"],
        "labour": ["Salary nahi mili", "PF complaint", "Labour Court kahan?", "Minimum wage kya hai?"],
        "cyber": ["Cyber crime report", "UPI fraud hua", "cybercrime.gov.in", "UP Cyber Cell"],
        "family": ["Free legal aid chahiye", "UPSLSA contact", "Vakeel se milna hai"],
        "general": ["RTI ke baare mein", "FIR kaise karein?", "Women safety helpline", "SC/ST rights"]
    }
    return actions_map.get(domain, actions_map["general"])


# ─── Routes ───

@app.get("/", response_model=HealthResponse)
async def root():
    ensure_db_loaded()   # 🔥 ADD THIS
    stats = get_collection_stats()
    return HealthResponse(
        status="ok",
        message="NyayMitra API is running 🏛️",
        chromadb_stats=stats
    )


@app.get("/health")
async def health():
    return {"status": "ok", "service": "NyayMitra Legal Aid API"}


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    try:
        message = request.message.strip()
        if not message:
            raise HTTPException(status_code=400, detail="Message cannot be empty")

        # ─── Step 1: Analyze query ───
        analysis = analyze_query(message)
        domain = analysis["domain"]
        intent = analysis["intent"]
        language = analysis["language"]
        is_emergency = analysis["is_emergency"]
        ensure_db_loaded()
        # ─── Step 2: Retrieve relevant chunks ───
        chunks = retrieve_chunks(
            query=message,
            domain=domain if domain != "general" else None,
            top_k=5
        )

        # If no chunks found for specific domain, try general search
        if not chunks:
            chunks = retrieve_chunks(query=message, domain=None, top_k=5)

        context = format_context(chunks)

        # ─── Step 3: Get conversation history from session ───
        session_history = sessions.get(request.session_id, [])

        # ─── Step 4: Generate response ───
        response_text = generate_response(
            query=message,
            context=context,
            language=language,
            is_emergency=is_emergency,
            conversation_history=session_history
        )
        response_text = clean_reply(response_text)
        # ─── Step 5: Update session history ───
        session_history.append({"role": "user", "content": message})
        session_history.append({"role": "assistant", "content": response_text})
        sessions[request.session_id] = session_history[-10:]  # Keep last 5 turns

        # ─── Step 6: Get quick actions ───
        quick_actions = get_quick_actions(domain, intent)

        return ChatResponse(
            reply=response_text,
            domain=domain,
            intent=intent,
            language=language,
            is_emergency=is_emergency,
            session_id=request.session_id,
            quick_actions=quick_actions
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Chat error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal error: {str(e)}")


@app.post("/translate")
async def translate(source_text: str, source_lang: str = "english", target_lang: str = "hindi"):
    """Translate text using Sarvam Translate API."""
    try:
        translated = translate_text(source_text, source_lang, target_lang)
        return {
            "original": source_text,
            "translated": translated,
            "source_lang": source_lang,
            "target_lang": target_lang
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/domains")
async def get_domains():
    """Get list of all supported legal domains."""
    return {
        "deep_domains": DEEP_DOMAINS,
        "basic_domains": BASIC_DOMAINS,
        "total": len(DEEP_DOMAINS) + len(BASIC_DOMAINS)
    }


@app.get("/stats")
async def get_stats():
    ensure_db_loaded()   # 🔥 ADD THIS
    return get_collection_stats()


@app.delete("/session/{session_id}")
async def clear_session(session_id: str):
    """Clear conversation history for a session."""
    if session_id in sessions:
        del sessions[session_id]
    return {"message": f"Session {session_id} cleared"}

# main.py mein yeh 2 endpoints add karo — existing code ke baad

from fastapi import UploadFile, File, Form
from backend.sarvam_speech import speech_to_text, text_to_speech


@app.post("/stt")
async def stt_endpoint(
    audio: UploadFile = File(...),
    language: str = Form(default="unknown")
):
    """
    Speech to Text — Frontend se audio blob receive karo, text return karo.
    Frontend browser microphone se record karta hai aur yahan bhejta hai.
    """
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="Empty audio file")

        result = await speech_to_text(audio_bytes, language)

        if "error" in result and not result.get("transcript"):
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "transcript": result.get("transcript", ""),
            "language_code": result.get("language_code", "hi-IN"),
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# main.py mein /tts endpoint update karo — yeh replace karo purana wala

from typing import Any

@app.post("/tts")
async def tts_endpoint(request: dict):
    """
    Text to Speech — chunked audio for long responses.
    Returns list of base64 audio chunks.
    """
    try:
        text     = request.get("text", "").strip()
        language = request.get("language", "hi-IN")

        if not text:
            raise HTTPException(status_code=400, detail="Text is required")

        result = await text_to_speech(text, language)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])

        return {
            "audio_chunks":  result["audio_chunks"],
            "chunk_count":   result["chunk_count"],
            "content_type":  result["content_type"],
            "success": True
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
# ─── Run ───
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
