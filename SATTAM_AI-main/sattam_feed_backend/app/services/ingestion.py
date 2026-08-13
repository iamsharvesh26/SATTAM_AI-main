import feedparser
import httpx
from bs4 import BeautifulSoup
from datetime import datetime
from app.database import get_db

# ── RSS Feed URLs ──────────────────────────────────────────────
FEEDS = [
    {"url": "https://www.livelaw.in/feed/", "source": "LiveLaw"},
    {"url": "https://www.barandbench.com/feed", "source": "Bar and Bench"},
    {"url": "https://lawbeat.in/feed", "source": "LawBeat"},
]

# ── Detect Feed Type ───────────────────────────────────────────
def detect_type(title: str) -> str:
    title = title.lower()
    if any(w in title for w in ["breaking", "urgent", "just in"]):
        return "BREAKING"
    elif any(w in title for w in ["live", "hearing", "ongoing"]):
        return "LIVE"
    elif any(w in title for w in ["verdict", "convicted", "acquitted"]):
        return "VERDICT"
    elif any(w in title for w in ["judgment", "judgement", "ruled", "upheld", "dismissed"]):
        return "JUDGMENT"
    else:
        return "ALERT"

# ── Detect Court ───────────────────────────────────────────────
def detect_court(title: str) -> str:
    title = title.lower()
    if "supreme court" in title:
        return "Supreme Court of India"
    elif "high court" in title:
        # Try to detect which high court
        courts = ["madras", "bombay", "delhi", "calcutta", "kerala",
                  "allahabad", "gujarat", "karnataka", "telangana"]
        for c in courts:
            if c in title:
                return f"{c.title()} High Court"
        return "High Court"
    elif "ngt" in title or "green tribunal" in title:
        return "National Green Tribunal"
    elif "nclt" in title:
        return "NCLT"
    elif "sessions" in title:
        return "Sessions Court"
    else:
        return "Indian Court"

# ── Detect State ───────────────────────────────────────────────
def detect_state(title: str) -> str:
    states = {
        "tamil nadu": "Tamil Nadu", "madras": "Tamil Nadu",
        "delhi": "Delhi", "mumbai": "Maharashtra",
        "bombay": "Maharashtra", "kerala": "Kerala",
        "karnataka": "Karnataka", "bengaluru": "Karnataka",
        "gujarat": "Gujarat", "rajasthan": "Rajasthan",
        "punjab": "Punjab", "haryana": "Haryana",
        "telangana": "Telangana", "hyderabad": "Telangana",
        "allahabad": "Uttar Pradesh", "lucknow": "Uttar Pradesh",
    }
    title_lower = title.lower()
    for key, value in states.items():
        if key in title_lower:
            return value
    return None

# ── Extract Tags ───────────────────────────────────────────────
def extract_tags(title: str) -> list:
    keywords = [
        "bail", "murder", "rape", "pocso", "fraud", "corruption",
        "privacy", "aadhaar", "sedition", "ngt", "environment",
        "supreme court", "high court", "bnss", "bns", "ipc",
        "divorce", "property", "tax", "cyber", "terror",
        "custody", "cheque", "arbitration", "contempt", "fir",
        "anticipatory bail", "habeas corpus", "pil",
    ]
    found = []
    for kw in keywords:
        if kw in title.lower():
            found.append(kw.title())
    return found if found else ["Legal", "India"]

# ── Clean HTML ─────────────────────────────────────────────────
def clean_html(raw: str) -> str:
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(separator=" ")
    return " ".join(text.split())[:600]

# ── Main Ingestion Function ────────────────────────────────────
async def fetch_and_store_cases():
    db = get_db()
    if db is None:
        print("❌ DB not connected")
        return

    new_count = 0

    for feed_info in FEEDS:
        try:
            print(f"📡 Fetching from {feed_info['source']}...")
            feed = feedparser.parse(feed_info["url"])

            for entry in feed.entries[:15]:  # 15 per source = 45 total
                # Skip duplicates
                existing = await db["case_feeds"].find_one(
                    {"source_url": entry.get("link", "")}
                )
                if existing:
                    continue

                title = entry.get("title", "Untitled")
                raw_summary = entry.get("summary", "")
                summary = clean_html(raw_summary)

                # Parse date
                try:
                    published_at = datetime(*entry.published_parsed[:6])
                except Exception:
                    published_at = datetime.utcnow()

                case = {
                    "type": detect_type(title),
                    "court": detect_court(title),
                    "court_level": "Other",
                    "case_number": f"AUTO/{published_at.year}/{new_count+1}",
                    "state": detect_state(title),
                    "title": title,
                    "summary": summary if summary else title,
                    "full_text": None,
                    "source_url": entry.get("link", ""),
                    "sections": [],
                    "bns_bridge": None,
                    "strategy": None,
                    "tags": extract_tags(title),
                    "published_at": published_at,
                    "hearing_date": None,
                    "likes": 0,
                    "saves": 0,
                }

                await db["case_feeds"].insert_one(case)
                new_count += 1
                print(f"  ✅ {title[:70]}")

        except Exception as e:
            print(f"❌ Error fetching {feed_info['source']}: {e}")

    print(f"\n🎉 Done — {new_count} new real cases added to MongoDB!")