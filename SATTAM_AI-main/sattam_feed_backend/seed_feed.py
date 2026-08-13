import asyncio
from motor.motor_asyncio import AsyncIOMotorClient
from datetime import datetime, timezone, timedelta
import random

MONGO_URI = "mongodb://localhost:27017"
DB_NAME = "sattam_feed_db"

CASES = [
    {
        "type": "BREAKING",
        "court": "Supreme Court of India",
        "case_number": "SLP (Crl.) 4521/2024",
        "state": "Delhi",
        "title": "Supreme Court Grants Interim Bail in Money Laundering Case",
        "summary": "The Supreme Court granted interim bail to the accused citing prolonged incarceration without trial completion. The bench observed that personal liberty cannot be indefinitely curtailed and directed release on furnishing surety of ₹5 lakhs.",
        "source_url": None,
        "sections": [
            {"code": "PMLA", "section": "Sec 45", "description": "Bail provisions under PMLA"},
            {"code": "IPC", "section": "Sec 420", "description": "Cheating"},
        ],
        "bns_bridge": "Under BNS 2023: Sec 318 (Cheating) replaces IPC Sec 420",
        "strategy": {
            "bail_likely": True,
            "confidence": 0.82,
            "summary": "High probability of bail given prolonged trial delay and clean antecedents of accused.",
            "sentencing_estimate": "3-5 years if convicted"
        },
        "tags": ["bail", "PMLA", "money laundering", "Supreme Court"],
        "published_at": datetime.now(timezone.utc) - timedelta(hours=2),
        "likes": 142,
        "saves": 89,
    },
    {
        "type": "JUDGMENT",
        "court": "Madras High Court",
        "case_number": "Crl. A. No. 312/2024",
        "state": "Tamil Nadu",
        "title": "Madras HC: Anticipatory Bail Cannot Be Denied Solely on Gravity of Offence",
        "summary": "The Madras High Court held that gravity of offence alone is not sufficient ground to deny anticipatory bail. The court must consider the accused's antecedents, likelihood of fleeing, and threat to witnesses before making a decision.",
        "source_url": None,
        "sections": [
            {"code": "CrPC", "section": "Sec 438", "description": "Anticipatory Bail"},
            {"code": "BNS", "section": "Sec 311", "description": "Anticipatory bail under BNSS"},
        ],
        "bns_bridge": "BNSS 2023 Sec 311 now governs anticipatory bail replacing CrPC Sec 438",
        "strategy": {
            "bail_likely": True,
            "confidence": 0.75,
            "summary": "Favorable precedent for anticipatory bail applications in non-heinous offences.",
            "sentencing_estimate": None
        },
        "tags": ["anticipatory bail", "Madras HC", "BNSS", "CrPC"],
        "published_at": datetime.now(timezone.utc) - timedelta(hours=5),
        "likes": 98,
        "saves": 54,
    },
    {
        "type": "VERDICT",
        "court": "Sessions Court, Chennai",
        "case_number": "S.C. No. 88/2023",
        "state": "Tamil Nadu",
        "title": "Sessions Court Convicts Accused in Cyber Fraud Case — 4 Years Rigorous Imprisonment",
        "summary": "The Sessions Court convicted the accused under IT Act for operating a phishing network targeting senior citizens. The court awarded 4 years RI and ₹2 lakh fine, noting the deliberate targeting of vulnerable persons as an aggravating circumstance.",
        "source_url": None,
        "sections": [
            {"code": "IT Act", "section": "Sec 66C", "description": "Identity theft"},
            {"code": "IT Act", "section": "Sec 66D", "description": "Cheating by personation"},
            {"code": "IPC", "section": "Sec 419", "description": "Cheating by personation"},
        ],
        "bns_bridge": "BNS Sec 319 now covers cheating by personation replacing IPC Sec 419",
        "strategy": {
            "bail_likely": False,
            "confidence": 0.91,
            "summary": "Strong digital evidence and victim testimony led to conviction. Limited grounds for appeal.",
            "sentencing_estimate": "4 years RI (awarded)"
        },
        "tags": ["cyber fraud", "IT Act", "conviction", "phishing"],
        "published_at": datetime.now(timezone.utc) - timedelta(hours=8),
        "likes": 203,
        "saves": 167,
    },
    {
        "type": "ALERT",
        "court": "High Court of Karnataka",
        "case_number": "WP 19234/2024",
        "state": "Karnataka",
        "title": "Karnataka HC Issues Notice to State on Custodial Death — NHRC Involved",
        "summary": "The Karnataka High Court issued notice to the state government following a custodial death in Bengaluru. The NHRC has been impleaded as a party. The court sought action taken report within 4 weeks on alleged police brutality.",
        "source_url": None,
        "sections": [
            {"code": "IPC", "section": "Sec 304", "description": "Culpable homicide not amounting to murder"},
            {"code": "Constitution", "section": "Art 21", "description": "Right to life"},
        ],
        "bns_bridge": "BNS Sec 105 replaces IPC Sec 304 for culpable homicide",
        "strategy": None,
        "tags": ["custodial death", "NHRC", "Karnataka", "police brutality"],
        "published_at": datetime.now(timezone.utc) - timedelta(hours=12),
        "likes": 312,
        "saves": 198,
    },
    {
        "type": "LIVE",
        "court": "Supreme Court of India",
        "case_number": "W.P. (C) 876/2024",
        "state": "Delhi",
        "title": "LIVE: SC Hearing on Electoral Bond Scheme Compliance",
        "summary": "The Supreme Court is currently hearing arguments on compliance with its earlier order directing SBI to submit details of electoral bonds. The bench expressed displeasure over incomplete data submission and warned of contempt proceedings.",
        "source_url": None,
        "sections": [
            {"code": "Constitution", "section": "Art 19(1)(a)", "description": "Freedom of speech"},
            {"code": "Constitution", "section": "Art 32", "description": "Right to constitutional remedies"},
        ],
        "bns_bridge": None,
        "strategy": None,
        "tags": ["electoral bonds", "Supreme Court", "SBI", "contempt"],
        "published_at": datetime.now(timezone.utc) - timedelta(minutes=15),
        "likes": 445,
        "saves": 321,
    },
    {
        "type": "JUDGMENT",
        "court": "Delhi High Court",
        "case_number": "CS (COMM) 234/2024",
        "state": "Delhi",
        "title": "Delhi HC: AI-Generated Content Can Attract Copyright Protection in Certain Cases",
        "summary": "In a landmark ruling, the Delhi High Court held that AI-generated content may attract copyright protection where there is sufficient human creative input in directing the AI. The court distinguished between fully autonomous AI output and human-directed AI assistance.",
        "source_url": None,
        "sections": [
            {"code": "Copyright Act", "section": "Sec 2(d)", "description": "Definition of author"},
            {"code": "Copyright Act", "section": "Sec 13", "description": "Works in which copyright subsists"},
        ],
        "bns_bridge": None,
        "strategy": {
            "bail_likely": None,
            "confidence": None,
            "summary": "Landmark precedent for AI intellectual property law in India. Expected to influence future disputes.",
            "sentencing_estimate": None
        },
        "tags": ["AI", "copyright", "Delhi HC", "intellectual property"],
        "published_at": datetime.now(timezone.utc) - timedelta(hours=1),
        "likes": 567,
        "saves": 412,
    },
    {
        "type": "BREAKING",
        "court": "Supreme Court of India",
        "case_number": "SLP (C) 9981/2024",
        "state": None,
        "title": "SC Stays Demolition of 400 Homes — 'Bulldozer Justice' Under Scanner",
        "summary": "The Supreme Court stayed demolition of 400 homes in a municipal action, observing that due process must be followed before any demolition. The bench said state cannot become prosecutor, judge and executioner simultaneously.",
        "source_url": None,
        "sections": [
            {"code": "Constitution", "section": "Art 21", "description": "Right to life and personal liberty"},
            {"code": "Constitution", "section": "Art 300A", "description": "Right to property"},
        ],
        "bns_bridge": None,
        "strategy": None,
        "tags": ["demolition", "bulldozer", "Article 21", "property rights"],
        "published_at": datetime.now(timezone.utc) - timedelta(minutes=45),
        "likes": 892,
        "saves": 634,
    },
    {
        "type": "ALERT",
        "court": "Bombay High Court",
        "case_number": "PIL 445/2024",
        "state": "Maharashtra",
        "title": "Bombay HC: WhatsApp Messages Admissible as Evidence if Properly Certified",
        "summary": "The Bombay High Court ruled that WhatsApp messages and screenshots are admissible as electronic evidence if accompanied by a certificate under Section 65B of the Indian Evidence Act. The court clarified the procedure for authenticating digital evidence.",
        "source_url": None,
        "sections": [
            {"code": "IEA", "section": "Sec 65B", "description": "Admissibility of electronic records"},
            {"code": "BSA", "section": "Sec 63", "description": "Secondary evidence under BSA 2023"},
        ],
        "bns_bridge": "BSA 2023 Sec 63 now governs electronic evidence replacing IEA Sec 65B",
        "strategy": None,
        "tags": ["WhatsApp", "digital evidence", "65B", "Bombay HC"],
        "published_at": datetime.now(timezone.utc) - timedelta(hours=3),
        "likes": 234,
        "saves": 189,
    },
]


async def seed():
    client = AsyncIOMotorClient(MONGO_URI)
    db = client[DB_NAME]

    existing = await db["case_feeds"].count_documents({})
    if existing > 0:
        print(f"⚠️  Already has {existing} cases. Clearing and re-seeding...")
        await db["case_feeds"].delete_many({})

    # Create text index for search
    await db["case_feeds"].create_index([("title", "text"), ("summary", "text"), ("tags", "text")])
    print("✅ Text index created")

    result = await db["case_feeds"].insert_many(CASES)
    print(f"✅ Inserted {len(result.inserted_ids)} cases into sattam_feed_db")
    client.close()
    print("🌱 Feed seed complete!")


if __name__ == "__main__":
    asyncio.run(seed())