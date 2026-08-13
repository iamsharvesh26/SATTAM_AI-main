import os
import json
import re
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_openai import ChatOpenAI
from langchain_pinecone import PineconeVectorStore
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_core.runnables import RunnablePassthrough
from deep_translator import GoogleTranslator
from app.core.database import chat_sessions

load_dotenv()


NS_LAW        = "law"
NS_USER_PREFIX = "user_"

def user_namespace(user_id: str) -> str:
    return f"{NS_USER_PREFIX}{user_id}"


embeddings = HuggingFaceEmbeddings(model_name="intfloat/multilingual-e5-large")

law_vectorstore = PineconeVectorStore(
    index_name=os.getenv("PINECONE_INDEX_NAME", "sattam-law"),
    embedding=embeddings,
    text_key="text",
    namespace=NS_LAW,
)


chat_llm = ChatOpenAI(
    model="llama-3.1-8b-instant",
    api_key=os.getenv("GROQ_API_KEY"),
    base_url="https://api.groq.com/openai/v1",
    max_tokens=2000,
    temperature=0.1,
)


qa_prompt = PromptTemplate.from_template(
    """You are a helpful Indian Legal Assistant. Answer clearly for a non-lawyer.
First, identify the user intent:
- If the user input is a greeting or casual message (like "hi", "hello", "how are you"), respond normally and politely WITHOUT giving legal information.
- If the user asks a legal question, then:
    - Use the provided context.
    - If not found, use your general knowledge of Indian Law.
    - Explain clearly for a non-lawyer and do not give incomplte answer.
    - Mention relevant section numbers, article numbers, or act names.
    - End with: "Please consult a qualified lawyer for advice specific to your situation."


PREVIOUS CONVERSATION:
{chat_history}

DOCUMENT CONTEXT (from user's uploaded document):
{doc_context}

INDIAN LAW CONTEXT:
{law_context}

QUESTION: {question}
ANSWER IN ENGLISH (include relevant section/article numbers):"""
)

explain_prompt = PromptTemplate.from_template(
    """Analyze this legal term/clause: '{term}'
Context: {context_info}

Explain it simply for a non-lawyer.
Return ONLY a valid JSON object:
{{
    "term": "{term}",
    "explanation": "simple plain-language explanation",
    "examples": ["example 1", "example 2"],
    "related_laws": ["law 1", "law 2"],
    "related_terms": ["term 1", "term 2"],
    "case_references": ["case 1"]
}}
JSON:"""
)




def _translate(text: str, source: str, target: str) -> str:
    """Translate using deep_translator. Handles long text by splitting."""
    if source == target or not text.strip():
        return text
    try:
        if len(text) > 4500:
            mid   = text[:4500].rfind(". ")
            mid   = mid if mid != -1 else 4500
            part1 = _translate(text[:mid + 1], source, target)
            part2 = _translate(text[mid + 1:], source, target)
            return part1 + " " + part2
        result = GoogleTranslator(source=source, target=target).translate(text)
        return result or text
    except Exception as e:
        print(f"Translation error ({source}→{target}): {e}")
        return text   


def _translate_to_english(text: str, source_lang: str) -> str:
    if source_lang == "en":
        return text
    return _translate(text, source_lang, "en")


def _translate_from_english(text: str, target_lang: str) -> str:
    if target_lang == "en":
        return text
    return _translate(text, "en", target_lang)




def get_hybrid_context(inputs: dict) -> dict:
    """
    Namespace-isolated Pinecone search.
    Law namespace → shared for all users.
    user_{id} namespace → private per user.
    """
    question    = f"query: {inputs['question']}"
    document_id = inputs.get("document_id")
    user_id     = inputs.get("user_id", "")

    
    law_docs = law_vectorstore.similarity_search(
        question, k=4, filter={"type": "global_law"}
    )

    
    doc_docs = []
    if document_id and document_id not in ("null", None, ""):
        user_vs = PineconeVectorStore(
            index_name=os.getenv("PINECONE_INDEX_NAME", "sattam-law"),
            embedding=embeddings,
            text_key="text",
            namespace=user_namespace(user_id),
        )
        doc_docs = user_vs.similarity_search(
            question, k=4, filter={"document_id": document_id}
        )

    return {
        "doc_context":  "\n".join([d.page_content for d in doc_docs])
                        if doc_docs else "No specific document context.",
        "law_context":  "\n".join([d.page_content for d in law_docs])
                        if law_docs else "No global law context found.",
        "question":     inputs["question"],
        "chat_history": inputs.get("chat_history", "No previous conversation."),
    }



def explain_legal_term(term: str, language: str, context: str = "General legal context") -> dict:
    """
    Always generates the explanation in English (LLaMA is most reliable in English),
    then translates the explanation and examples to the user's language via Google Translate.
    """
    chain = explain_prompt | chat_llm | StrOutputParser()
    raw   = chain.invoke({"term": term, "context_info": context})

    json_match = re.search(r'\{.*\}', raw, re.DOTALL)
    if not json_match:
        return {"term": term, "explanation": "Analysis failed. Please try again."}

    try:
        data = json.loads(json_match.group(0))
    except json.JSONDecodeError:
        return {"term": term, "explanation": "Could not parse explanation. Please try again."}

    if language != "en":
        data["explanation"] = _translate_from_english(data.get("explanation", ""), language)
        data["examples"]    = [_translate_from_english(ex, language)
                                for ex in data.get("examples", [])]

    return data



def generate_answer(
    question:    str,
    document_id,
    session_id:  str,
    user_id:     str,
    language:    str,   
) -> tuple:
    """
    Language pipeline:
    1. EXPLAIN requests → handled separately, no chat history saved
    2. Non-English questions → translated to English before LLM (better quality)
    3. LLM always answers in English
    4. English answer → translated back to user's language via Google Translate
    5. Both English and translated answers saved to MongoDB
    """

    if "EXPLAIN_LEGAL_TERM:" in question:
        term             = question.replace("EXPLAIN_LEGAL_TERM:", "").strip()
        explanation_data = explain_legal_term(term, language)
        json_str         = json.dumps(explanation_data)
        return json_str, json_str


    if language != "en":
        english_question = _translate_to_english(question, language)
        if not english_question or english_question == question:
            english_question = question
    else:
        english_question = question

    session          = chat_sessions.find_one({"session_id": session_id})
    chat_history_str = ""
    if session and "history" in session:
        for msg in session["history"][-3:]:
            ai_text = msg.get("ai_english", msg.get("ai", ""))
            chat_history_str += f"User: {msg.get('user', '')}\nAI: {ai_text}\n"

    qa_chain = (
        RunnablePassthrough()
        | get_hybrid_context
        | qa_prompt
        | chat_llm
        | StrOutputParser()
    )

    eng_answer = qa_chain.invoke({
        "question":     english_question,
        "document_id":  document_id,
        "user_id":      user_id,
        "chat_history": chat_history_str or "No previous conversation.",
    }).strip()

    if language != "en":
        final_answer = _translate_from_english(eng_answer, language)
        if not final_answer or final_answer.strip() == eng_answer.strip():
            print(f"Warning: Translation to '{language}' failed. Returning English.")
            final_answer = eng_answer
    else:
        final_answer = eng_answer

    # Save to MongoDB 
    chat_sessions.update_one(
        {"session_id": session_id},
        {
            "$set":  {"user_id": user_id},
            "$push": {
                "history": {
                    "user":       question,       
                    "ai":         final_answer,   
                    "ai_english": eng_answer,     
                }
            },
        },
        upsert=True,
    )

    return eng_answer, final_answer