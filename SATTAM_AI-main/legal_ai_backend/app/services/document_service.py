import fitz
import json
import re
import os
import uuid
import io
import docx
from PIL import Image
import pytesseract
from sentence_transformers import SentenceTransformer
from pinecone import Pinecone
from app.core.database import documents_meta
from langchain_openai import ChatOpenAI
from deep_translator import GoogleTranslator
from dotenv import load_dotenv

load_dotenv()

pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

pc       = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
index    = pc.Index(os.getenv("PINECONE_INDEX_NAME", "sattam-law"))
embedder = SentenceTransformer('intfloat/multilingual-e5-large')

chat_llm = ChatOpenAI(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    max_tokens=2000,
    temperature=0.1,
)

NS_USER_PREFIX = "user_"

def user_namespace(user_id: str) -> str:
    return f"{NS_USER_PREFIX}{user_id}"


def get_smart_chunks(text, max_words=200):
    words = text.split()
    chunks = []
    for i in range(0, len(words), max_words - 20):
        chunk = " ".join(words[i:i + max_words])
        if len(chunk.strip()) > 20:
            chunks.append(chunk)
    return chunks


def _detect_doc_language(text: str) -> str:
    """Detect document language from Unicode character ranges."""
    sample = text[:300]
    checks = [
        ("ta", 0x0B80, 0x0BFF),
        ("hi", 0x0900, 0x097F),
        ("te", 0x0C00, 0x0C7F),
        ("ml", 0x0D00, 0x0D7F),
        ("kn", 0x0C80, 0x0CFF),
    ]
    for lang_code, start, end in checks:
        if any(start <= ord(c) <= end for c in sample):
            return lang_code
    return "en"


def _translate_en_to(text: str, target_lang: str) -> str:
    """Translate English text to target language. Returns original on failure."""
    if not text or target_lang == "en":
        return text
    try:
        if len(text) > 4500:
            mid = text[:4500].rfind(". ")
            mid = mid if mid != -1 else 4500
            return (_translate_en_to(text[:mid + 1], target_lang)
                    + " "
                    + _translate_en_to(text[mid + 1:], target_lang))
        result = GoogleTranslator(source="en", target=target_lang).translate(text)
        return result or text
    except Exception as e:
        print(f"Translation error (en→{target_lang}): {e}")
        return text


def _translate_list(items: list, target_lang: str) -> list:
    if target_lang == "en":
        return items
    return [_translate_en_to(item, target_lang) for item in items if item]


def _translate_clauses(clauses: list, target_lang: str) -> list:
    if target_lang == "en":
        return clauses
    return [
        {
            "heading": _translate_en_to(c.get("heading", ""), target_lang),
            "body":    _translate_en_to(c.get("body", ""), target_lang),
        }
        for c in clauses
    ]


async def process_and_upload_document(
    file,
    user_id:    str,
    session_id: str,
    language:   str = "en",     # user's chosen UI language
):
    print(f">>> process_and_upload_document called — language={language}")

    contents  = await file.read()
    filename  = file.filename.lower()
    text      = ""
    num_pages = 1

    # ── Step 1: Extract text ──────────────────────────────────
    try:
        if filename.endswith(".pdf"):
            pdf = fitz.open(stream=contents, filetype="pdf")
            num_pages = len(pdf)
            pages_text = []
            for page in pdf:
                page_text = page.get_text()
                if len(page_text.strip()) > 30:
                    pages_text.append(page_text)
                else:
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                    img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
                    try:
                        pages_text.append(
                            pytesseract.image_to_string(img, lang="eng+tam+hin+mal+tel+kan")
                        )
                    except pytesseract.TesseractError:
                        pages_text.append(pytesseract.image_to_string(img, lang="eng"))
            text = " ".join(pages_text)

        elif filename.endswith(".docx"):
            doc  = docx.Document(io.BytesIO(contents))
            text = "\n".join([p.text for p in doc.paragraphs if p.text.strip()])

        elif filename.endswith((".png", ".jpg", ".jpeg")):
            image = Image.open(io.BytesIO(contents))
            try:
                text = pytesseract.image_to_string(image, lang="eng+tam+hin+mal+tel+kan")
            except pytesseract.TesseractError:
                text = pytesseract.image_to_string(image, lang="eng")
        else:
            return {"error": "Unsupported file type. Use PDF, DOCX, or image."}

        if not text.strip():
            return {"error": "No readable text found in this document."}

    except Exception as e:
        return {"error": f"Failed to read file: {str(e)}"}

    # ── Step 2: Detect document language ─────────────────────
    doc_language = _detect_doc_language(text)
    print(f">>> Detected document language: {doc_language}")

    # ── Step 3: Embed ORIGINAL text into Pinecone ─────────────
    chunks  = get_smart_chunks(text)
    doc_id  = str(uuid.uuid4())
    vectors = []

    for i, chunk in enumerate(chunks):
        vector = embedder.encode(f"passage: {chunk}").tolist()
        vectors.append({
            "id":     f"{doc_id}_chunk_{i}",
            "values": vector,
            "metadata": {
                "type":        "user_doc",
                "document_id": doc_id,
                "user_id":     user_id,
                "language":    doc_language,
                "text":        chunk,
            },
        })

    for i in range(0, len(vectors), 100):
        index.upsert(vectors=vectors[i:i + 100], namespace=user_namespace(user_id))

    # ── Step 4: Prepare English text for LLaMA ───────────────
    # IMPORTANT: We send the RAW Tamil/Malayalam text to LLaMA directly.
    # Do NOT translate to English first — translation corrupts Tamil names
    # (e.g. "Rajesh Kumar" becomes "Wo Kagayolar").
    # LLaMA 3.1 can read Tamil text and extract structured info from it.
    # We only tell it to RETURN the JSON values in English.
    preview_text = text[:4000]

    # ── Step 5: LLaMA analysis ────────────────────────────────
    prompt = f"""You are a helpful Indian legal assistant. Analyze this legal document.
The document text may be in Tamil, Hindi, Malayalam or another Indian language.
Read it carefully and extract the information.

Document text:
{preview_text}

Return ONLY a valid JSON object. All values must be in ENGLISH:
{{
    "document_type": "e.g. Rental Agreement, Court Order, Employment Contract",
    "summary": "3-sentence simplified summary in plain English",
    "parties_involved": ["Full name of party 1", "Full name of party 2"],
    "important_dates": ["Date 1", "Date 2"],
    "key_obligations": ["Obligation 1 in English", "Obligation 2 in English"],
    "extracted_clauses": [{{"heading": "Clause name in English", "body": "Clause content in English"}}],
    "questions": ["Question 1 in English?", "Question 2 in English?", "Question 3 in English?"]
}}"""

    try:
        response   = chat_llm.invoke(prompt)
        json_match = re.search(r'\{.*\}', response.content, re.DOTALL)
        ai_data    = json.loads(json_match.group(0)) if json_match else {}
        print(f">>> AI analysis complete. Keys: {list(ai_data.keys())}")
    except Exception as e:
        print(f">>> AI analysis error: {e}")
        ai_data = {}

    # ── Step 6: Translate English fields to user's language ───
    # Now we have clean English output from LLaMA.
    # Translate to the user's chosen language.
    print(f">>> Translating to user language: {language}")

    if language != "en":
        summary           = _translate_en_to(ai_data.get("summary", ""), language)
        document_type     = _translate_en_to(ai_data.get("document_type", "Legal Document"), language)
        parties_involved  = ai_data.get("parties_involved", [])  # names stay in English/original
        important_dates   = ai_data.get("important_dates", [])   # dates are universal
        key_obligations   = _translate_list(ai_data.get("key_obligations", []), language)
        extracted_clauses = _translate_clauses(ai_data.get("extracted_clauses", []), language)
        questions         = _translate_list(
            ai_data.get("questions", ["Explain this document", "What are my rights?"]),
            language,
        )
    else:
        summary           = ai_data.get("summary", "No summary available.")
        document_type     = ai_data.get("document_type", "Legal Document")
        parties_involved  = ai_data.get("parties_involved", [])
        important_dates   = ai_data.get("important_dates", [])
        key_obligations   = ai_data.get("key_obligations", [])
        extracted_clauses = ai_data.get("extracted_clauses", [])
        questions         = ai_data.get("questions", ["Explain this document", "What are my rights?"])

    print(f">>> Translation complete. Summary preview: {summary[:80]}")

    # ── Step 7: Save to MongoDB ───────────────────────────────
    doc_metadata = {
        "document_id":           doc_id,
        "user_id":               user_id,
        "session_id":            session_id,
        "filename":              filename,
        "num_pages":             num_pages,
        "doc_language":          doc_language,
        "user_language":         language,
        "pinecone_namespace":    user_namespace(user_id),
        "document_type":         document_type,
        "summary":               summary,
        "parties_involved":      parties_involved,
        "important_dates":       important_dates,
        "key_obligations":       key_obligations,
        "extracted_clauses":     extracted_clauses,
        "questions":             questions,
        # English originals stored for future re-use
        "summary_en":            ai_data.get("summary", ""),
        "key_obligations_en":    ai_data.get("key_obligations", []),
        "extracted_clauses_en":  ai_data.get("extracted_clauses", []),
        "questions_en":          ai_data.get("questions", []),
    }
    documents_meta.insert_one(doc_metadata.copy())

    return doc_metadata