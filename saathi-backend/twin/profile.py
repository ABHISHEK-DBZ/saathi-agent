import os
from twin.anonymizer import tokenize_customer_id

def get_demo_phone() -> str:
    """
    Get the configured WhatsApp test phone number from the environment,
    with fallbacks if not defined.
    """
    return (
        os.getenv("WHATSAPP_TEST_PHONE")
        or os.getenv("WHATSAPP_RECIPIENT_PHONE")
        or "919999999999"
    )

# Hardcoded demo profiles
DEMO_PROFILES = {
    "TOKEN-RAMESH": {
        "language": "hi",
        "language_code": "hi",
        "income_tier": "entry",
        "risk_score": 2,
        "whatsapp": get_demo_phone(),
        "whatsapp_number": get_demo_phone(),
        "name": "Ramesh Kumar"
    },
    "TOKEN-PRIYA": {
        "language": "mr",
        "language_code": "mr",
        "income_tier": "mid",
        "risk_score": 5,
        "whatsapp": get_demo_phone(),
        "whatsapp_number": get_demo_phone(),
        "name": "Priya Deshpande"
    },
    "TOKEN-ARUN": {
        "language": "ta",
        "language_code": "ta",
        "income_tier": "mid",
        "risk_score": 4,
        "whatsapp": get_demo_phone(),
        "whatsapp_number": get_demo_phone(),
        "name": "Arun Krishnamurthy"
    }
}

async def get_or_create_twin(customer_token: str) -> dict:
    """
    Retrieve a financial digital twin profile matching the given token.
    Resolves using direct lookup, original customer ID, or dynamic token match.
    Falls back to a default entry-level profile if not found.
    """
    # Dynamic profile resolution updates the phone number on read
    for key in DEMO_PROFILES:
        DEMO_PROFILES[key]["whatsapp"] = get_demo_phone()
        DEMO_PROFILES[key]["whatsapp_number"] = get_demo_phone()

    # 1. Direct token key match (e.g. "TOKEN-RAMESH")
    if customer_token in DEMO_PROFILES:
        return DEMO_PROFILES[customer_token]

    # 2. Dynamic check matching the HMAC tokens of customer IDs
    ramesh_token = tokenize_customer_id("DEMO-RAMESH-001")
    priya_token = tokenize_customer_id("DEMO-PRIYA-002")
    arun_token = tokenize_customer_id("DEMO-ARUN-003")

    if customer_token == ramesh_token or customer_token == "DEMO-RAMESH-001":
        return DEMO_PROFILES["TOKEN-RAMESH"]
    elif customer_token == priya_token or customer_token == "DEMO-PRIYA-002":
        return DEMO_PROFILES["TOKEN-PRIYA"]
    elif customer_token == arun_token or customer_token == "DEMO-ARUN-003":
        return DEMO_PROFILES["TOKEN-ARUN"]

    # 3. Fallback entry profile
    return {
        "language": "hi",
        "language_code": "hi",
        "income_tier": "entry",
        "risk_score": 3,
        "whatsapp": get_demo_phone(),
        "whatsapp_number": get_demo_phone(),
        "name": "Default Guest"
    }
