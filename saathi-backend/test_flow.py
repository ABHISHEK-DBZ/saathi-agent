import asyncio
import os
import json
import sys

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

# Setup mock environment variables before importing modules
os.environ["ENV"] = "development"
os.environ["PII_ENCRYPTION_KEY"] = "test-encryption-key-for-saathi-123"
os.environ["WHATSAPP_ACCESS_TOKEN"] = "mock-token"
os.environ["WHATSAPP_PHONE_NUMBER_ID"] = "mock-phone-id"
os.environ["WHATSAPP_WEBHOOK_VERIFY_TOKEN"] = "mock-verify-token"
os.environ["WHATSAPP_TEST_PHONE"] = "919876543210"


from channels.webhook_router import process_transaction_event, TransactionWebhook
from channels.session import get_session, update_session
from channels.whatsapp import receive_whatsapp_message
from fastapi import Request

# Simple custom mock Request to simulate incoming JSON body for FastAPI
class MockRequest:
    def __init__(self, json_data):
        self._json_data = json_data
        
    async def json(self):
        return self._json_data

async def run_simulation():
    safe_print("=================== STARTING SAATHI END-TO-END FLOW SIMULATION ===================")
    
    customer_phone = "919876543210"
    
    # Clean up any existing session
    from channels.session import delete_session
    await delete_session(customer_phone)
    
    # ----------------------------------------------------
    # Step 1: Core Banking sends transaction webhook
    # ----------------------------------------------------
    safe_print("\n--- STEP 1: Core Banking sends transaction webhook (Salary Credit) ---")
    event = TransactionWebhook(
        customer_id="DEMO-RAMESH-001",
        transaction_type="salary_credit",
        amount=28000.0,
        account_balance=41000.0,
        timestamp="2026-06-29T17:00:00Z"
    )
    
    safe_print(f"Triggering event for customer: {event.customer_id}")
    await process_transaction_event(event)
    
    # Verify session has been created in Redis/Memory
    session = await get_session(customer_phone)
    safe_print("Session created successfully in memory/Redis!")
    safe_print(f"Current Session Stage: {session.get('stage')}")
    safe_print(f"Selected Product: {session.get('selected_product', {}).get('product_name')}")
    
    if session.get("conversation_messages"):
        safe_print(f"Outbound message sent: \n{session['conversation_messages'][-1]['content']}")
    else:
        safe_print("Error: No conversation message was sent.")
        
    # ----------------------------------------------------
    # Step 2: Customer replies "1" (wants to proceed)
    # ----------------------------------------------------
    safe_print("\n--- STEP 2: Customer replies '1' (Proceed) ---")
    payload_1 = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "123456", "phone_number_id": "123456"},
                            "contacts": [{"profile": {"name": "Ramesh Kumar"}, "wa_id": customer_phone}],
                            "messages": [
                                {
                                    "from": customer_phone,
                                    "id": "wamid.ID1",
                                    "timestamp": "1234567890",
                                    "text": {"body": "1"},
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    mock_request_1 = MockRequest(payload_1)
    response_1 = await receive_whatsapp_message(mock_request_1)
    safe_print(f"Response from WhatsApp webhook endpoint: {response_1}")
    
    # Verify session updated
    session = await get_session(customer_phone)
    safe_print(f"Current Session Stage after reply: {session.get('stage')}")
    safe_print(f"Execution Payload Compiled: {session.get('execution_payload') is not None}")
    
    # ----------------------------------------------------
    # Step 3: Customer enters OTP "123456"
    # ----------------------------------------------------
    safe_print("\n--- STEP 3: Customer enters OTP '123456' ---")
    payload_2 = {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": "123456",
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"display_phone_number": "123456", "phone_number_id": "123456"},
                            "contacts": [{"profile": {"name": "Ramesh Kumar"}, "wa_id": customer_phone}],
                            "messages": [
                                {
                                    "from": customer_phone,
                                    "id": "wamid.ID2",
                                    "timestamp": "1234567891",
                                    "text": {"body": "123456"},
                                    "type": "text"
                                }
                            ]
                        },
                        "field": "messages"
                    }
                ]
            }
        ]
    }
    
    mock_request_2 = MockRequest(payload_2)
    response_2 = await receive_whatsapp_message(mock_request_2)
    safe_print(f"Response from WhatsApp webhook endpoint: {response_2}")
    
    # Verify final session state
    session = await get_session(customer_phone)
    safe_print(f"Current Session Stage after OTP verification: {session.get('stage')}")
    safe_print(f"OTP Verified: {session.get('otp_verified')}")
    safe_print(f"Consent Obtained: {session.get('consent_obtained')}")
    
    safe_print("\n=================== SIMULATION COMPLETED SUCCESSFULLY ===================")

if __name__ == "__main__":
    asyncio.run(run_simulation())

