import os
import sys
import json
import time
import httpx
import redis
from dotenv import load_dotenv

# Configure console to use UTF-8 to handle Hindi/Marathi and emojis on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

def safe_print(text: str):
    try:
        print(text)
    except Exception:
        try:
            encoding = sys.stdout.encoding or 'utf-8'
            print(text.encode(encoding, errors='replace').decode(encoding))
        except Exception:
            print(text.encode('ascii', errors='replace').decode('ascii'))

# Load environment variables from .env
backend_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(backend_dir, ".env")
load_dotenv(env_path)

def verify_flow():
    safe_print("=================== SAATHI END-TO-END DEMO TEST RUN ===================")
    
    # Configuration
    base_url = "http://localhost:8000"
    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379")
    test_phone = os.getenv("WHATSAPP_TEST_PHONE") or os.getenv("WHATSAPP_RECIPIENT_PHONE") or "919999999999"
    
    safe_print(f"Backend Target URL: {base_url}")
    safe_print(f"Redis target URL: {redis_url}")
    safe_print(f"Test WhatsApp Phone: {test_phone}")
    
    # 1. Trigger Salary Credit Webhook for Ramesh Kumar
    webhook_url = f"{base_url}/webhook/transaction"
    payload = {
        "customer_id": "DEMO-RAMESH-001",
        "transaction_type": "salary_credit",
        "amount": 28000.0,
        "account_balance": 41000.0,
        "timestamp": "2026-06-29T17:00:00Z"
    }
    
    safe_print("\n[Step 1] Triggering transaction webhook (Salary Credit for Ramesh Kumar)...")
    try:
        response = httpx.post(webhook_url, json=payload, timeout=5.0)
        response.raise_for_status()
        resp_data = response.json()
        event_id = resp_data.get("event_id")
        safe_print(f"Webhook Accepted! Event ID: {event_id}")
    except Exception as e:
        safe_print(f"Error firing transaction webhook: {e}")
        safe_print("Please ensure your FastAPI backend is running (uvicorn main:app --port 8000)")
        sys.exit(1)
        
    # 2. Poll GET /dashboard/events every second for 10 seconds
    safe_print("\n[Step 2] Polling dashboard events list to track execution...")
    event_found = False
    
    for sec in range(1, 11):
        time.sleep(1.0)
        try:
            events_response = httpx.get(f"{base_url}/dashboard/events", timeout=5.0)
            events_response.raise_for_status()
            events_list = events_response.json()
            
            # Search for the triggered event ID in the list
            matching_event = next((e for e in events_list if e.get("event_id") == event_id), None)
            if matching_event:
                safe_print(f"  -> Event found in dashboard feed (Poll second {sec}!)")
                event_found = True
                break
            else:
                safe_print(f"  -> Poll second {sec}: Event not written to DB yet...")
        except Exception as e:
            safe_print(f"  -> Poll second {sec} failed: {e}")
            
    if not event_found:
        safe_print("\nError: Event was not found in the dashboard audit log feed within 10 seconds.")
        safe_print("Check if PostgreSQL is running and connected (docker-compose status).")
        sys.exit(1)
        
    # 3. Retrieve Event details and print the agent steps
    safe_print("\n[Step 3] Fetching detailed agent chain decision record...")
    try:
        detail_response = httpx.get(f"{base_url}/dashboard/event/{event_id}", timeout=5.0)
        detail_response.raise_for_status()
        event_detail = detail_response.json()
        
        agent_chain = event_detail.get("agent_chain", [])
        rationale = event_detail.get("rationale", "No rationale recorded.")
        life_event = event_detail.get("life_event_tag", "None")
        product = event_detail.get("product_id", "None")
        
        safe_print("\n--- Agent Execution Flow ---")
        for i, step in enumerate(agent_chain, 1):
            safe_print(f" Step {i}: {step.upper()}")
            
        safe_print(f"\nPredicted Life Event Tag: {life_event}")
        safe_print(f"Recommended Product ID: {product}")
        safe_print(f"Auditable Recommendation Rationale:\n{rationale}")
        safe_print("-----------------------------")
        
    except Exception as e:
        safe_print(f"Error fetching event details: {e}")
        sys.exit(1)
        
    # 4. Verify outbound WhatsApp message queue (via Redis or FastAPI fallback)
    safe_print("\n[Step 4] Checking session state to verify WhatsApp queue...")
    session = None
    try:
        # Try direct Redis check
        safe_print("  -> Attempting direct Redis connection...")
        r = redis.Redis.from_url(redis_url, socket_timeout=1.0, socket_connect_timeout=1.0, decode_responses=True)
        session_str = r.get(test_phone)
        if session_str:
            session = json.loads(session_str)
            safe_print("  -> Session successfully loaded from Redis!")
        else:
            safe_print("  -> No session found in Redis for phone key.")
    except Exception as redis_err:
        safe_print(f"  -> Redis direct connection bypassed ({redis_err})")
        
    if not session:
        # Try API session endpoint fallback
        safe_print("  -> Falling back to FastAPI session diagnostic endpoint...")
        try:
            session_response = httpx.get(f"{base_url}/dashboard/session/{test_phone}", timeout=5.0)
            session_response.raise_for_status()
            session = session_response.json()
            if session:
                safe_print("  -> Session successfully loaded from FastAPI memory!")
        except Exception as api_err:
            safe_print(f"  -> API session diagnostics fallback failed: {api_err}")
            
    if not session:
        safe_print("Error: Could not retrieve customer session via Redis or FastAPI diagnostics.")
        sys.exit(1)
        
    messages = session.get("conversation_messages", [])
    if not messages:
        safe_print("Error: Session retrieved, but conversation messages list is empty!")
        sys.exit(1)
        
    last_message = messages[-1]
    safe_print("Success! Confirmed WhatsApp message was queued in session.")
    safe_print(f"Recipient: {test_phone}")
    safe_print(f"Role: {last_message.get('role')}")
    safe_print(f"Queued Content:\n{last_message.get('content')}")
    
    safe_print("\n=================== E2E DEMO TEST COMPLETED SUCCESSFULLY ===================")


if __name__ == "__main__":
    verify_flow()
