import re

DEVANAGARI = re.compile(r'[\u0900-\u097F]')

HINGLISH_MARKERS = set([
    "kaise", "kya", "kab", "kyun", "kyunki", "kaun", "kitna", "kitni",
    "mera", "meri", "mujhe", "mere", "hamara", "hamari", "tumhara",'hogyi','hogya'
    "aapka", "aapki", "unka", "uska", "iski", "iska",
    "karein", "karo", "karoon", "kar", "karna", "karte", "karti",
    "dena", "diya", "de", "dedo", "milega", "milegi", "milta",
    "batao", "bata", "samjhao", "samjha", "chahiye", "chahie",
    "chahta", "chahti", "lagta", "lagti", "hoga", "hogi",
    "nahi", "nhi", "nai", "mat", "na",
    "hai", "hain", "tha", "thi", "ho", "hoon",
    "aur", "ya", "lekin", "toh", "tou", "agar", "jab", "tab",
    "isliye", "phir", "bhi",
    "mein", "se", "ke", "ki", "ko", "pe", "par", "tak", "liye",
    "pati", "patni", "ghar", "paisa", "paise", "zameen", "makaan",
    "adhikar", "haq", "kanoon", "samasya", "madad",
    "bachao", "wapas", "jaldi", "abhi", "plz",
    "vakeel", "adalat", "thana", "shikayat",
])

DOMAIN_KEYWORDS = {
    "rti": [
        "rti", "right to information", "soochna ka adhikar", "soochna adhikar",
        "soochna", "pio", "public information", "jan soochna",
        "cic", "sic", "information commissioner", "ration nahi mila",
        "sarkari document", "government record",
    ],
    "fir": [
        "fir", "police complaint", "police station", "thana", "report",
        "complaint", "arrest", "zero fir", "magistrate complaint",
        "cognizable", "chori", "theft", "dacoity", "assault",
        "maar peet", "police nahi sun rahi", "fir nahi likh rahi",
        "sp complaint", "156(3)", "anticipatory bail", "bail",
        "crime", "offense", "ipc", "crpc", "chargesheet",
    ],
    "property": [
        "property", "zameen", "land", "bhumi", "plot", "makaan", "house",
        "khatauni", "khasra", "bhulekh", "registry", "mutation",
        "dakhil kharij", "encroachment", "rera", "builder complaint",
        "patwari", "lekhpal", "tehsildar", "land dispute", "zameen vivad",
        "benami", "revenue", "jamabandi",
    ],
    "traffic": [
        "traffic", "challan", "fine", "driving license", "dl", "vehicle",
        "motor vehicle", "speed", "helmet", "seatbelt", "drunk driving",
        "parivahan", "echallan", "registration", "rc", "insurance",
        "seized vehicle", "impound", "galat challan", "wrong challan",
    ],
    "women_safety": [
        "domestic violence", "ghar mein maar", "pati maar raha",
        "dv act", "protection order", "dowry", "dahej", "498a",
        "mahila", "women", "aurat", "ladki", "rape", "sexual assault",
        "molestation", "pocso", "child abuse", "workplace harassment",
        "posh", "1090", "mahila helpline", "one stop centre", "sakhi",
        "stalking", "husband maar raha", "sasural mein",
    ],
    "labour": [
        "labour", "salary", "wages", "minimum wage", "pf", "provident fund",
        "esic", "gratuity", "mazdoor", "worker", "employee", "employer",
        "salary nahi mili", "paisa nahi diya", "labour court",
        "industrial dispute", "termination", "dismissal", "bonus",
    ],
    "consumer": [
        "consumer", "product defect", "service", "refund", "online fraud",
        "e-commerce", "amazon", "flipkart", "cheating", "fraud",
        "deficiency", "consumer forum", "district commission", "ncdrc",
        "warranty", "guarantee", "paisa wapas nahi", "product kharab",
    ],
    "cyber": [
        "cyber", "online fraud", "internet", "hacking", "phishing",
        "social media", "facebook", "whatsapp", "instagram", "cyber crime",
        "cyber cell", "otp fraud", "bank fraud", "upi fraud",
        "cybercrime.gov.in", "digital arrest", "blackmail online",
        "photo viral", "fake account", "identity theft", "ransom",
    ],
    "sc_st": [
        "sc", "st", "dalit", "adivasi", "scheduled caste", "scheduled tribe",
        "atrocity", "atrocities", "caste discrimination", "untouchability",
        "jati", "chamar", "valmiki", "pasi", "sc st act",
        "social boycott", "caste abuse", "manual scavenging",
        "14566", "nhaa", "jati ke naam pe gaali",
    ],
    "tenant": [
        "tenant", "landlord", "rent", "kiraya", "kirayedar", "makan malik",
        "eviction", "bedhakli", "lease", "rental agreement", "security deposit",
        "zamaanat", "notice", "rent court", "makaan", "flat",
        "deposit wapas nahi", "ghar khali karo", "bina notice ke",
        "bijli band kar di", "paani band kar diya", "rent increase",
    ],
    "family": [
        "divorce", "talaq", "separation", "alimony", "maintenance",
        "child custody", "custody", "marriage", "shaadi", "vivah",
        "matrimonial", "hindu marriage", "muslim marriage",
        "cruelty", "mental cruelty", "desertion", "succession",
        "inheritance", "will",
    ],
}

EMERGENCY_KEYWORDS = [
    "maar pit", "maar raha hai", "maar diya", "bachao", "help me",
    "kidnapping", "utha liya", "rape", "jabardasti",
    "jaan ka khatra", "jaan se marna", "khoon", "hatya", "murder",
    "aag lagi", "jalaya", "accident", "pistol", "chaku",
    "emergency", "danger", "khatra", "ghar mein ghus aaye",
    "dhamki de raha", "loot", "dacoity", "maar dega", "jaan lega",
]


def detect_language(text: str) -> str:
    if DEVANAGARI.search(text):
        return "hindi"
    words = re.findall(r'\b\w+\b', text.lower())
    hinglish_count = sum(1 for w in words if w in HINGLISH_MARKERS)
    if hinglish_count >= 2:
        return "hindi"
    return "english"


def detect_emergency(text: str) -> bool:
    text_lower = text.lower()
    return any(kw in text_lower for kw in EMERGENCY_KEYWORDS)


def detect_domain(text: str) -> str:
    text_lower = text.lower()
    domain_scores = {}
    for domain, keywords in DOMAIN_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            domain_scores[domain] = score
    if not domain_scores:
        return "general"
    return max(domain_scores, key=domain_scores.get)


def detect_intent(text: str) -> str:
    text_lower = text.lower()
    if any(w in text_lower for w in ["helpline", "number", "phone", "contact", "call", "nambar"]):
        return "helpline_request"
    if any(w in text_lower for w in ["template", "draft", "letter", "application", "likhna", "likho", "format"]):
        return "template_request"
    if any(w in text_lower for w in ["kaise", "how", "process", "steps", "procedure", "file", "tarika"]):
        return "process_query"
    if any(w in text_lower for w in ["kya hai", "what is", "explain", "batao", "samjhao", "matlab"]):
        return "information_query"
    if any(w in text_lower for w in ["rights", "adhikar", "haq", "entitled"]):
        return "rights_query"
    return "general_query"


def analyze_query(text: str) -> dict:
    return {
        "language":     detect_language(text),
        "domain":       detect_domain(text),
        "intent":       detect_intent(text),
        "is_emergency": detect_emergency(text),
    }