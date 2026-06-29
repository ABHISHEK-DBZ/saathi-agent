import os
import json
import chromadb
from sentence_transformers import SentenceTransformer

_client = None
_model = None

def get_client():
    global _client, _model
    if _client is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        db_path = os.path.join(base_dir, "chroma_db")
        _client = chromadb.PersistentClient(path=db_path)
        _model = SentenceTransformer("intfloat/multilingual-e5-large")
    return _client, _model

async def query_products(life_event: str, income_tier: str, risk_score: int, top_k: int = 3) -> list:
    """
    Query the product vector database using the multilingual-e5-large model, 
    falling back to JSON local filters if the DB is uninitialized.
    """
    try:
        client, model = get_client()
        collection = client.get_collection("sbi_products")
        
        # Build embedding text matching ingest prompt style
        query_text = f"product for {life_event} customer with {income_tier} income and risk score {risk_score}"
        embedding = model.encode([query_text]).tolist()[0]
        
        # Query matching meta tags using string substring check
        results = collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            where={"target_income_tiers": {"$contains": income_tier}}
        )
        
        if results and results.get("metadatas") and results["metadatas"][0]:
            metadatas = []
            for meta in results["metadatas"][0]:
                item = meta.copy()
                
                # Parse strings back into lists/numbers for application logic compatibility
                if isinstance(item.get("target_life_events"), str):
                    item["target_life_events"] = item["target_life_events"].split(",")
                if isinstance(item.get("target_income_tiers"), str):
                    item["target_income_tiers"] = item["target_income_tiers"].split(",")
                if isinstance(item.get("target_risk_scores"), str):
                    item["target_risk_scores"] = [int(x) for x in item["target_risk_scores"].split(",") if x.isdigit()]
                
                # Explicit type coercion
                if "min_amount" in item:
                    item["min_amount"] = float(item["min_amount"])
                if "typical_entry_amount" in item:
                    item["typical_entry_amount"] = float(item["typical_entry_amount"])
                if "tenure_months" in item:
                    item["tenure_months"] = int(item["tenure_months"])
                if "interest_rate" in item:
                    item["interest_rate"] = float(item["interest_rate"])
                if "expected_return_pct" in item:
                    item["expected_return_pct"] = float(item["expected_return_pct"])
                    
                metadatas.append(item)
            return metadatas
    except Exception as e:
        print(f"[RAG Retriever] ChromaDB query failed ({e}). Falling back to JSON local file database.")
        
    # Local JSON fallback
    try:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        json_path = os.path.join(base_dir, "knowledge", "data", "sbi_products.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                products = json.load(f)
            
            matched = []
            for p in products:
                event_match = life_event in p.get("target_life_events", [])
                income_match = income_tier in p.get("target_income_tiers", [])
                risk_match = risk_score in p.get("target_risk_scores", []) or not p.get("target_risk_scores")
                
                if event_match and income_match and risk_match:
                    matched.append(p)
            
            if not matched:
                matched = [p for p in products if income_tier in p.get("target_income_tiers", [])]
                
            return matched[:top_k]
    except Exception as ex:
        print(f"[RAG Retriever] Fallback parsing failed: {ex}")
        
    return []
