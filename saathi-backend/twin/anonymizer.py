import hmac
import hashlib
import os
from typing import Any, Dict

# A helper to encrypt/tokenise PII so LLM calls do not receive raw PII
def tokenize_customer_id(customer_id: str) -> str:
    """
    Generate a secure token for the customer ID using HMAC-SHA256.
    Same input always gives the same token.
    """
    key = os.getenv("PII_ENCRYPTION_KEY", "default-saathi-salt-key-12345")
    if isinstance(key, str):
        key = key.encode()
    return hmac.new(key, customer_id.encode(), hashlib.sha256).hexdigest()

def anonymize_context(context: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure no raw PII fields exist in the context before sending to the LLM.
    """
    anonymized = context.copy()
    # Remove any potential PII keys if they exist
    pii_keys = ["customer_id", "name", "phone", "email", "pan", "aadhaar"]
    for key in pii_keys:
        if key in anonymized:
            anonymized.pop(key)
    return anonymized

