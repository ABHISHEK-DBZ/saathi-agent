from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class DashboardStats(BaseModel):
    total_triggered: int
    in_conversation: int
    converted: int
    opted_out: int

class EventSummary(BaseModel):
    event_id: str
    trigger_type: Optional[str]
    life_event_tag: Optional[str]
    product_id: Optional[str]
    consent_method: Optional[str]
    created_at: datetime

class EventDetail(BaseModel):
    event_id: str
    customer_token: str
    trigger_type: Optional[str]
    life_event_tag: Optional[str]
    product_id: Optional[str]
    agent_chain: List[str]
    rationale: Optional[str]
    consent_obtained: bool
    consent_method: Optional[str]
    consent_at: Optional[datetime]
    timestamp: str
    integrity_hash: str
    conversation_messages: Optional[List[dict]] = None
