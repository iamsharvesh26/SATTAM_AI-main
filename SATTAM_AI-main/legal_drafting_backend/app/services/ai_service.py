import json
import re
from typing import Dict, Any, List, Optional, Tuple
from groq import Groq
from app.core.config import settings

client = Groq(api_key=settings.GROQ_API_KEY)
DEFAULT_MODEL = "llama-3.3-70b-versatile"

def call_ai(messages: List[Dict], system: Optional[str] = None, max_tokens: int = 2000) -> str:
    """Unified AI call using Together AI."""
    all_messages = []
    if system:
        all_messages.append({"role": "system", "content": system})
    all_messages.extend(messages)
    response = client.chat.completions.create(
        model=DEFAULT_MODEL,
        messages=all_messages,
        max_tokens=max_tokens,
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


# ─── Document Simplification ──────────────────────────────────────────────────

async def simplify_legal_document(text: str, language: str = "english") -> Dict[str, Any]:
    """Simplify legal document text into plain language."""

    prompt = f"""You are a legal document simplifier for Indian law. Analyze the following legal document/text and provide a structured response in JSON format ONLY (no markdown, no extra text).

Legal text:
{text}

Respond with this exact JSON structure:
{{
  "simplified_text": "Plain English summary of the entire document in simple language that a layperson can understand. Be thorough but clear.",
  "key_highlights": ["highlight 1", "highlight 2", "highlight 3", "...up to 8 key points"],
  "legal_terms_explained": {{
    "legal term 1": "plain explanation",
    "legal term 2": "plain explanation"
  }},
  "risk_flags": ["potential risk or issue 1", "potential risk or issue 2"]
}}"""

    raw = call_ai(
        messages=[{"role": "user", "content": prompt}],
        system="You are a legal document simplifier. Always respond with valid JSON only.",
        max_tokens=2000,
    )
    raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {
            "simplified_text": raw,
            "key_highlights": [],
            "legal_terms_explained": {},
            "risk_flags": [],
        }


# ─── Document Generation ──────────────────────────────────────────────────────

async def generate_document_from_data(
    document_type: str,
    filled_data: Dict[str, Any],
    template_body: Optional[str] = None,
    additional_instructions: Optional[str] = None,
    jurisdiction: str = "india",
) -> str:
    """Generate a legal document from filled fields."""

    if template_body:
        # Fill template placeholders
        content = template_body
        for key, value in filled_data.items():
            content = content.replace(f"{{{{{key}}}}}", str(value) if value else f"[{key.upper()}]")

        # Ask AI to refine/complete
        prompt = f"""You are an Indian legal document drafting expert. Below is a partially filled legal document template. 
Complete any missing sections, ensure legal language is proper, and make it ready for use under Indian law.

Document Type: {document_type}
Jurisdiction: {jurisdiction}

Current Draft:
{content}

Additional instructions: {additional_instructions or 'None'}

Rules:
1. Keep the original structure but improve legal language
2. Fill any [PLACEHOLDER] with appropriate generic text
3. Return ONLY the final document text, no explanations
4. Ensure compliance with Indian laws"""

    else:
        # Generate from scratch
        data_str = "\n".join([f"- {k}: {v}" for k, v in filled_data.items() if v])
        prompt = f"""You are an expert Indian legal document drafter. Draft a professional {document_type} document based on the following information.

Jurisdiction: {jurisdiction}
Provided Information:
{data_str}

Additional instructions: {additional_instructions or 'None'}

Rules:
1. Use proper legal language and structure
2. Ensure compliance with Indian laws and {jurisdiction} specific laws
3. Include all standard clauses for this document type
4. Return ONLY the final document text, properly formatted"""

    return call_ai(
        messages=[{"role": "user", "content": prompt}],
        system="You are an expert Indian legal document drafter. Return only the document text.",
        max_tokens=3000,
    )


# ─── Chatbot Drafting ─────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an AI Legal Assistant specializing in Indian law. You help users draft legal documents through conversation.

Your capabilities:
- Draft legal agreements, notices, affidavits, petitions
- Ask clarifying questions to gather required information
- Suggest appropriate clauses
- Identify missing or risky information
- Generate personalized legal documents

Communication style:
- Be friendly and professional
- Use simple language, avoid jargon
- Ask one or two questions at a time
- When you have enough info, generate the document

When generating a document, wrap it in <DOCUMENT_START> and <DOCUMENT_END> tags.
When asking for more info, list missing fields as <MISSING_FIELDS>field1,field2</MISSING_FIELDS>.
When you have a draft ready, include <ACTION>generate_draft</ACTION>.
When document is finalized, include <ACTION>finalize</ACTION>."""


async def chat_with_legal_ai(
    messages: List[Dict[str, str]],
    user_profile: Optional[Dict] = None,
) -> Tuple[str, Optional[str], Optional[List[str]], Optional[str]]:
    """
    Process chat message and return (response_text, document_draft, missing_fields, action)
    """

    system = SYSTEM_PROMPT
    if user_profile:
        system += f"\n\nUser profile: Name={user_profile.get('name', 'N/A')}, Location={user_profile.get('address', 'N/A')}"

    text = call_ai(messages=messages, system=system, max_tokens=2000)

    # Extract document draft
    document_draft = None
    doc_match = re.search(r"<DOCUMENT_START>(.*?)<DOCUMENT_END>", text, re.DOTALL)
    if doc_match:
        document_draft = doc_match.group(1).strip()
        text = text.replace(doc_match.group(0), "[Document generated above]").strip()

    # Extract missing fields
    missing_fields = None
    missing_match = re.search(r"<MISSING_FIELDS>(.*?)</MISSING_FIELDS>", text)
    if missing_match:
        missing_fields = [f.strip() for f in missing_match.group(1).split(",")]
        text = text.replace(missing_match.group(0), "").strip()

    # Extract action
    action = None
    action_match = re.search(r"<ACTION>(.*?)</ACTION>", text)
    if action_match:
        action = action_match.group(1).strip()
        text = text.replace(action_match.group(0), "").strip()

    return text, document_draft, missing_fields, action


# ─── Risk Check ───────────────────────────────────────────────────────────────

async def check_document_risks(content: str) -> List[str]:
    """Identify potential risks or missing elements in a draft document."""

    prompt = f"""Review this legal document draft and identify potential risks, missing clauses, or issues.
Return a JSON array of strings, each describing one risk or issue. Maximum 8 items.
Return ONLY the JSON array, no other text.

Document:
{content[:3000]}"""

    raw = call_ai(
        messages=[{"role": "user", "content": prompt}],
        system="You are a legal risk analyst. Return only a JSON array.",
        max_tokens=500,
    )
    raw = re.sub(r"^```json\s*|^```\s*|\s*```$", "", raw, flags=re.MULTILINE).strip()

    try:
        return json.loads(raw)
    except Exception:
        return ["Unable to perform risk analysis. Please review manually."]
