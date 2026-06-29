from typing import TypedDict, Optional, List
from enum import Enum

class ConversationStage(str, Enum):
    TRIGGERED = "triggered"
    LIFE_EVENT_IDENTIFIED = "life_event_identified"
    PRODUCT_RECOMMENDED = "product_recommended"
    AWAITING_CONSENT = "awaiting_consent"
    CONSENT_VERIFIED = "consent_verified"
    COMPLETED = "completed"
    OPTED_OUT = "opted_out"

class SAATHIState(TypedDict):
    # Customer context (anonymized)
    customer_token: str            # Pseudonymized identifier (e.g. hashed/tokenized customer ID)
    language_code: str             # "hi", "mr", "ta", "te", "bn"
    income_tier: str               # "entry" | "mid" | "high"
    risk_score: int                # 1-10, derived from behavior
    
    # Event data
    trigger_type: str              # "salary_credit" | "emi_cleared" | "high_travel_spend" | etc.
    trigger_amount: float
    account_balance: float
    
    # Agent outputs
    life_event_tag: Optional[str]
    recommended_products: Optional[List[dict]]
    conversation_messages: List[dict]
    
    # Execution payload
    selected_product: Optional[dict]
    execution_payload: Optional[dict]
    
    # State tracking
    stage: ConversationStage
    consent_obtained: bool
    audit_trail: List[dict]
