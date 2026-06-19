"""
API key authentication for admin-only endpoints.

In a production SaaS context, replace with OAuth2 / JWT.
For now, a static API key header provides basic protection for seed/admin operations.
"""
from __future__ import annotations

from fastapi import HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.core.config import settings

_api_key_header = APIKeyHeader(name="X-Admin-API-Key", auto_error=False)


async def require_admin_key(api_key: str | None = Security(_api_key_header)) -> str:
    """
    FastAPI dependency — validates the X-Admin-API-Key header.

    Usage:
        @router.post("/admin/seed", dependencies=[Depends(require_admin_key)])
    """
    if not api_key or api_key != settings.ADMIN_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key. Provide X-Admin-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return api_key
