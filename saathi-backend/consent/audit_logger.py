import json
import hashlib
from datetime import datetime
from typing import Optional, List, Dict, Any

_IN_MEMORY_LOGS: List[Dict[str, Any]] = []

async def log_agent_decision(
    db_conn,
    event_id: str,
    customer_token: str,
    trigger: str,
    life_event_tag: str,
    recommended_product: Any,
    recommendation_rationale: str,
    agent_chain: List[str],
    consent_obtained: bool,
    consent_method: Optional[str] = None,
    conversation_messages: Optional[List[dict]] = None,
) -> Dict[str, Any]:
    """
    Writes a full XAI audit record per RBI cybersecurity guidelines to PostgreSQL.
    If db_conn is None or database write fails, logs locally in fallback mode.
    """
    # 1. Parse product_id dynamically
    product_id = None
    if isinstance(recommended_product, dict):
        product_id = recommended_product.get("product_id") or recommended_product.get("id")
    elif isinstance(recommended_product, str):
        product_id = recommended_product

    # 2. Determine consent time
    consent_at = None
    if consent_obtained:
        consent_at = datetime.utcnow().isoformat()

    # 3. Build the primary compliance record dict
    record = {
        "event_id": event_id,
        "customer_token": customer_token,
        "trigger_type": trigger,
        "life_event_tag": life_event_tag,
        "product_id": product_id,
        "agent_chain": agent_chain,
        "rationale": recommendation_rationale,
        "consent_obtained": consent_obtained,
        "consent_method": consent_method,
        "consent_at": consent_at,
        "timestamp": datetime.utcnow().isoformat(),
        "conversation_messages": conversation_messages,
    }
    
    # 4. Generate integrity hash over the sorted JSON representation
    record_json_str = json.dumps(record, sort_keys=True)
    integrity_hash = hashlib.sha256(record_json_str.encode()).hexdigest()
    record["integrity_hash"] = integrity_hash
    
    # 5. Insert into PostgreSQL if connection is provided or can be fetched from main
    if db_conn is None:
        try:
            import main
            db_conn = main.db_pool
        except ImportError:
            pass

    if db_conn is not None:
        try:
            # Ensure the audit_log table exists
            await db_conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id SERIAL PRIMARY KEY,
                    event_id VARCHAR(64) NOT NULL UNIQUE,
                    customer_token VARCHAR(64) NOT NULL,
                    trigger_type VARCHAR(50),
                    life_event_tag VARCHAR(50),
                    product_id VARCHAR(50),
                    agent_chain JSONB,
                    rationale TEXT,
                    consent_method VARCHAR(20),
                    consent_at TIMESTAMPTZ,
                    record_json JSONB NOT NULL,
                    integrity_hash VARCHAR(64) NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                );
            """)
            
            # Insert the record
            await db_conn.execute("""
                INSERT INTO audit_log (
                    event_id,
                    customer_token,
                    trigger_type,
                    life_event_tag,
                    product_id,
                    agent_chain,
                    rationale,
                    consent_method,
                    consent_at,
                    record_json,
                    integrity_hash
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
                ON CONFLICT (event_id) DO UPDATE SET
                    consent_method = EXCLUDED.consent_method,
                    consent_at = EXCLUDED.consent_at,
                    record_json = EXCLUDED.record_json,
                    integrity_hash = EXCLUDED.integrity_hash;
            """, 
                event_id,
                customer_token,
                trigger,
                life_event_tag,
                product_id,
                json.dumps(agent_chain),
                recommendation_rationale,
                consent_method,
                consent_at,
                json.dumps(record),
                integrity_hash
            )
            print(f"[XAI Audit Logger] Saved log {event_id} to database.")
        except Exception as e:
            print(f"[XAI Audit Logger] Database insert failed ({e}). Logged record in fallback mode.")
    else:
        print(f"[XAI Audit Logger] (Local Fallback) Decision Record: {event_id} - Hash: {integrity_hash}")
        
    # 6. Broadcast the decision record via WebSocket if broadcaster is running
    try:
        from api.dashboard import broadcast_queue
        import asyncio
        asyncio.create_task(broadcast_queue.put(record))
    except Exception as e:
        print(f"[XAI Audit Logger] Failed to queue record for broadcast: {e}")

    # 7. Cache in-memory for offline dashboard fallback
    _IN_MEMORY_LOGS.append(record)

    return record

