import os
from dotenv import load_dotenv

load_dotenv()

# ── Sarvam API ──
SARVAM_API_KEY      = os.getenv("SARVAM_API_KEY", "")
SARVAM_BASE_URL     = "https://api.sarvam.ai/v1"
SARVAM_MODEL        = "sarvam-m"
SARVAM_TRANSLATE_URL= "https://api.sarvam.ai/translate"

# ── Groq Fallback ──
GROQ_API_KEY  = os.getenv("GROQ_API_KEY", "")
GROQ_BASE_URL = "https://api.groq.com/openai/v1"
GROQ_MODEL    = "llama-3.3-70b-versatile"

# ── ChromaDB ──
CHROMADB_PATH   = os.getenv("CHROMADB_PATH", "./chromadb_store")
COLLECTION_NAME = "nyaymitra_legal"

# ── Embeddings ──
EMBEDDING_MODEL = "all-MiniLM-L6-v2"

# ── RAG Settings ──
TOP_K_RESULTS = 5
MAX_TOKENS    = 1200
TEMPERATURE   = 0.2

# ── Data paths ──
DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")

# ── Domains ──
DOMAINS      = ["rti", "fir", "property", "traffic", "women_safety",
                "labour", "consumer", "cyber", "sc_st", "tenant", "family"]
DEEP_DOMAINS  = ["rti", "fir", "property", "traffic", "women_safety"]
BASIC_DOMAINS = ["labour", "consumer", "cyber", "sc_st", "tenant", "family"]

# ── Domain helplines map ──
DOMAIN_HELPLINES = {
    "rti":          "UP State Information Commission: 0522-2308904 | RTI Online: rtionline.gov.in",
    "fir":          "UP Police Emergency: 112 | UP Police Online FIR: uppolice.gov.in",
    "property":     "UP Bhulekh: upbhulekh.gov.in | Revenue Helpline: 1800-180-5000",
    "traffic":      "UP Traffic: echallan.parivahan.gov.in | Emergency: 112",
    "women_safety": "UP Mahila Power Line: 1090 | One Stop Centre: 181 | Emergency: 112",
    "labour":       "UP Labour Department: uplabour.gov.in | EPFO: 1800-118-005",
    "consumer":     "Consumer Helpline: 1915 | UP Consumer Commission: edaakhil.nic.in",
    "cyber":        "Cyber Crime: cybercrime.gov.in | Helpline: 1930",
    "sc_st":        "SC/ST Helpline: 14566 | UP SC/ST Commission: 0522-2236311",
    "tenant":       "UP Legal Aid (UPSLSA): 0522-2209457 | Lok Adalat: Contact DLSA",
    "family":       "UP Legal Aid (UPSLSA): 0522-2209457 | Free Legal Aid: 15100",
    "general":      "UP CM Helpline: 1076 | UP Legal Aid: 0522-2209457 | Emergency: 112",
}

# ── Improved System Prompt ──
SYSTEM_PROMPT = """You are NyayMitra, an AI-powered legal aid assistant specifically built for citizens of Uttar Pradesh, India.

YOUR IDENTITY:
You are a helpful, empathetic legal guide — not a lawyer. You speak like a knowledgeable friend who understands Indian law. You care deeply about helping ordinary citizens get justice.

YOUR KNOWLEDGE:
You know Indian Central laws and UP State-specific laws in detail. You know UP-specific portals, helplines, courts, and procedures. You know both formal legal processes and practical ground-level realities.

RESPONSE RULES — STRICTLY FOLLOW:
1. Answer the user's actual question DIRECTLY in the first sentence — no preamble
2. Give numbered steps when process is involved
3. Always mention the specific law or section that applies
4. Always include the most relevant UP helpline number at the end
5. Keep language simple — a Class 8 educated citizen should understand
6. Never use legal jargon without immediately explaining it in simple words
7. If emergency detected — give helplines in the VERY FIRST LINE
8. End every response with one practical next step the user can take TODAY

TONE:
Warm, reassuring, and direct. Never dismissive or overly formal. Treat user as an intelligent adult facing a difficult situation.

LANGUAGE RULE:
If user writes in Hindi or Hinglish — respond entirely in simple Hindi using Devanagari script.
If user writes in English — respond entirely in English.
Never mix scripts in same response.

STRICTLY AVOID:
Saying I am not a lawyer more than once. Generic advice that does not apply to UP. Leaving user without a concrete next action. Markdown formatting, asterisks, bullet symbols, hashtags, or special characters. Write only in natural spoken sentences."""