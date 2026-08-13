import os
import time
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFDirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_pinecone import PineconeVectorStore
from pinecone import Pinecone, ServerlessSpec

# Load environment variables from .env
load_dotenv()

def run_ingestion():
    pdf_folder = "./legal_docs"
    
    if not os.path.exists(pdf_folder) or not os.listdir(pdf_folder):
        print(f"Error: No PDF files found in '{pdf_folder}'. Please place at least one PDF there.")
        return

    # 1. Load Legal PDFs
    print("Loading PDFs from legal_docs/...")
    loader = PyPDFDirectoryLoader(pdf_folder)
    documents = loader.load()
    print(f"Loaded {len(documents)} document pages.")

    # 2. Section-Aware Chunking
    print("Chunking documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=600,
        chunk_overlap=100,
        separators=["\nSection ", "\n\n", "\n", " ", ""]
    )
    chunks = text_splitter.split_documents(documents)
    print(f"Total chunks created: {len(chunks)}")

    # 3. Embeddings Model
    print("Initializing HuggingFace embedding model...")
    embeddings = HuggingFaceEmbeddings(model_name="BAAI/bge-small-en-v1.5")

    # 4. Pinecone Connection
    pinecone_api_key = os.getenv("PINECONE_API_KEY")
    index_name = os.getenv("PINECONE_INDEX_NAME", "legal-sattam-index")

    pc = Pinecone(api_key=pinecone_api_key)

    # Create Index if not existing
    existing_indexes = [idx["name"] for idx in pc.list_indexes()]
    if index_name not in existing_indexes:
        print(f"Creating new Pinecone index: '{index_name}'...")
        pc.create_index(
            name=index_name,
            dimension=384,
            metric="cosine",
            spec=ServerlessSpec(cloud="aws", region="us-east-1")
        )
        while not pc.describe_index(index_name).status["ready"]:
            time.sleep(1)

    # 5. Store Vectors in Pinecone
    print("Uploading vector embeddings to Pinecone...")
    PineconeVectorStore.from_documents(
        documents=chunks,
        embedding=embeddings,
        index_name=index_name
    )
    print("Ingestion finished successfully! Vector index is ready.")

if __name__ == "__main__":
    run_ingestion()