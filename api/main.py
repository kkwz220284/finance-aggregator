from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from api.routers import accounts, offsets, transactions, truelayer
from app.db.session import engine


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    yield
    await engine.dispose()


app = FastAPI(
    title="Finance Aggregator",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(accounts.router, prefix="/api/v1", tags=["accounts"])
app.include_router(transactions.router, prefix="/api/v1", tags=["transactions"])
app.include_router(offsets.router, prefix="/api/v1", tags=["offsets"])
app.include_router(truelayer.router, prefix="/api/v1", tags=["truelayer"])


@app.get("/health", include_in_schema=False)
async def health():
    return {"status": "ok"}
