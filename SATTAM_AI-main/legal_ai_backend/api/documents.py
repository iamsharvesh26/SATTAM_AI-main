from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from app.services.document_service import process_and_upload_document

router = APIRouter()

@router.post("/upload")
async def upload_document(
    file:       UploadFile = File(...),
    user_id:    str        = Form(...),
    session_id: str        = Form(...),
    language:   str        = Form(default="en"),
):
    print(f">>> documents.py received language={language}")
    try:
        result = await process_and_upload_document(file, user_id, session_id, language)

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {
            "status":                "success",
            "document_id":           result["document_id"],
            "filename":              result["filename"],
            "document_type":         result.get("document_type", "Legal Document"),
            "num_pages":             result.get("num_pages", 1),
            "summary":               result["summary"],
            "parties":               result["parties_involved"],
            "key_dates":             result["important_dates"],
            "obligations":           result["key_obligations"],
            "extracted_clauses":     result["extracted_clauses"],
            "recommended_questions": result.get("questions", []),
        }

    except Exception as e:
        print(f"Upload Router Error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error during document processing.")