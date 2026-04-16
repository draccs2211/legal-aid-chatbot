import os
from dotenv import load_dotenv
#Load environment variables
load_dotenv()
def get_env(key: str, default=None, required: bool=False):
    value = os.getenv(key, default)
    if required and (value is None or value == ""):
        raise ValueError(f"Missing required environment variable: {key}")
    return value
# ─── Sarvam API(Primary LLM) ───
SARVAM_API_KEY = get_env("SARVAM_API_KEY", required=True)
SARVAM_BASE_URL = get_env("SARVAM_BASE_URL","https://api.sarvam.ai/v1")
SARVAM_MODEL = get_env("SARVAM_MODEL","sarvam-m")
SARVAM_TRANSLATE_URL = get_env("SARVAM_TRANSLATE_URL", "https://api.sarvam.ai/translate")
# ─── Groq (Fallback LLM) ───
GROQ_API_KEY = get_env("GROQ_API_KEY", required=False)  
GROQ_BASE_URL = get_env("GROQ_BASE_URL", "https://api.groq.com/openai/v1")
GROQ_MODEL = get_env("GROQ_MODEL", "llama-3.3-70b-versatile")

# ─── ChromaDB ───
CHROMADB_PATH = get_env("CHROMADB_PATH", "./chromadb_store")
COLLECTION_NAME = get_env("COLLECTION_NAME", "nyaymitra_legal")

# ─── Embeddings ───
EMBEDDING_MODEL = get_env("EMBEDDING_MODEL", "all-MiniLM-L6-v2")

# ─── RAG Settings ───
TOP_K_RESULTS = int(get_env("TOP_K_RESULTS", 5)) #Top chunks to retrieve
MAX_TOKENS = int(get_env("MAX_TOKENS", 1000))    #Max response tokens
TEMPERATURE = float(get_env("TEMPERATURE", 0.3))        

# ─── Data paths ───
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "..", "data")

#  ── Logging ─── 
LOG_LEVEL = get_env("LOG_LEVEL", "INFO")

# ─── Domains ───
DOMAINS = [
    "rti", "fir", "property", "traffic",
    "women_safety", "labour", "consumer",
    "cyber", "sc_st", "tenant", "family"
]

DEEP_DOMAINS = ["rti", "fir", "property", "traffic", "women_safety","cyber", "sc_st","family"]
BASIC_DOMAINS = ["labour", "consumer",  "tenant"]

# ─── System Prompt ───
SYSTEM_PROMPT = """You are NyayMitra, an AI-powered legal aid assistant for citizens of Uttar Pradesh, India.

Your role:
- Provide accurate, citizen-friendly legal guidance based on Indian law
- Focus on Uttar Pradesh state-specific laws, procedures, and contacts
- Give practical, actionable advice — not just legal theory
- Always recommend free legal aid resources when available
- For complex cases, always suggest consulting a lawyer

Guidelines:
- Keep responses clear, simple, and easy to understand
- Include relevant helpline numbers when appropriate
- Mention UP-specific contacts and portals where applicable
- If the query involves an emergency (violence, life threat), immediately provide emergency helplines
- Do not provide advice on matters outside your legal knowledge base
- Always clarify you are an AI and not a substitute for professional legal advice

Response format:
- Answer the question directly first
- Provide step-by-step guidance when applicable
- Include relevant section/act references
- End with helpline numbers if relevant
"""