import asyncio
import os
import json
import sys

# Configure console to use UTF-8 to handle Unicode encoding on Windows
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding='utf-8')
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

# Setup mock environment variables before importing
os.environ["REDIS_URL"] = "redis://localhost:6379"

from api.dashboard import broadcast_queue, get_dashboard_stats, get_dashboard_events, get_dashboard_event_detail

async def run_dashboard_tests():
    safe_print("=================== STARTING DASHBOARD API AND BROADCASTER TESTS ===================")
    
    # 1. Test Stats (Fallback Offline Mode)
    safe_print("\n--- TEST 1: Get Dashboard Stats (Mock Fallback) ---")
    stats = await get_dashboard_stats()
    safe_print(f"Stats: {stats}")
    
    # 2. Test List Events (Fallback Offline Mode)
    safe_print("\n--- TEST 2: Get Dashboard Events (Mock Fallback) ---")
    events = await get_dashboard_events(limit=5)
    safe_print(f"Events: {events}")
    
    # 3. Test Broadcaster Queue Push
    safe_print("\n--- TEST 3: Push Live Record to Broadcaster Queue ---")
    dummy_record = {
        "event_id": "test-live-999",
        "customer_token": "CUST-TEST",
        "trigger_type": "salary_credit",
        "integrity_hash": "dummyhash"
    }
    
    await broadcast_queue.put(dummy_record)
    safe_print(f"Broadcaster queue size: {broadcast_queue.qsize()}")
    
    # Verify we can pull it back out (mocking the broadcaster daemon)
    pulled_record = await broadcast_queue.get()
    safe_print(f"Pulled from Broadcaster queue: {pulled_record}")
    broadcast_queue.task_done()
    
    safe_print("\n=================== TESTS COMPLETED SUCCESSFULLY ===================")

if __name__ == "__main__":
    asyncio.run(run_dashboard_tests())
