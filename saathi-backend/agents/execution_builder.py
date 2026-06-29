import datetime
from graph.state import SAATHIState, ConversationStage

def can_execute(state: SAATHIState) -> bool:
    """
    Hard check: only proceeds if consent_obtained == True AND otp_verified == True.
    This acts as a strict guardrail before triggering any external Core Banking APIs.
    """
    return (
        state.get("consent_obtained") is True and
        state.get("otp_verified") is True and
        state.get("execution_payload") is not None
    )

async def build_execution_payload(state: SAATHIState) -> SAATHIState:
    """
    Execution Builder Agent.
    Compiles the product activation payload and calculates maturity deterministically.
    Does NOT call any banking API directly.
    """
    # 1. Fetch selected product
    product = state.get("selected_product")
    if not product:
        product = state["recommended_products"][0] if state["recommended_products"] else {}
        
    rate = product.get("interest_rate", 5.5) or 5.5
    amount = product.get("recommended_amount", 500)
    tenure = product.get("tenure_months", 12)
    
    # 2. Deterministic formula calculation (no LLM estimation)
    # maturity = amount * tenure * (1 + rate / 100)
    maturity_amount = amount * tenure * (1 + rate / 100)
    
    # 3. Compile the payload
    payload = {
        "product_id": product.get("product_id"),
        "product_name": product.get("product_name"),
        "customer_token": state["customer_token"],
        "amount": float(amount),
        "tenure_months": int(tenure),
        "interest_rate": float(rate),
        "maturity_amount": float(maturity_amount),
        "timestamp": datetime.datetime.utcnow().isoformat()
    }
    
    state["selected_product"] = product
    state["execution_payload"] = payload
    
    # Update stage to AWAITING_CONSENT
    state["stage"] = ConversationStage.AWAITING_CONSENT
    
    # 4. Log to audit trail
    state["audit_trail"].append({
        "agent": "execution_builder",
        "output": {
            "payload_compiled": True,
            "maturity_amount": maturity_amount,
            "stage_updated": ConversationStage.AWAITING_CONSENT
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    
    return state

async def execute_payload(payload: dict) -> dict:
    """
    Mock Core Banking API transaction execution.
    Only triggered outside the Graph loop once consent is verified.
    """
    now = datetime.datetime.utcnow()
    # Simple consistent suffix using token hash
    token = payload.get("customer_token", "default")
    suffix = str(abs(hash(token)))[-4:]
    
    return {
        "status": "SUCCESS",
        "account_number": f"RD-{payload.get('product_id', 'SBI')}-{suffix}",
        "activation_date": now.strftime("%Y-%m-%d"),
        "next_debit_date": (now + datetime.timedelta(days=30)).strftime("%Y-%m-%d"),
        "maturity_date": (now + datetime.timedelta(days=payload.get("tenure_months", 12) * 30)).strftime("%Y-%m-%d"),
        "maturity_amount": payload.get("maturity_amount")
    }
