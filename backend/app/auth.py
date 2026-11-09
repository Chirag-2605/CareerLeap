from __future__ import annotations

from typing import Optional
import json
from functools import lru_cache
from fastapi import Header, HTTPException
from .config import settings

@lru_cache(maxsize=1)
def _firebase_app():
    import firebase_admin
    from firebase_admin import credentials
    try:
        return firebase_admin.get_app()
    except ValueError:
        raw = settings.firebase_service_account_json
        if raw:
            cred = credentials.Certificate(json.loads(raw))
        else:
            # Uses GOOGLE_APPLICATION_CREDENTIALS / application default credentials.
            cred = credentials.ApplicationDefault()
        return firebase_admin.initialize_app(cred)


async def require_user(authorization: Optional[str] = Header(default=None)) -> dict:
    if not settings.auth_required:
        return {"uid": "local-development-user", "email": "local@example.test"}
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Sign in is required to scan a resume.")
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token.")
    try:
        from firebase_admin import auth
        decoded = auth.verify_id_token(token, app=_firebase_app(), check_revoked=True)
        return {"uid": decoded["uid"], "email": decoded.get("email")}
    except Exception:
        raise HTTPException(status_code=401, detail="Your session is invalid or expired. Please sign in again.")
