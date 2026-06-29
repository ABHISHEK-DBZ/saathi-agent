import os
import asyncio
import asyncpg
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Load environmental variables
load_dotenv()

from channels.whatsapp import router as whatsapp_router
from channels.webhook_router import router as webhook_router
from api.dashboard import router as dashboard_router

# Initialize database pool globally
db_pool = None

app = FastAPI(
    title="SAATHI API",
    description="Backend API for SAATHI - Vernacular Proactive Financial Inclusion Agent",
    version="1.0.0"
)

# CORS middleware to allow all origins for easy dashboard development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers
app.include_router(whatsapp_router, tags=["WhatsApp"])
app.include_router(webhook_router, tags=["Core Webhooks"])
app.include_router(dashboard_router, tags=["Dashboard"])

@app.on_event("startup")
async def startup_event():
    """
    On application startup:
    1. Initialize the WebSocket event broadcaster background loop.
    2. Establish the PostgreSQL connection pool.
    3. Auto-execute migrations/table setup.
    """
    # 1. Start the WebSocket broadcaster daemon task
    from api.dashboard import event_broadcaster
    asyncio.create_task(event_broadcaster())
    
    # 2. Setup PostgreSQL Pool and verify audit_log table
    global db_pool
    database_url = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/saathi")
    
    try:
        db_pool = await asyncpg.create_pool(database_url)
        async with db_pool.acquire() as conn:
            await conn.execute("""
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
        print("[Startup] Database pool connected and audit_log table verified.")
    except Exception as e:
        print(f"[Startup] Database connection failed ({e}). Database logs will fall back to local mode.")
        db_pool = None

@app.on_event("shutdown")
async def shutdown_event():
    """
    Close the database pool on application shutdown.
    """
    global db_pool
    if db_pool is not None:
        await db_pool.close()
        print("[Shutdown] Closed database connection pool.")

@app.get("/")
async def root():
    """
    Health check endpoint.
    """
    return {"status": "ok", "service": "SAATHI"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
