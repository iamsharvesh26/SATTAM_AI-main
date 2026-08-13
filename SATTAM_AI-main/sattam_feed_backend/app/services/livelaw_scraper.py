import os
from dotenv import load_dotenv
load_dotenv()

import asyncio
import httpx
import feedparser
import re
from datetime import datetime, timezone
from bs4 import BeautifulSoup
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "sattam_feed_db")
COLLECTION = "case_feeds"

LEGAL_FEEDS = [
    "https://www.barandbench.com/feed",
    "https://www.barandbench.com/news/feed",
    "https://indiankanoon.org/feeds/",
    "https://indialegallive.com/feed",
]

# ── Rule-based extraction helpers ────────────────────────────────────────────

COURT_PATTERNS = [
    "Supreme Court of India", "Supreme Court",
    "High Court of Delhi", "Delhi High Court",
    "High Court of Bombay", "Bombay High Court",
    "High Court of Madras", "Madras High Court",
    "High Court of Calcutta", "Calcutta High Court",
    "High Court of Karnataka", "Karnataka High Court",
    "High Court of Kerala", "Kerala High Court",
    "High Court of Allahabad", "Allahabad High Court",
    "High Court of Gujarat", "Gujarat High Court",
    "High Court of Telangana", "Telangana High Court",
    "High Court of Andhra Pradesh",
    "National Green Tribunal", "NGT",
    "Sessions Court", "District Court",
    "Consumer Forum", "NCLAT", "NCLT",
]

STATE_PATTERNS = [
    "Delhi", "Maharashtra", "Tamil Nadu", "Karnataka", "Kerala",
    "West Bengal", "Uttar Pradesh", "Gujarat", "Rajasthan",
    "Madhya Pradesh", "Bihar", "Andhra Pradesh", "Telangana",
    "Punjab", "Haryana", "Himachal Pradesh", "Uttarakhand",
    "Jharkhand", "Chhattisgarh", "Odisha", "Assam", "Goa",
]

SECTION_PATTERNS = [
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(IPC|Indian Penal Code)", "IPC"),
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(CrPC|Code of Criminal Procedure)", "CrPC"),
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(BNS|Bharatiya Nyaya Sanhita)", "BNS"),
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(BNSS|Bharatiya Nagarik Suraksha Sanhita)", "BNSS"),
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(PMLA)", "PMLA"),
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(IT Act|Information Technology Act)", "IT Act"),
    (r"Article\s+(\d+[A-Z]?(?:\([\d\w]+\))?)\s+(?:of\s+)?(?:the\s+)?(Constitution)", "Constitution"),
    (r"Section\s+(\d+[A-Z]?)\s+(?:of\s+)?(?:the\s+)?(BSA|Bharatiya Sakshya Adhiniyam)", "BSA"),
]

BNS_BRIDGE_MAP = {
    "IPC": "BNS 2023 replaces IPC; corresponding BNS section may apply.",
    "CrPC": "BNSS 2023 replaces CrPC; corresponding BNSS section may apply.",
}

TYPE_KEYWORDS = {
    "BREAKING": ["breaking", "urgent", "just in", "stay granted", "stays"],
    "LIVE": ["live", "live updates", "live blog", "ongoing hearing"],
    "VERDICT": ["convict", "convicted", "acquit", "acquitted", "sentenced", "verdict"],
    "JUDGMENT": ["judgment", "judgement", "ruled", "held", "dismissed", "upheld", "quashed"],
    "ALERT": ["notice", "notice issued", "suo motu", "contempt", "nhrc", "ncpcr"],
    "ANALYSIS": ["analysis", "opinion", "explainer", "column", "commentary"],
}

TAG_KEYWORDS = [
    "bail", "anticipatory bail", "Supreme Court", "High Court", "Sessions Court",
    "murder", "rape", "fraud", "cheating", "corruption", "PMLA", "ED",
    "CBI", "IT Act", "cyber", "constitution", "Article 21", "property",
    "divorce", "custody", "maintenance", "POCSO", "juvenile", "trademark",
    "copyright", "contempt", "PIL", "writ", "habeas corpus", "sedition",
    "UAPA", "terrorism", "NIA", "demolition", "electoral", "election",
]


def detect_type(title: str, body: str) -> str:
    text = (title + " " + body).lower()
    for case_type, keywords in TYPE_KEYWORDS.items():
        if any(kw.lower() in text for kw in keywords):
            return case_type
    return "JUDGMENT"


def detect_court(text: str) -> str | None:
    for court in COURT_PATTERNS:
        if court.lower() in text.lower():
            return court
    return None


def detect_state(text: str) -> str | None:
    for state in STATE_PATTERNS:
        if state.lower() in text.lower():
            return state
    return None


def detect_case_number(text: str) -> str | None:
    patterns = [
        r"[A-Z]+\s*(?:No\.?|Appeal|Petition|Case)\s*[\w./]+/\d{4}",
        r"(?:WP|SLP|CRL|CRA|MA|OP|PIL|W\.P\.|Crl\.)\s*[.()\w\s]+/\d{4}",
        r"[A-Z]{2,}\s*\(?\w+\)?\s*\d+/\d{4}",
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(0).strip()
    return None


def detect_sections(text: str) -> list[dict]:
    sections = []
    seen = set()
    for pattern, code in SECTION_PATTERNS:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            sec_num = match.group(1)
            key = f"{code}-{sec_num}"
            if key not in seen:
                seen.add(key)
                sections.append({
                    "code": code,
                    "section": f"Sec {sec_num}",
                    "description": f"Section {sec_num} of {code}",
                })
    return sections[:5]


def detect_bns_bridge(sections: list[dict]) -> str | None:
    codes = {s["code"] for s in sections}
    bridges = []
    for code, bridge in BNS_BRIDGE_MAP.items():
        if code in codes:
            bridges.append(bridge)
    return " | ".join(bridges) if bridges else None


def detect_tags(title: str, body: str) -> list[str]:
    text = (title + " " + body).lower()
    found = [tag for tag in TAG_KEYWORDS if tag.lower() in text]
    return found[:6] if found else ["legal", "court", "India"]


def make_summary(title: str, body: str) -> str:
    # Take first 2 sentences from body as summary
    sentences = re.split(r'(?<=[.!?])\s+', body.strip())
    sentences = [s.strip() for s in sentences if len(s.strip()) > 30]
    if sentences:
        return " ".join(sentences[:2])
    return title


# ── Core functions ────────────────────────────────────────────────────────────

async def fetch_article_text(url: str, client: httpx.AsyncClient) -> str:
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; SattamBot/1.0; legal research)"}
        resp = await client.get(url, headers=headers, timeout=15, follow_redirects=True)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "aside", "header", "form"]):
            tag.decompose()
        article = (
            soup.find("div", class_="article-body")
            or soup.find("div", class_="entry-content")
            or soup.find("article")
            or soup.find("main")
        )
        text = article.get_text(separator=" ", strip=True) if article else soup.get_text(separator=" ", strip=True)
        return re.sub(r"\s+", " ", text)[:3000]
    except Exception as e:
        print(f"    ⚠️  Could not fetch body for {url}: {e}")
        return ""


def extract_case(title: str, body: str) -> dict:
    text = title + " " + body
    sections = detect_sections(text)
    return {
        "type": detect_type(title, body),
        "court": detect_court(text),
        "case_number": detect_case_number(text),
        "state": detect_state(text),
        "title": title,
        "summary": make_summary(title, body),
        "sections": sections,
        "bns_bridge": detect_bns_bridge(sections),
        "strategy": None,
        "tags": detect_tags(title, body),
    }


def build_document(extracted: dict, entry: dict, article_url: str) -> dict:
    published_raw = entry.get("published_parsed")
    published_at = (
        datetime(*published_raw[:6], tzinfo=timezone.utc)
        if published_raw
        else datetime.now(timezone.utc)
    )
    return {
        **extracted,
        "source_url": article_url,
        "published_at": published_at,
        "likes": 0,
        "saves": 0,
    }


async def seed_20_cases() -> dict:
    TARGET = 20
    mongo = AsyncIOMotorClient(MONGO_URI)
    db = mongo[DB_NAME]
    collection = db[COLLECTION]

    await collection.create_index(
        [("title", "text"), ("summary", "text"), ("tags", "text")], background=True
    )
    await collection.create_index(
        "source_url", unique=True, background=True,
        partialFilterExpression={"source_url": {"$type": "string"}}
    )

    results = {"inserted": 0, "skipped_duplicates": 0, "failed": 0, "new_cases": []}

    all_entries: list[tuple[dict, str]] = []
    seen_urls: set[str] = set()

    print(f"📡 Collecting articles from {len(LEGAL_FEEDS)} feeds...")
    for feed_url in LEGAL_FEEDS:
        try:
            feed = feedparser.parse(feed_url)
            for entry in feed.entries:
                url = entry.get("link", "").strip()
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    all_entries.append((entry, url))
        except Exception as e:
            print(f"  ⚠️  Feed error {feed_url}: {e}")

    print(f"  → {len(all_entries)} unique articles found")

    async with httpx.AsyncClient() as http_client:
        for entry, article_url in all_entries:
            if results["inserted"] >= TARGET:
                break

            existing = await collection.find_one({"source_url": article_url})
            if existing:
                results["skipped_duplicates"] += 1
                continue

            title = entry.get("title", "")
            print(f"  🔍 [{results['inserted']}/{TARGET}] {title[:65]}")
            await asyncio.sleep(0.3)

            body = await fetch_article_text(article_url, http_client)
            extracted = extract_case(title, body)

            doc = build_document(extracted, entry, article_url)
            try:
                await collection.insert_one(doc)
                results["inserted"] += 1
                results["new_cases"].append({
                    "title": doc["title"],
                    "court": doc["court"],
                    "type": doc["type"],
                    "source_url": article_url,
                    "published_at": doc["published_at"].isoformat(),
                })
                print(f"  ✅ [{results['inserted']}/{TARGET}] [{doc['type']}] {doc['title'][:60]}")
            except Exception as e:
                print(f"  ⚠️  Insert failed: {e}")
                results["failed"] += 1

    mongo.close()
    return results


async def scrape_livelaw() -> dict:
    mongo = AsyncIOMotorClient(MONGO_URI)
    db = mongo[DB_NAME]
    collection = db[COLLECTION]

    results = {"fetched": 0, "skipped_duplicates": 0, "inserted": 0, "failed": 0, "new_cases": []}
    seen_urls: set[str] = set()

    async with httpx.AsyncClient() as http_client:
        for feed_url in LEGAL_FEEDS:
            print(f"📡 Fetching feed: {feed_url}")
            try:
                feed = feedparser.parse(feed_url)
            except Exception as e:
                print(f"  ⚠️  Failed to parse feed {feed_url}: {e}")
                continue

            for entry in feed.entries:
                article_url = entry.get("link", "").strip()
                if not article_url or article_url in seen_urls:
                    continue
                seen_urls.add(article_url)
                results["fetched"] += 1

                existing = await collection.find_one({"source_url": article_url})
                if existing:
                    results["skipped_duplicates"] += 1
                    continue

                print(f"  🔍 {entry.get('title', '')[:70]}")
                await asyncio.sleep(0.3)

                body = await fetch_article_text(article_url, http_client)
                extracted = extract_case(entry.get("title", ""), body)
                doc = build_document(extracted, entry, article_url)

                try:
                    await collection.insert_one(doc)
                    results["inserted"] += 1
                    results["new_cases"].append({"title": doc["title"], "court": doc["court"], "type": doc["type"]})
                    print(f"  ✅ [{doc['type']}] {doc['title'][:60]}")
                except Exception:
                    results["failed"] += 1

    mongo.close()
    return results