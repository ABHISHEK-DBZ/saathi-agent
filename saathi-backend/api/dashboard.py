import json
import asyncio
from typing import List
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, HTTPException

from api.schemas import DashboardStats, EventSummary, EventDetail

router = APIRouter()

# Global list of active WebSockets and a queue for broadcasting event updates
active_websockets: List[WebSocket] = []
broadcast_queue = asyncio.Queue()

async def event_broadcaster():
    """
    Background daemon task. Reads new audit log records from broadcast_queue
    and pushes them to all active WebSocket clients.
    """
    while True:
        try:
            record = await broadcast_queue.get()
            # Broadcast to all connected clients
            for ws in list(active_websockets):
                try:
                    await ws.send_json(record)
                except Exception:
                    # Connection closed or dead, remove client
                    if ws in active_websockets:
                        active_websockets.remove(ws)
            broadcast_queue.task_done()
        except asyncio.CancelledError:
            break
        except Exception as e:
            print(f"[Event Broadcaster] Error in websocket broadcast: {e}")
            await asyncio.sleep(1)

@router.get("/dashboard/stats", response_model=DashboardStats)
async def get_dashboard_stats():
    """
    Retrieve aggregated transaction conversion funnel KPIs from PostgreSQL.
    """
    import main
    
    # Fallback to in-memory stats if database is not connected
    if main.db_pool is None:
        from consent.audit_logger import _IN_MEMORY_LOGS
        total = len(_IN_MEMORY_LOGS)
        converted = sum(1 for log in _IN_MEMORY_LOGS if log.get("consent_obtained"))
        opted_out = sum(1 for log in _IN_MEMORY_LOGS if log.get("opted_out") or log.get("stage") == "opted_out")
        return {
            "total_triggered": total,
            "in_conversation": total - converted - opted_out,
            "converted": converted,
            "opted_out": opted_out
        }
        
    try:
        async with main.db_pool.acquire() as conn:
            # Query counts
            total = await conn.fetchval("SELECT COUNT(*) FROM audit_log;")
            
            converted = await conn.fetchval(
                "SELECT COUNT(*) FROM audit_log WHERE consent_at IS NOT NULL;"
            )
            
            opted_out = await conn.fetchval("""
                SELECT COUNT(*) FROM audit_log 
                WHERE record_json->>'stage' = 'opted_out' 
                   OR record_json->>'opted_out' = 'true';
            """)
            
            # trigger_count - converted - opted_out = in_progress conversations
            in_conversation = await conn.fetchval("""
                SELECT COUNT(*) FROM audit_log 
                WHERE consent_at IS NULL 
                  AND NOT (record_json->>'stage' = 'opted_out' 
                           OR record_json->>'opted_out' = 'true');
            """)
            
            return {
                "total_triggered": total or 0,
                "in_conversation": in_conversation or 0,
                "converted": converted or 0,
                "opted_out": opted_out or 0
            }
    except Exception as e:
        print(f"[Dashboard API] Stats database query failed: {e}")
        # Default fallback
        return {
            "total_triggered": 0,
            "in_conversation": 0,
            "converted": 0,
            "opted_out": 0
        }

@router.get("/dashboard/events", response_model=List[EventSummary])
async def get_dashboard_events(limit: int = 20):
    """
    Query the last N event summaries from PostgreSQL ordered by created_at DESC.
    """
    import main
    
    if main.db_pool is None:
        from consent.audit_logger import _IN_MEMORY_LOGS
        from datetime import datetime
        return [
            {
                "event_id": log["event_id"],
                "trigger_type": log.get("trigger_type"),
                "life_event_tag": log.get("life_event_tag"),
                "product_id": log.get("product_id"),
                "consent_method": log.get("consent_method"),
                "created_at": log.get("timestamp") or datetime.utcnow().isoformat()
            }
            for log in reversed(_IN_MEMORY_LOGS)
        ][:limit]
        
    try:
        async with main.db_pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT event_id, trigger_type, life_event_tag, product_id, consent_method, created_at
                FROM audit_log
                ORDER BY created_at DESC
                LIMIT $1;
            """, limit)
            
            return [dict(row) for row in rows]
    except Exception as e:
        print(f"[Dashboard API] Events database query failed: {e}")
        return []

@router.get("/dashboard/event/{event_id}", response_model=EventDetail)
async def get_dashboard_event_detail(event_id: str):
    """
    Query the complete JSON decision record of an event for Explainable AI auditing.
    """
    import main
    
    if main.db_pool is None:
        from consent.audit_logger import _IN_MEMORY_LOGS
        matching = next((log for log in _IN_MEMORY_LOGS if log["event_id"] == event_id), None)
        if not matching:
            raise HTTPException(status_code=404, detail=f"Event ID {event_id} not found in-memory.")
        return matching
        
    try:
        async with main.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT record_json 
                FROM audit_log 
                WHERE event_id = $1;
            """, event_id)
            
            if not row:
                raise HTTPException(status_code=404, detail=f"Event ID {event_id} not found.")
                
            record = json.loads(row["record_json"])
            return record
    except HTTPException:
        raise
    except Exception as e:
        print(f"[Dashboard API] Event detail database query failed: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")

@router.websocket("/dashboard/live")
async def websocket_live_dashboard(websocket: WebSocket):
    """
    Websocket endpoint for pushing live event feeds to the dashboard UI.
    """
    await websocket.accept()
    active_websockets.append(websocket)
    try:
        while True:
            # Keeps the WebSocket connection open and listens for client heartbeats/messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        if websocket in active_websockets:
            active_websockets.remove(websocket)
    except Exception:
        if websocket in active_websockets:
            active_websockets.remove(websocket)

@router.get("/dashboard/session/{phone}")
async def get_session_diagnostics(phone: str):
    """
    Diagnostic endpoint to retrieve the active session for testing and demos.
    """
    from channels.session import get_session
    session = await get_session(phone)
    return session

