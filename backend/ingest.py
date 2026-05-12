import os
from llama_index.core import SimpleDirectoryReader, VectorStoreIndex, StorageContext
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core.node_parser import SentenceSplitter
import chromadb

CORPUS_DIR = os.path.join(os.path.dirname(__file__), "corpus")
CHROMA_DIR = os.path.join(os.path.dirname(__file__), "chroma_db")

def build_index():
    print("Loading documents...")
    documents = SimpleDirectoryReader(CORPUS_DIR).load_data()

    print("Initialising embedding model...")
    embed_model = HuggingFaceEmbedding(model_name="BAAI/bge-small-en-v1.5")

    print("Setting up ChromaDB...")
    chroma_client = chromadb.PersistentClient(path=CHROMA_DIR)
    chroma_collection = chroma_client.get_or_create_collection("vaultrag")
    vector_store = ChromaVectorStore(chroma_collection=chroma_collection)
    storage_context = StorageContext.from_defaults(vector_store=vector_store)

    print("Chunking and indexing...")
    splitter = SentenceSplitter(chunk_size=256, chunk_overlap=32)
    index = VectorStoreIndex.from_documents(
        documents,
        storage_context=storage_context,
        embed_model=embed_model,
        transformations=[splitter],
    )
    print("Index built successfully.")
    return index

if __name__ == "__main__":
    build_index()
