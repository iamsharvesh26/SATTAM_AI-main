from fastapi import APIRouter, HTTPException
from fastapi.responses import PlainTextResponse, Response
from pydantic import BaseModel
from typing import Optional
from app.services.rag_service import generate_answer, explain_legal_term
from app.services.recommendation import generate_recommendations
from app.core.database import chat_sessions
from datetime import datetime
import io
import os
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

router = APIRouter()

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fonts")
_FONTS_DIR = os.path.abspath(_FONTS_DIR)

_REGULAR = "Helvetica"       # fallback if fonts not downloaded
_BOLD    = "Helvetica-Bold"  # fallback

def _try_register(font_name: str, filename: str):
    path = os.path.join(_FONTS_DIR, filename)
    if os.path.exists(path):
        try:
            pdfmetrics.registerFont(TTFont(font_name, path))
            return True
        except Exception:
            pass
    return False

if _try_register("NotoSans",      "NotoSans-Regular.ttf"):
    _REGULAR = "NotoSans"
if _try_register("NotoSans-Bold", "NotoSans-Bold.ttf"):
    _BOLD = "NotoSans-Bold"

# Script-specific fonts (optional — base NotoSans covers most scripts)
for _fn, _ff in [
    ("NotoSansTamil",      "NotoSansTamil-Regular.ttf"),
    ("NotoSansDevanagari", "NotoSansDevanagari-Regular.ttf"),
    ("NotoSansTelugu",     "NotoSansTelugu-Regular.ttf"),
    ("NotoSansMalayalam",  "NotoSansMalayalam-Regular.ttf"),
    ("NotoSansKannada",    "NotoSansKannada-Regular.ttf"),
]:
    _try_register(_fn, _ff)


class ChatRequest(BaseModel):
    user_id: str
    session_id: str
    document_id: Optional[str] = None
    question: str
    language: Optional[str] = "en"


@router.post("/ask")
async def ask(request: ChatRequest):
    try:
        eng_answer, final_answer = generate_answer(
            request.question, request.document_id,
            request.session_id, request.user_id, request.language
        )
        recommendations = []
        if request.document_id and request.document_id not in ("null", "", None):
            recommendations = generate_recommendations(eng_answer, request.language)

        return {"answer": final_answer, "recommended_questions": recommendations}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/history/{session_id}")
async def get_chat_history(session_id: str):
    session = chat_sessions.find_one({"session_id": session_id})
    return {
        "session_id": session_id,
        "history": session.get("history", []) if session else []
    }


@router.get("/sessions/{user_id}")
async def get_all_user_sessions(user_id: str):
    cursor = chat_sessions.find(
        {"user_id": user_id},
        {"session_id": 1, "history": 1, "created_at": 1, "_id": 0}
    )
    sessions = []
    for doc in cursor:
        sid     = doc["session_id"]
        history = doc.get("history", [])
        if history and history[0].get("user"):
            first_q = history[0]["user"]
            title   = first_q[:40] + ("..." if len(first_q) > 40 else "")
        else:
            title = f"Chat — {sid[-6:]}"
        sessions.append({"session_id": sid, "title": title})
    return {"sessions": list(reversed(sessions))}


@router.get("/explain")
async def explain(term: str, language: str = "en", context: str = ""):
    return explain_legal_term(term, language, context or "General legal context")


@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    result = chat_sessions.delete_one({"session_id": session_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    return {"message": "Session deleted"}


# ── EXPORT ─────────────────────────────────────────────────────

@router.get("/export/{session_id}")
async def export_chat_transcript(session_id: str, format: str = "txt"):
    session = chat_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    history = session.get("history", [])
    if format == "pdf":
        return _export_as_pdf(session_id, history)
    return _export_as_txt(session_id, history)


def _export_as_txt(session_id: str, history: list) -> Response:
    lines = [
        "=" * 50,
        "  SATTAM LEGAL AI — CHAT TRANSCRIPT",
        "=" * 50,
        f"  Session : {session_id}",
        f"  Exported: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
        "=" * 50, "",
    ]
    for msg in history:
        if msg.get("user"):
            lines.append(f"You:\n  {msg['user']}")
        if msg.get("ai"):
            lines.append(f"\nSattam AI:\n  {msg['ai']}")
        lines.append("\n" + "-" * 40 + "\n")
    lines.append("  This transcript is for reference only.")
    lines.append("  Please consult a qualified lawyer for legal advice.")

    content_bytes = "\n".join(lines).encode("utf-8")
    return Response(
        content=content_bytes,
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="Sattam_Chat_{session_id[-6:]}.txt"',
            "Content-Type": "text/plain; charset=utf-8",
        },
    )


def _export_as_pdf(session_id: str, history: list) -> Response:
    try:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            rightMargin=20*mm, leftMargin=20*mm,
            topMargin=20*mm,  bottomMargin=20*mm,
        )

        title_style = ParagraphStyle("Title",
            fontSize=16, fontName=_BOLD,
            textColor=colors.HexColor("#1A3C5E"), spaceAfter=4)

        meta_style = ParagraphStyle("Meta",
            fontSize=9, fontName=_REGULAR,
            textColor=colors.grey, spaceAfter=12)

        user_label = ParagraphStyle("UserLabel",
            fontSize=10, fontName=_BOLD,
            textColor=colors.HexColor("#1A3C5E"),
            spaceBefore=10, spaceAfter=3)

        user_style = ParagraphStyle("UserMsg",
            fontSize=11, fontName=_REGULAR,       # Noto here = Tamil renders
            backColor=colors.HexColor("#E6F1FB"),
            leftIndent=10, rightIndent=10,
            spaceAfter=6, leading=18, borderPad=6) # leading=18 for Indic scripts

        ai_label = ParagraphStyle("AILabel",
            fontSize=10, fontName=_BOLD,
            textColor=colors.HexColor("#0F6E56"),
            spaceBefore=6, spaceAfter=3)

        ai_style = ParagraphStyle("AIMsg",
            fontSize=11, fontName=_REGULAR,        # Noto here = Tamil renders
            backColor=colors.HexColor("#F1FFF8"),
            leftIndent=10, rightIndent=10,
            spaceAfter=6, leading=18, borderPad=6) # leading=18 for Indic scripts

        warning_style = ParagraphStyle("Warning",
            fontSize=9, fontName=_REGULAR,
            textColor=colors.HexColor("#854F0B"), spaceBefore=16)

        story = [
            Paragraph("Sattam Legal AI", title_style),
            Paragraph("Chat Transcript", title_style),
            Paragraph(
                f"Session: {session_id[-12:]}   "
                f"Exported: {datetime.now().strftime('%d %b %Y, %I:%M %p')}",
                meta_style,
            ),
            HRFlowable(width="100%", thickness=0.5,
                       color=colors.HexColor("#1A3C5E")),
            Spacer(1, 10),
        ]

        def safe(text: str) -> str:
            return (text or "").replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

        def _font_for(text: str) -> str:
            """
            Detect script from Unicode ranges and return the best
            registered Noto font for that script. Falls back to _REGULAR.
            Each Indic script has its own Unicode block — checking the
            first non-ASCII character is enough to identify the script.
            """
            for ch in (text or ""):
                cp = ord(ch)
                if 0x0B80 <= cp <= 0x0BFF:   # Tamil
                    return "NotoSansTamil" if "NotoSansTamil" in pdfmetrics.getRegisteredFontNames() else _REGULAR
                if 0x0900 <= cp <= 0x097F:   # Hindi / Devanagari
                    return "NotoSansDevanagari" if "NotoSansDevanagari" in pdfmetrics.getRegisteredFontNames() else _REGULAR
                if 0x0C00 <= cp <= 0x0C7F:   # Telugu
                    return "NotoSansTelugu" if "NotoSansTelugu" in pdfmetrics.getRegisteredFontNames() else _REGULAR
                if 0x0D00 <= cp <= 0x0D7F:   # Malayalam
                    return "NotoSansMalayalam" if "NotoSansMalayalam" in pdfmetrics.getRegisteredFontNames() else _REGULAR
                if 0x0C80 <= cp <= 0x0CFF:   # Kannada
                    return "NotoSansKannada" if "NotoSansKannada" in pdfmetrics.getRegisteredFontNames() else _REGULAR
            return _REGULAR  # English / Latin

        for msg in history:
            if msg.get("user"):
                text = msg["user"]
                # Pick font based on detected script of this specific message
                msg_style = ParagraphStyle(
                    f"UserMsg_{id(text)}",
                    parent=user_style,
                    fontName=_font_for(text),
                )
                story.append(Paragraph("You", user_label))
                story.append(Paragraph(safe(text), msg_style))

            if msg.get("ai"):
                text = msg["ai"]
                msg_style = ParagraphStyle(
                    f"AIMsg_{id(text)}",
                    parent=ai_style,
                    fontName=_font_for(text),
                )
                story.append(Paragraph("Sattam AI", ai_label))
                story.append(Paragraph(safe(text), msg_style))
                story.append(Spacer(1, 4))

        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.grey))
        story.append(Paragraph(
            "This transcript is for reference only. "
            "Please consult a qualified lawyer for legal advice.",
            warning_style,
        ))

        doc.build(story)
        return Response(
            content=buf.getvalue(),
            media_type="application/pdf",
            headers={
                "Content-Disposition":
                    f'attachment; filename="Sattam_Chat_{session_id[-6:]}.pdf"',
            },
        )

    except Exception as e:
        print(f"PDF export error: {e}")
        return _export_as_txt(session_id, history)