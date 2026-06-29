import os
import json
import datetime
from anthropic import AsyncAnthropic
from graph.state import SAATHIState, ConversationStage
from knowledge.retriever import query_products

# Initialize Anthropic Async client
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", "mock-key"))

RECOMMENDER_SYSTEM = """
You are an SBI product specialist. Given a customer life-event, profile, and a list of eligible products,
select the SINGLE most appropriate SBI product and recommend a monthly saving/investment amount and tenure.

Respond ONLY with valid JSON (no markdown formatting, no other text):
{
  "product_id": "<product_id>",
  "product_name": "<product_name>",
  "recommended_amount": <number>,
  "tenure_months": <number>,
  "plain_rationale": "<one sentence rationale in simple language>"
}
"""

def filter_eligible_products(products: list, income_tier: str, risk_score: int) -> list:
    """
    Apply hardcoded eligibility rules (NOT AI-decided)
    - SBI_RD_12M: max_risk 6, min income tier entry
    - SBI_MF_SIP: min_risk 4, min income tier entry
    - SBI_TRAVEL_INS: any risk, any income tier
    """
    eligible = []
    for p in products:
        p_id = p.get("id")
        if p_id == "SBI_RD_12M":
            if risk_score <= 6:
                eligible.append(p)
        elif p_id == "SBI_MF_SIP":
            if risk_score >= 4:
                eligible.append(p)
        elif p_id == "SBI_TRAVEL_INS":
            eligible.append(p)
        else:
            eligible.append(p)
    return eligible

async def recommend_products(state: SAATHIState) -> SAATHIState:
    """
    Product Recommender Agent.
    Queries vector store, filters products dynamically, and uses Claude to select the single best recommendation.
    """
    # 1. Query candidate products from ChromaDB RAG
    candidates = await query_products(
        life_event=state["life_event_tag"],
        income_tier=state["income_tier"],
        risk_score=state["risk_score"],
        top_k=3
    )
    
    # 2. Filter using hardcoded rules
    eligible = filter_eligible_products(candidates, state["income_tier"], state["risk_score"])
    
    # Safe default if no eligible products are found
    if not eligible:
        eligible = [{
            "id": "SBI_RD_12M",
            "name": "SBI Recurring Deposit (12 Month)",
            "category": "savings",
            "min_amount": 100,
            "typical_entry_amount": 500,
            "tenure_months": 12,
            "interest_rate": 5.5,
            "plain_description": "Fixed monthly savings with guaranteed return."
        }]
        
    # 3. Choose the best product using Claude
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    recommendation = None
    
    if api_key and not api_key.startswith("your-") and not api_key == "mock-key":
        try:
            response = await client.messages.create(
                model="claude-3-5-sonnet-20241022",
                max_tokens=300,
                system=RECOMMENDER_SYSTEM,
                messages=[{
                    "role": "user",
                    "content": f"""
Customer Profile: income_tier={state['income_tier']}, risk_score={state['risk_score']}/10, account_balance={state['account_balance']}
Life Event: {state['life_event_tag']}
Eligible Products: {json.dumps(eligible)}

Please select the single best product and recommended starting amount.
                    """
                }],
                temperature=0.0
            )
            raw_text = response.content[0].text.strip()
            if raw_text.startswith("```"):
                lines = raw_text.split("\n")
                if lines[0].strip().startswith("```json") or lines[0].strip().startswith("```"):
                    raw_text = "\n".join(lines[1:-1])
            recommendation = json.loads(raw_text)
        except Exception as e:
            print(f"[Product Recommender] LLM call failed ({e}). Using rule-based fallback.")
            
    if recommendation is None:
        # Rule-based fallback
        selected = eligible[0]
        rec_amount = selected.get("typical_entry_amount", 500)
        tenure = selected.get("tenure_months", 12)
        
        # Adjust amount based on customer context
        if state["account_balance"] > 100000:
            rec_amount = rec_amount * 2
            
        recommendation = {
            "product_id": selected.get("id"),
            "product_name": selected.get("name"),
            "recommended_amount": float(rec_amount),
            "tenure_months": int(tenure),
            "plain_rationale": f"Recommend starting a {selected.get('name')} to lock in guaranteed returns."
        }
        
    state["recommended_products"] = [recommendation]
    state["selected_product"] = recommendation
    state["stage"] = ConversationStage.PRODUCT_RECOMMENDED
    
    # 4. Log to audit trail
    state["audit_trail"].append({
        "agent": "product_recommender",
        "output": recommendation,
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    
    return state
