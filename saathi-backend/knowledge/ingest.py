import os
import json
import chromadb
from sentence_transformers import SentenceTransformer

def ingest_products():
    """
    Ingest product metadata into ChromaDB vector database with embeddings.
    """
    # 1. Load JSON file
    base_dir = os.path.dirname(os.path.dirname(__file__))
    json_path = os.path.join(base_dir, "knowledge", "data", "sbi_products.json")
    db_path = os.path.join(base_dir, "chroma_db")
    
    print(f"[Ingestion] Loading products from: {json_path}")
    with open(json_path, "r", encoding="utf-8") as f:
        products = json.load(f)
        
    # 2. Initialize ChromaDB
    print(f"[Ingestion] Setting up ChromaDB at: {db_path}")
    client = chromadb.PersistentClient(path=db_path)
    collection = client.get_or_create_collection(
        name="sbi_products",
        metadata={"hnsw:space": "cosine"}
    )
    
    # 3. Load Embedding Model
    print("[Ingestion] Loading multilingual-e5-large sentence transformer...")
    model = SentenceTransformer("intfloat/multilingual-e5-large")
    
    documents = []
    embeddings = []
    metadatas = []
    ids = []
    
    # 4. Prepare Embeddings and Metadata
    for product in products:
        name = product.get("name")
        category = product.get("category")
        events = ", ".join(product.get("target_life_events", []))
        desc = product.get("plain_description")
        
        # Exact prompt construction
        text = f"Product: {name}\nCategory: {category}\nLife Events: {events}\nDescription: {desc}"
        documents.append(text.strip())
        
        # Safe copy to avoid mutation, and convert lists to strings for Chroma compatibility
        meta = product.copy()
        meta["target_life_events"] = ",".join(product.get("target_life_events", []))
        meta["target_income_tiers"] = ",".join(product.get("target_income_tiers", []))
        meta["target_risk_scores"] = ",".join(map(str, product.get("target_risk_scores", [])))
        
        metadatas.append(meta)
        ids.append(product["id"])
        
    # 5. Generate embeddings
    print("[Ingestion] Generating embeddings...")
    embeddings = model.encode(documents).tolist()
    
    # 6. Add to Collection
    print(f"[Ingestion] Saving {len(products)} products to ChromaDB collection 'sbi_products'...")
    collection.add(
        documents=documents,
        embeddings=embeddings,
        metadatas=metadatas,
        ids=ids
    )
    
    print("Ingestion complete. ChromaDB database is successfully seeded.")

if __name__ == "__main__":
    ingest_products()
