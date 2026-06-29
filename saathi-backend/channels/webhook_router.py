import uuid
from fastapi import APIRouter, BackgroundTasks
from pydantic import BaseModel

from graph.workflow import saathi_graph
from graph.state import SAATHIState, ConversationStage
from twin.profile import get_or_create_twin
from twin.anonymizer import tokenize_customer_id
from channels.session import get_session, update_session
from channels.whatsapp import send_whatsapp_message

router = APIRouter()

class TransactionWebhook(BaseModel):
    customer_id: str
    transaction_type: str          # e.g., "salary_credit", "emi_cleared", "high_travel_spend"
    amount: float
    account_balance: float
    timestamp: str

@router.post("/webhook/transaction")
async def receive_transaction(event: TransactionWebhook, background: BackgroundTasks):
    """
    Core Banking system pushes transaction signals here.
    Returns status instantly while processing the workflow asynchronously.
    """
    event_id = str(uuid.uuid4())
    background.add_task(process_transaction_event, event, event_id)
    return {"status": "accepted", "event_id": event_id}

async def process_transaction_event(event: TransactionWebhook, event_id: str = None):
    """
    Asynchronous runner for processing transaction alerts.
    Tokenizes ID, fetches/builds financial twin, validates opt-out,
    invokes LangGraph pipeline, pushes outbound WhatsApp, caches state, and logs decision.
    """
    if not event_id:
        event_id = str(uuid.uuid4())
    # 1. Anonymize the PII customer ID
    customer_token = tokenize_customer_id(event.customer_id)
    
    # 2. Retrieve customer financial digital twin
    twin = await get_or_create_twin(customer_token)
    
    # 3. Check opted_out status from twin profile and existing Redis session
    phone = twin.get("whatsapp") or twin.get("whatsapp_number")
    if not phone:
        print(f"[Webhook Event] Missing phone number for token {customer_token}. Aborting event.")
        return
        
    session = await get_session(phone)
    if twin.get("opted_out") or session.get("opted_out"):
        print(f"[Webhook Event] Customer {customer_token} has opted out. Ignoring transaction.")
        return
        
    # 4. Construct initial SAATHI state
    initial_state: SAATHIState = {
        "customer_token": customer_token,
        "language_code": twin.get("language_code", "hi"),
        "income_tier": twin.get("income_tier", "entry"),
        "risk_score": int(twin.get("risk_score", 3)),
        "trigger_type": event.transaction_type,
        "trigger_amount": float(event.amount),
        "account_balance": float(event.account_balance),
        "life_event_tag": None,
        "recommended_products": None,
        "conversation_messages": [],
        "selected_product": None,
        "execution_payload": None,
        "stage": ConversationStage.TRIGGERED,
        "consent_obtained": False,
        "audit_trail": []
    }
    
    print(f"[Webhook Event] Invoking LangGraph for {customer_token} ({phone})")
    
    # 5. Run the graph workflow and stream progress to the WebSocket broadcaster
    import asyncio
    import datetime
    final_state = initial_state.copy()
    async for node_update in saathi_graph.astream(initial_state):
        node_name = list(node_update.keys())[0]
        # Broadcast progress update to all active dashboard feeds
        try:
            from api.dashboard import broadcast_queue
            await broadcast_queue.put({
                "event_id": event_id or str(uuid.uuid4()),
                "type": "progress",
                "node": node_name,
                "status": "completed",
                "timestamp": datetime.datetime.utcnow().isoformat()
            })
        except Exception as ws_err:
            print(f"[WebSocket Progress] Broadcast failed: {ws_err}")
            
        # Update final_state with the node's outputs
        final_state.update(node_update[node_name])
        # Add a tiny delay between steps so the UI looks smooth and organic
        await asyncio.sleep(0.4)
        
    # 6. Send the last outbound message via WhatsApp if one was composed
    if final_state.get("conversation_messages"):
        last_message = final_state["conversation_messages"][-1]["content"]
        await send_whatsapp_message(phone, last_message)
        
    # 7. Save the final workflow state to Redis
    final_state["event_id"] = event_id or str(uuid.uuid4())
    await update_session(phone, final_state)

    # 8. Log the initial triggered decision to PostgreSQL
    from consent.audit_logger import log_agent_decision
    rec_products = final_state.get("recommended_products") or []
    product = rec_products[0] if rec_products else {}
    product_name = product.get("product_name", "Unknown Product")
    rationale = product.get("plain_rationale", "Initial recommendation triggered.")
    
    await log_agent_decision(
        db_conn=None,
        event_id=event_id or str(uuid.uuid4()),
        customer_token=customer_token,
        trigger=event.transaction_type,
        life_event_tag=final_state.get("life_event_tag"),
        recommended_product=product,
        recommendation_rationale=rationale,
        agent_chain=["supervisor", "life_event_predictor", "product_recommender", "language_adapter"],
        consent_obtained=False,
        consent_method=None,
        conversation_messages=final_state.get("conversation_messages")
    )

