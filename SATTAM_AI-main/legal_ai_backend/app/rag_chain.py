import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.chains import create_retrieval_chain
from langchain_classic.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate

load_dotenv()

def get_legal_rag_chain():
    # 1. Initialize Embeddings (384 dimensions)
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    
    # 2. Connect to Pinecone Index
    index_name = os.getenv("PINECONE_INDEX_NAME", "lgpw")
    vectorstore = PineconeVectorStore(
        index_name=index_name,
        embedding=embeddings
    )
    
    retriever = vectorstore.as_retriever(search_kwargs={"k": 4})

    # 3. Grounded Legal System Prompt
    system_prompt = (
        "You are SATTAM AI, an expert Legal Assistant specializing in Indian Law.\n"
        "Use the provided legal context to accurately answer the user's question.\n"
        "If the answer cannot be determined from the context, state that clearly.\n"
        "Always cite relevant Section numbers and Act names when present in the context.\n\n"
        "Context:\n{context}"
    )

    prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        ("human", "{input}"),
    ])

    # 4. LLM Generation Model (Free Gemini API)
    llm = ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=os.getenv("GEMINI_API_KEY"),
        temperature=0.1
    )

    # 5. Build RAG Chain
    question_answer_chain = create_stuff_documents_chain(llm, prompt)
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    return rag_chain