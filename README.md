# SAATHI: Vernacular Proactive Financial Inclusion Agent

SAATHI is an AI-powered, vernacular, proactive financial inclusion agent designed to bridge the digital divide for underserved Indian rural/sub-urban communities. Integrated with core banking webhooks and Meta's WhatsApp Business API, SAATHI uses an agentic LangGraph workflow to detect critical customer life events and dynamically recommend tailored, micro-targeted financial products (savings, micro-loans, insurance, and retirement plans) with an explainable, auditable RBI-compliant consent mechanism.

---

## 🛠️ Prerequisites

Ensure you have the following installed on your system:
- **Python 3.11+**
- **Node.js 18+** (with npm)
- **Docker & Docker Compose**
- An **Anthropic API Key** (for agent reasoning & translation)
- A **Meta Developer Account** with WhatsApp Business API configured (for live messaging)

---

## 🚀 Setup & Installation

Follow these steps to get SAATHI running locally:

### 1. Configure the Environment
Go to the backend directory, duplicate the environment template, and fill in the required keys:
```bash
cd saathi-backend
cp .env.example .env
```
Open `.env` and configure your `ANTHROPIC_API_KEY`, WhatsApp API credentials, and target test number.

### 2. Start PostgreSQL and Redis Containers
Launch the required database and cache containers in the background:
```bash
docker-compose up -d
```
This runs:
- **PostgreSQL (Port 5432)**: Stores compliance audit logs.
- **Redis (Port 6379)**: Tracks active customer sessions and OTP verification caches.

### 3. Install Backend Dependencies
We recommend setting up a virtual environment first:
```bash
python -m venv .venv
# On Windows (PowerShell):
.venv\Scripts\Activate.ps1
# On Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt
```

### 4. Ingest Product Knowledge
Run the vector database ingestion script. This embeds the financial product catalog and saves it in ChromaDB:
```bash
python knowledge/ingest.py
```

### 5. Launch the FastAPI Backend
Start the backend API server:
```bash
uvicorn main:app --reload --port 8000
```
The backend API is now live at `http://localhost:8000`. You can inspect the interactive OpenAPI documentation at `http://localhost:8000/docs`.

### 6. Install & Launch the Frontend Dashboard
In a new terminal window, navigate to the frontend folder, install dependencies, and launch the Vite development server:
```bash
cd saathi-frontend
npm install
npm run dev
```
Open your browser and navigate to `http://localhost:5173` (or the URL outputted by Vite) to view the SAATHI Compliance and Control Dashboard.

---

## 🎭 Running the Demo (3 Scenarios)

The dashboard control panel lets you trigger simulations for three specific persona profiles to see how the agent adapts to income, language, and risk variations:

### Scenario 1: Ramesh Kumar (Rural New Professional)
- **Customer ID**: `DEMO-RAMESH-001`
- **Language**: Hindi (`hi`)
- **Income Tier**: Entry
- **Risk Score**: 2 (Conservative)
- **Trigger event**: Salary Credit of **₹28,000** (creating a balance of ₹41,000)
- **Expected Outcome**: The agent predicts a **"new_professional"** life event. It recommends a **Recurring Deposit (RD)** as a disciplined savings habit, translating the entire outreach message and consent flow into Hindi (e.g. *"Badhai ho!..."*).

### Scenario 2: Priya Deshpande (Urban Sub-Urban Merchant)
- **Customer ID**: `DEMO-PRIYA-002`
- **Language**: Marathi (`mr`)
- **Income Tier**: Mid
- **Risk Score**: 5 (Moderate)
- **Trigger event**: Merchant Salary/Credit of **₹15,500** (creating a balance of ₹89,000)
- **Expected Outcome**: The agent predicts a **"wealth_accumulation"** target. It recommends an **Equity Hybrid Mutual Fund** to beat inflation, translating the outreach message and transaction steps into Marathi.

### Scenario 3: Arun Krishnamurthy (Retiring Senior Citizen)
- **Customer ID**: `DEMO-ARUN-003`
- **Language**: Tamil (`ta`)
- **Income Tier**: Mid
- **Risk Score**: 4 (Moderate-Conservative)
- **Trigger event**: Large Credit/Gratuity of **₹45,000** (creating a balance of ₹1,25,000)
- **Expected Outcome**: The agent predicts a **"retirement_planning"** or **"senior_citizen"** threshold. It recommends the **Senior Citizens Savings Scheme (SCSS)**, translating the outreach, features, and consent prompts into Tamil.

---

## ⚡ Programmatic Test Execution

You can run the end-to-end webhook integration, dashboard update, and Redis message queuing flow programmatically using the provided test script:
```bash
cd saathi-backend
python test_demo.py
```
This script will:
1. Fire a transaction webhook to `/webhook/transaction` representing Ramesh Kumar's salary credit.
2. Poll `/dashboard/events` every second for 10 seconds to detect processing.
3. Call `/dashboard/event/{event_id}` to print the exact nodes executed in the LangGraph workflow (`supervisor` -> `life_event_predictor` -> `product_recommender` -> `language_adapter`) and print the generated XAI audit rationale.
4. Retrieve the active session from Redis to confirm the WhatsApp message has been compiled and queued for delivery.

---

## 🌐 Exposing the Webhook for WhatsApp (ngrok)

To receive incoming replies (OTP confirmations, menu clicks) from users on their mobile phones back into your local backend, Meta requires an HTTPS endpoint. Use `ngrok` to tunnel traffic securely:

1. Download and authenticate ngrok, then run:
   ```bash
   ngrok http 8000
   ```
2. Copy the secure forwarding URL (e.g., `https://xxxx-xx-xx-xx.ngrok-free.app`).
3. Set your webhook endpoints on Meta Developer Portal to:
   - **Webhook URL**: `https://xxxx-xx-xx-xx.ngrok-free.app/webhook/whatsapp`
   - **Verify Token**: Input the value of your `WHATSAPP_WEBHOOK_VERIFY_TOKEN` (from `.env`).
4. Select the **messages** subscription field under Webhook settings to ensure incoming text replies are sent to SAATHI.

---

## 🔑 Environment Variables Explained

SAATHI uses environment variables to adjust its execution behavior. Here is a summary of the keys defined in `saathi-backend/.env`:

| Key | Description | Example Value |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | Developer API key from Anthropic. Used for LLM-based product recommendation, life-event prediction, and localization. | `sk-ant-api03-...` |
| `WHATSAPP_ACCESS_TOKEN` | Meta Developer authorization token used to post requests to the WhatsApp Cloud API. | `EAALx...` |
| `WHATSAPP_PHONE_NUMBER_ID` | Meta-assigned Phone Number ID for the test/sender profile sending WhatsApp messages. | `102938475610293` |
| `WHATSAPP_WEBHOOK_VERIFY_TOKEN` | A secret token you define. Meta passes this token during initial handshake verification. | `mySecretVerifyToken123` |
| `WHATSAPP_TEST_PHONE` | Recipient phone number (E.164 without prefix) to receive mock/test WhatsApp alerts in dev mode. | `919876543210` |
| `DATABASE_URL` | PostgreSQL database connection URI string. Used for storing RBI compliance event records. | `postgresql://postgres:postgres@localhost:5432/saathi` |
| `REDIS_URL` | Redis cache connection URI string. Used for tracking active conversation sessions and OTP states. | `redis://localhost:6379` |
| `SECRET_KEY` | Session signing key used for backend API encryption features. | `random_session_secret_hash` |
| `PII_ENCRYPTION_KEY` | Secret key used to encrypt customer IDs and other details before database tokenization. | `test-encryption-key-for-saathi-123` |
| `ENV` | Environment state configuration. Dictates strict validation levels. (`development` / `production`). | `development` |
