import os
import datetime
from anthropic import AsyncAnthropic
from graph.state import SAATHIState

# Initialize Anthropic Async client
client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", "mock-key"))

# Hardcoded exact template for Ramesh (new_professional + hi) and other translations for salary credit flow
LANGUAGE_TEMPLATES = {
    "new_professional": {
        "hi": """Ramesh ji 🙏 Aapki ₹{amount} ki salary aayi. Badhai ho!

Aapke account mein ₹{balance} hain aur koi investment nahi hai.
Sirf ₹{recommended_amount}/month se {product_name} shuru karein:

  {tenure_months} mahine mein → ₹{maturity_amount}+ ({interest_rate}% byaaj)
  Kabhi bhi band kar sakte hain

Shuru karna chahenge?
  1️⃣ Haan, abhi shuru karo
  2️⃣ Kal yaad dilao
  3️⃣ Nahi chahiye""",
        
        "mr": """नमस्कार 🙏 तुमची ₹{amount} ची पगार जमा झाली!

तुमच्या खात्यात ₹{balance} आहेत, पण गुंतवणूक नाही.
फक्त ₹{recommended_amount}/महिन्याने {product_name} सुरू करा:

  {tenure_months} महिन्यांत → ₹{maturity_amount}+ ({interest_rate}% व्याज)

सुरू करायचे का?
  1️⃣ हो, आत्ता सुरू करा
  2️⃣ उद्या आठवण द्या
  3️⃣ नको""",
        
        "en": """Hello! 🙏 Your salary of ₹{amount} has been credited.

Your account balance is ₹{balance} with no active investments.
Start {product_name} with just ₹{recommended_amount}/month:

  In {tenure_months} months → ₹{maturity_amount}+ ({interest_rate}% interest)
  Cancel anytime

Would you like to start?
  1️⃣ Yes, start now
  2️⃣ Remind me tomorrow
  3️⃣ Not interested"""
    }
}

MANDATORY_DISCLOSURE = """

*Investments are subject to market risks. Please read offer document carefully.
To stop messages: reply STOP.
SBI Reg: SBI-WA-2026-9912*"""

LANGUAGE_NAMES = {
    "hi": "Hindi",
    "mr": "Marathi",
    "ta": "Tamil",
    "te": "Telugu",
    "bn": "Bengali",
    "en": "English"
}

async def adapt_language(state: SAATHIState) -> SAATHIState:
    """
    Language Adapter Agent.
    Formulates vernacular WhatsApp messages using templates or Claude for dynamic messages.
    """
    lang = state.get("language_code", "hi")
    life_event = state["life_event_tag"]
    product = state["recommended_products"][0] if state["recommended_products"] else {}
    
    # Calculate maturity amount deterministically: amount * months * (1 + rate/100)
    rate = product.get("interest_rate", 5.5) or 5.5
    recommended_amount = product.get("recommended_amount", 500)
    tenure_months = product.get("tenure_months", 12)
    maturity = recommended_amount * tenure_months * (1 + rate / 100)
    
    amount_str = f"{state['trigger_amount']:,.0f}"
    balance_str = f"{state['account_balance']:,.0f}"
    maturity_str = f"{maturity:,.0f}"
    
    message = None
    
    # 1. Check if we have a matching template
    if life_event in LANGUAGE_TEMPLATES and lang in LANGUAGE_TEMPLATES[life_event]:
        template = LANGUAGE_TEMPLATES[life_event][lang]
        message = template.format(
            amount=amount_str,
            balance=balance_str,
            recommended_amount=recommended_amount,
            product_name=product.get("product_name"),
            tenure_months=tenure_months,
            maturity_amount=maturity_str,
            interest_rate=str(rate)
        )
    
    # 2. If no template exists, call Claude to generate a localized message
    if message is None:
        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        lang_name = LANGUAGE_NAMES.get(lang, "English")
        
        if api_key and not api_key.startswith("your-") and not api_key == "mock-key":
            system_prompt = f"""
            You are a helpful language localization agent for SBI bank.
            Create a warm, professional, and clear WhatsApp message in {lang_name} for the customer.
            
            Rules:
            1. Use a respectful tone (e.g., use 'ji' for Hindi/Marathi/Indian contexts).
            2. For salary credits, start with a congratulations/celebration.
            3. Present the recommended product details: {product.get('product_name')}, recommended monthly saving amount ₹{recommended_amount}, tenure {tenure_months} months, maturity ₹{maturity_str} (at interest rate {rate}%).
            4. Display the current account balance (₹{balance_str}) and trigger amount (₹{amount_str}).
            5. End with exactly 3 numbered choice options:
               1️⃣ Yes, start now
               2️⃣ Remind me tomorrow
               3️⃣ Not interested
               
            Respond ONLY with the WhatsApp message content, no other text or explanation. Do not append any disclosures.
            """
            try:
                response = await client.messages.create(
                    model="claude-3-5-sonnet-20241022",
                    max_tokens=400,
                    system=system_prompt,
                    messages=[{"role": "user", "content": "Generate the localized message."}],
                    temperature=0.0
                )
                message = response.content[0].text.strip()
            except Exception as e:
                print(f"[Language Adapter] Claude translation failed ({e}). Using English fallback template.")
                
        if message is None:
            # Fallback to English template if Claude fails or key is missing
            template = LANGUAGE_TEMPLATES["new_professional"]["en"]
            message = template.format(
                amount=amount_str,
                balance=balance_str,
                recommended_amount=recommended_amount,
                product_name=product.get("product_name"),
                tenure_months=tenure_months,
                maturity_amount=maturity_str,
                interest_rate=str(rate)
            )
            
    # 3. Always append the mandatory regulatory disclosure
    full_message = message + MANDATORY_DISCLOSURE
    
    state["conversation_messages"].append({
        "direction": "outbound",
        "content": full_message,
        "language": lang
    })
    
    # Update stage
    state["stage"] = "awaiting_consent"
    
    # 4. Append to audit trail
    state["audit_trail"].append({
        "agent": "language_adapter",
        "output": {
            "language": lang,
            "message_length": len(full_message),
            "templated": (life_event in LANGUAGE_TEMPLATES and lang in LANGUAGE_TEMPLATES[life_event])
        },
        "timestamp": datetime.datetime.utcnow().isoformat()
    })
    
    return state
