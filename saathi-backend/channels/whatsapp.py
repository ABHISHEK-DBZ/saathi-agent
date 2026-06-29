import os
import uuid
import httpx
from fastapi import APIRouter, Request, HTTPException, Query
from fastapi.responses import PlainTextResponse
from datetime import datetime

from graph.state import ConversationStage
from channels.session import get_session, update_session

router = APIRouter()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_ACCESS_TOKEN", "mock-token")
PHONE_NUMBER_ID = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "mock-phone-id")
WHATSAPP_VERIFY_TOKEN = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "mock-verify-token")

def safe_print(text: str):
    import sys
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding='utf-8')
        print(text)
    except Exception:
        try:
            encoding = sys.stdout.encoding or 'utf-8'
            print(text.encode(encoding, errors='replace').decode(encoding))
        except Exception:
            print(text.encode('ascii', errors='replace').decode('ascii'))

async def send_whatsapp_message(to: str, message: str) -> dict:
    """
    Send a text message via Meta WhatsApp Business API v19.0.
    """
    url = f"https://graph.facebook.com/v19.0/{PHONE_NUMBER_ID}/messages"
    payload = {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": message}
    }
    headers = {
        "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        "Content-Type": "application/json"
    }
    
    # If using mock environment or not configured, log locally and return mock response
    if WHATSAPP_TOKEN == "mock-token" or PHONE_NUMBER_ID == "mock-phone-id":
        safe_print(f"[WhatsApp Send Mock] To: {to} | Message: {message}")
        return {"messaging_product": "whatsapp", "contacts": [{"input": to, "wa_id": to}], "messages": [{"id": f"wamid.{uuid.uuid4()}"}]}

    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, headers=headers, timeout=10.0)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            safe_print(f"[WhatsApp Send Error] HTTP error {e.response.status_code}: {e.response.text}")
            return {"error": e.response.text}
        except Exception as e:
            safe_print(f"[WhatsApp Send Error] Connection failed: {e}")
            return {"error": str(e)}


def build_confirmation_message(result: dict, lang: str) -> str:
    """
    Formulate the final subscription/activation confirmation message in the user's language.
    """
    if lang == "hi":
        return (
            f"Badhai ho! Aapka account {result.get('account_number')} safalta purvak khul gaya hai. 🙏\n\n"
            f"Maturity Date: {result.get('maturity_date')}\n"
            f"Maturity Amount: ₹{result.get('maturity_amount'):,.0f}\n\n"
            f"Dhanyawad! SBI aapki pragati ka saathi."
        )
    elif lang == "mr":
        return (
            f"अभिनंदन! तुमचे खाते {result.get('account_number')} यशस्वीरित्या सुरू झाले आहे. 🙏\n\n"
            f"मॅच्युरिटी तारीख: {result.get('maturity_date')}\n"
            f"मॅच्युरिटी रक्कम: ₹{result.get('maturity_amount'):,.0f}\n\n"
            f"धन्यवाद! SBI तुमच्या प्रगतीचा साथी."
        )
    elif lang == "ta":
        return (
            f"வாழ்த்துகள்! உங்கள் கணக்கு {result.get('account_number')} வெற்றிகரமாக தொடங்கப்பட்டது. 🙏\n\n"
            f"முதிர்வு தேதி: {result.get('maturity_date')}\n"
            f"முதிர்வு தொகை: ₹{result.get('maturity_amount'):,.0f}\n\n"
            f"நன்றி! SBI உங்கள் முன்னேற்றத்தின் தோழன்."
        )
    else:
        return (
            f"Congratulations! Your account {result.get('account_number')} has been successfully opened. 🙏\n\n"
            f"Maturity Date: {result.get('maturity_date')}\n"
            f"Maturity Amount: ₹{result.get('maturity_amount'):,.0f}\n\n"
            f"Thank you for choosing SBI!"
        )

async def handle_customer_confirmation(customer_phone: str, session: dict):
    """
    Called when customer responds '1' or 'yes' to proceed.
    Transitions state, calls LangGraph to build execution payload,
    generates simulated OTP, and messages it to the customer.
    """
    # 1. Update stage and consent
    session["stage"] = ConversationStage.CONSENT_VERIFIED
    session["consent_obtained"] = True
    
    # 2. Invoke the agent graph to compile the execution payload
    from graph.workflow import saathi_graph
    final_state = await saathi_graph.ainvoke(session)
    
    # 3. Generate simulated OTP
    from consent.otp import generate_otp
    otp = await generate_otp(customer_phone)
    
    # 4. Formulate localized OTP request
    lang = final_state.get("language_code", "hi")
    product_name = final_state.get("selected_product", {}).get("product_name", "SBI product")
    
    if lang == "hi":
        msg = f"Aapka OTP {otp} hai. {product_name} confirm karne ke liye kripya reply mein OTP enter karein. 🙏"
    elif lang == "mr":
        msg = f"तुमचा OTP {otp} आहे. {product_name} सुरू करण्यासाठी कृपया उत्तर म्हणून OTP प्रविष्ट करा. 🙏"
    elif lang == "ta":
        msg = f"உங்கள் OTP {otp} ஆகும். {product_name} ஐ உறுதிப்படுத்த, இந்த OTP ஐ பதிலளிக்கவும். 🙏"
    else:
        msg = f"Your OTP is {otp}. To confirm starting {product_name}, please reply with this OTP. 🙏"
        
    # Append outbound OTP request to messages
    if "conversation_messages" not in final_state or final_state["conversation_messages"] is None:
        final_state["conversation_messages"] = []
    final_state["conversation_messages"].append({
        "direction": "outbound",
        "content": msg,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # 5. Save updated state back to Redis
    final_state["event_id"] = session.get("event_id")
    await update_session(customer_phone, final_state)

@router.get("/webhook/whatsapp", response_class=PlainTextResponse)
async def verify_whatsapp_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Meta webhook validation endpoint.
    """
    if hub_mode == "subscribe" and hub_verify_token == WHATSAPP_VERIFY_TOKEN:
        print("[WhatsApp Webhook] Handshake successful!")
        return hub_challenge
    raise HTTPException(status_code=403, detail="Verification token mismatch")

@router.post("/webhook/whatsapp")
async def receive_whatsapp_message(request: Request):
    """
    Receives incoming WhatsApp messages from customers, parses options/OTPs,
    and updates conversation state.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Extract entry, changes, messages
    entries = data.get("entry", [])
    if not entries:
        return {"status": "no_entries"}
        
    changes = entries[0].get("changes", [])
    if not changes:
        return {"status": "no_changes"}
        
    value = changes[0].get("value", {})
    messages = value.get("messages", [])
    if not messages:
        # Might be a status update (delivered, read, sent) which we ignore
        return {"status": "ignored_status_update"}
        
    msg = messages[0]
    customer_phone = msg.get("from")
    
    # Extract text content
    text = ""
    if "text" in msg and isinstance(msg["text"], dict):
        text = msg["text"].get("body", "")
    elif hasattr(msg, "text") and hasattr(msg.text, "body"):
        text = msg.text.body
    
    text = text.strip()
    if not text:
        return {"status": "empty_message"}

    # Fetch session from Redis
    session = await get_session(customer_phone)
    
    # Normalize reply comparison
    normalized_text = text.lower()
    
    # Log incoming message to session
    if session:
        if "conversation_messages" not in session or session["conversation_messages"] is None:
            session["conversation_messages"] = []
        session["conversation_messages"].append({
            "direction": "inbound",
            "content": text,
            "timestamp": datetime.utcnow().isoformat()
        })
        await update_session(customer_phone, session)
    
    # Case: Session is in AWAITING_CONSENT stage AND execution_payload is built, treat input as OTP
    if session and session.get("stage") in [ConversationStage.AWAITING_CONSENT, "awaiting_consent"] and session.get("execution_payload") is not None:
        from consent.otp import verify_otp
        if await verify_otp(customer_phone, text):
            # OTP verified, execute consent activation
            from agents.execution_builder import execute_payload
            result = await execute_payload(session.get("execution_payload", {}))
            
            # Send success confirmation
            lang = session.get("language_code", "hi")
            confirmation = build_confirmation_message(result, lang)
            await send_whatsapp_message(customer_phone, confirmation)
            
            # Append outbound confirmation message
            session["conversation_messages"].append({
                "direction": "outbound",
                "content": confirmation,
                "timestamp": datetime.utcnow().isoformat()
            })
            await update_session(customer_phone, session)
            
            # Write RBI-compliant XAI audit log
            from consent.audit_logger import log_agent_decision
            rec_product = session.get("selected_product") or (session.get("recommended_products")[0] if session.get("recommended_products") else {})
            product_name = rec_product.get("product_name", "Unknown Product")
            rationale = rec_product.get("plain_rationale", "Consent verified via WhatsApp simulated OTP.")
            
            await log_agent_decision(
                db_conn=None,
                event_id=session.get("event_id") or str(uuid.uuid4()),
                customer_token=session.get("customer_token"),
                trigger=session.get("trigger_type"),
                life_event_tag=session.get("life_event_tag"),
                recommended_product=product_name,
                recommendation_rationale=rationale,
                agent_chain=["supervisor", "life_event_predictor", "product_recommender", "language_adapter", "execution_builder"],
                consent_obtained=True,
                consent_method="whatsapp_otp",
                conversation_messages=session.get("conversation_messages")
            )
            return {"status": "consent_completed"}
        else:
            # Invalid OTP message
            lang = session.get("language_code", "hi")
            if lang == "hi":
                err_msg = "OTP galat hai. Dobara try karein."
            elif lang == "mr":
                err_msg = "OTP चुकीचा आहे. कृपया पुन्हा प्रयत्न करा."
            elif lang == "ta":
                err_msg = "தவறான OTP. மீண்டும் முயற்சிக்கவும்."
            else:
                err_msg = "Incorrect OTP. Please try again."
            await send_whatsapp_message(customer_phone, err_msg)
            session["conversation_messages"].append({
                "direction": "outbound",
                "content": err_msg,
                "timestamp": datetime.utcnow().isoformat()
            })
            await update_session(customer_phone, session)
            return {"status": "otp_failed"}

    # Menu Reply Case 1: Yes / Proceed
    elif normalized_text in ["1", "haan", "yes", "ha", "हाँ"]:
        if not session:
            # If session expired or missing, send standard welcome
            await send_whatsapp_message(customer_phone, "Welcome! Please initiate by triggering a new event.")
            return {"status": "no_session"}
        await handle_customer_confirmation(customer_phone, session)
        return {"status": "confirmation_triggered"}

    # Menu Reply Case 2: Remind Later
    elif normalized_text in ["2", "baad mein", "later"]:
        reply = "Bilkul! Kal subah 10 baje yaad dilaunga. 🙏"
        await send_whatsapp_message(customer_phone, reply)
        if session:
            session["conversation_messages"].append({
                "direction": "outbound",
                "content": reply,
                "timestamp": datetime.utcnow().isoformat()
            })
            await update_session(customer_phone, session)
        return {"status": "reminder_scheduled"}

    # Menu Reply Case 3: Reject / Opt Out
    elif normalized_text in ["3", "nahi", "no", "नहीं", "stop", "stop"]:
        # Send opt-out confirmation message
        lang = session.get("language_code", "hi") if session else "hi"
        if lang == "hi":
            opt_out_msg = "Theek hai. Koi baat nahi. Jab chahein, 'Hi' bhejein. 🙏"
        elif lang == "mr":
            opt_out_msg = "ठीक आहे. काही हरकत नाही. तुम्हाला हवे तेव्हा 'Hi' पाठवा. 🙏"
        else:
            opt_out_msg = "Alright. No problem. You can reply 'Hi' anytime to start again. 🙏"
            
        await send_whatsapp_message(customer_phone, opt_out_msg)
        
        # Save opted-out flag in Redis
        if session:
            session["opted_out"] = True
            session["conversation_messages"].append({
                "direction": "outbound",
                "content": opt_out_msg,
                "timestamp": datetime.utcnow().isoformat()
            })
            await update_session(customer_phone, session)
        else:
            await update_session(customer_phone, {
                "opted_out": True,
                "conversation_messages": [{
                    "direction": "inbound",
                    "content": text,
                    "timestamp": datetime.utcnow().isoformat()
                }, {
                    "direction": "outbound",
                    "content": opt_out_msg,
                    "timestamp": datetime.utcnow().isoformat()
                }]
            })
            
        return {"status": "opted_out"}

    else:
        # Default fallback / greeting
        greeting = "SBI SAATHI virtual assistant mein aapka swagat hai. Kripya menu options (1, 2, 3) ya OTP reply karein. 🙏"
        await send_whatsapp_message(customer_phone, greeting)
        if session:
            session["conversation_messages"].append({
                "direction": "outbound",
                "content": greeting,
                "timestamp": datetime.utcnow().isoformat()
            })
            await update_session(customer_phone, session)
        return {"status": "default_greeting"}
