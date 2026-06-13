import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text

from app.api.admin.farmers import router as admin_farmers_router
from app.api.admin.funds import router as admin_funds_router
from app.api.admin.loans import router as admin_loans_router
from app.api.admin.oversight import router as admin_oversight_router
from app.api.auth import router as auth_router
from app.api.commodities import router as commodities_router
from app.api.farmers import router as farmers_router
from app.api.intakes import router as intakes_router
from app.api.koperasi import router as koperasi_router
from app.api.loans import router as farmer_loans_router
from app.api.notifications import router as notifications_router
from app.api.orders import router as orders_router
from app.api.reports import router as reports_router
from app.core.config import settings
from app.db.engine import engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.connect() as conn:
            version = (await conn.execute(text("SELECT version()"))).scalar()
            logger.info("DB connected: %s", version)
    except Exception as exc:
        logger.exception("DB probe failed at startup — continuing anyway: %s", exc)
    yield
    await engine.dispose()


app = FastAPI(title="KoperaLink API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


app.include_router(auth_router)
app.include_router(admin_farmers_router)
app.include_router(admin_funds_router)
app.include_router(admin_loans_router)
app.include_router(admin_oversight_router)
app.include_router(farmer_loans_router)
app.include_router(farmers_router)
app.include_router(intakes_router)
app.include_router(orders_router)
app.include_router(commodities_router)
app.include_router(koperasi_router)
app.include_router(notifications_router)
app.include_router(reports_router, prefix="/reports")


@app.get("/health")
async def health():
    return {"status": "ok", "mode": settings.MODE}


@app.get("/readiness")
async def readiness():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception as exc:
        logger.warning("Readiness check failed: %s", exc)
        return JSONResponse(status_code=503, content={"status": "unavailable", "detail": str(exc)})
