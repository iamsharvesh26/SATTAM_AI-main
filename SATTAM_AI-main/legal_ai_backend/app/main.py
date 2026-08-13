from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.rag_chain import get_legal_rag_chain

app = FastAPI(
    title="SATTAM AI - Legal RAG API",
    description="Backend API providing Retrieval-Augmented Generation for Indian Law.",
    version="1.0.0"
)

# Enable CORS for all origins (Required for HTML files opened locally)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize RAG Chain
rag_chain = get_legal_rag_chain()

class LegalQueryRequest(BaseModel):
    question: str

class SourceDocument(BaseModel):
    content: str
    metadata: dict

class LegalQueryResponse(BaseModel):
    answer: str
    sources: list[SourceDocument]

@app.get("/")
def home():
    return {"message": "SATTAM AI Legal RAG Engine is running."}

@app.post("/api/v1/chat", response_model=LegalQueryResponse)
async def query_legal_rag(payload: LegalQueryRequest):
    if not payload.question.strip():
        raise HTTPException(status_code=400, detail="Query string cannot be empty.")
        
    try:
        response = rag_chain.invoke({"input": payload.question})
        
        retrieved_sources = [
            SourceDocument(
                content=doc.page_content[:300] + "...",
                metadata=doc.metadata
            )
            for doc in response.get("context", [])
        ]
        
        return LegalQueryResponse(
            answer=response["answer"],
            sources=retrieved_sources
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
