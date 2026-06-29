import os
import json
import redis.asyncio as redis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Initialize Redis client pool
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

# In-memory fallback dictionary
_IN_MEMORY_SESSIONS = {}
_use_fallback = False

async def get_session(phone: str) -> dict:
    """
    Retrieve the session dictionary from Redis for the given phone number.
    Falls back to in-memory storage if Redis is unreachable.
    """
    global _use_fallback
    if _use_fallback:
        return _IN_MEMORY_SESSIONS.get(phone, {})
    try:
        session_data = await redis_client.get(phone)
        if session_data:
            return json.loads(session_data)
    except Exception as e:
        print(f"[Redis Session] Redis unavailable ({e}). Falling back to memory.")
        _use_fallback = True
        return _IN_MEMORY_SESSIONS.get(phone, {})
    return {}

async def update_session(phone: str, session: dict) -> None:
    """
    Save or update the session dictionary in Redis for the given phone number.
    Falls back to in-memory storage if Redis is unreachable.
    """
    global _use_fallback
    if _use_fallback:
        _IN_MEMORY_SESSIONS[phone] = session
        return
    try:
        await redis_client.set(phone, json.dumps(session))
    except Exception as e:
        print(f"[Redis Session] Redis unavailable ({e}). Falling back to memory.")
        _use_fallback = True
        _IN_MEMORY_SESSIONS[phone] = session

async def delete_session(phone: str) -> None:
    """
    Delete the session in Redis for the given phone number.
    Falls back to in-memory storage if Redis is unreachable.
    """
    global _use_fallback
    if _use_fallback:
        if phone in _IN_MEMORY_SESSIONS:
            del _IN_MEMORY_SESSIONS[phone]
        return
    try:
        await redis_client.delete(phone)
    except Exception as e:
        print(f"[Redis Session] Redis unavailable ({e}). Falling back to memory.")
        _use_fallback = True
        if phone in _IN_MEMORY_SESSIONS:
            del _IN_MEMORY_SESSIONS[phone]

