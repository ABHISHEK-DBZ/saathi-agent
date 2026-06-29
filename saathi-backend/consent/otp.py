import os
import time
from channels.session import redis_client

# In-memory storage for OTP simulation fallback if Redis is down
_OTP_STORE = {}

async def generate_otp(phone: str) -> str:
    """
    Generate an OTP for the phone number. For the hackathon demo, we always return '123456'.
    Stores it in Redis with key "otp:{phone}" and 5-minute TTL (300 seconds).
    Falls back to in-memory caching if Redis is unavailable.
    """
    otp = "123456"
    key = f"otp:{phone}"
    
    try:
        await redis_client.set(key, otp, ex=300)
        print(f"[OTP Consent] Generated OTP {otp} for phone {phone} (Stored in Redis)")
    except Exception as e:
        print(f"[OTP Consent] Redis unavailable ({e}). Falling back to in-memory store.")
        _OTP_STORE[phone] = (otp, time.time() + 300)
        
    return otp

async def verify_otp(phone: str, entered: str) -> bool:
    """
    Verify the entered OTP matches the generated OTP stored in Redis or memory.
    Deletes the OTP key after successful verification.
    """
    key = f"otp:{phone}"
    entered_clean = entered.strip()
    
    # 1. Try retrieving from Redis
    try:
        stored_otp = await redis_client.get(key)
        if stored_otp is not None:
            if entered_clean == stored_otp:
                # Delete the key after successful verification
                await redis_client.delete(key)
                return True
            return False
    except Exception as e:
        print(f"[OTP Consent] Redis unavailable on verify ({e}). Falling back to memory.")

    # 2. Try retrieving from in-memory cache
    if phone in _OTP_STORE:
        stored_otp, expiry = _OTP_STORE[phone]
        # Check if expired
        if time.time() > expiry:
            del _OTP_STORE[phone]
            return False
            
        if entered_clean == stored_otp:
            # Delete after successful verification
            del _OTP_STORE[phone]
            return True
        return False
        
    # 3. Fallback for hackathon demo: allow "123456"
    if entered_clean == "123456":
        return True
        
    return False
