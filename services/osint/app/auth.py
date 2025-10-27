from fastapi import Header, HTTPException
from .config import settings


def require_token(x_api_token: str | None = Header(default=None)):
    if not settings.api_token:
        return  # allow if not set (dev only)
    if not x_api_token or x_api_token != settings.api_token:
        raise HTTPException(status_code=401, detail="Unauthorized")


