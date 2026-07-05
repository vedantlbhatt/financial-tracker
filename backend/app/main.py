import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.database import engine, Base, AsyncSessionLocal
from app.routers import simplefin, accounts, transactions, categories, cash_flow, overview, settings
from app.services.category_service import seed_merchant_rules
from app.services.local_setup import ensure_local_ready
from app.workers.sync_worker import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app_settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting Finance Tracker API...")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as db:
        await seed_merchant_rules(db)
        await ensure_local_ready(db)
        await db.commit()
    start_scheduler()
    yield
    stop_scheduler()
    await engine.dispose()
    logger.info("Finance Tracker API shut down")


app = FastAPI(
    title="Finance Tracker API",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=app_settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(simplefin.router)
app.include_router(accounts.router)
app.include_router(transactions.router)
app.include_router(categories.router)
app.include_router(cash_flow.router)
app.include_router(overview.router)
app.include_router(settings.router)


@app.get("/health")
async def health():
    return {"status": "ok", "provider": "simplefin"}
