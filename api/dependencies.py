from collections.abc import AsyncGenerator

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db.session import AsyncSessionLocal

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


async def require_api_key(key: str | None = Security(_api_key_header)) -> None:
    if key != get_settings().api_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
