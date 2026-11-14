from __future__ import annotations

from datetime import datetime
from typing import Any

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query

from .auth import require_user
from .config import settings

router = APIRouter(prefix="/api/v1/credits", tags=["credits"])


def _connect():
    if not settings.database_url:
        raise HTTPException(status_code=503, detail="Credits are not configured yet.")
    try:
        return psycopg.connect(settings.database_url, connect_timeout=5)
    except Exception:
        raise HTTPException(status_code=503, detail="Credit service is temporarily unavailable.")


def _ensure_wallet(conn, user_id: str) -> None:
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO user_wallets (user_id, balance, reserved_credits)
            VALUES (%s, 3, 0)
            ON CONFLICT (user_id) DO NOTHING
            RETURNING user_id
            """,
            (user_id,),
        )
        created = cur.fetchone() is not None
        if created:
            cur.execute(
                """
                INSERT INTO credit_transactions
                    (user_id, amount, transaction_type, reference_id, idempotency_key)
                VALUES (%s, 3, 'FREE_GRANT', 'initial-free-credits', %s)
                """,
                (user_id, "free-grant:" + user_id),
            )


@router.get("/balance")
def get_balance(user: dict = Depends(require_user)) -> dict[str, int]:
    with _connect() as conn:
        with conn.transaction():
            _ensure_wallet(conn, user["uid"])
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT balance, reserved_credits FROM user_wallets WHERE user_id = %s",
                    (user["uid"],),
                )
                row = cur.fetchone()
    return {"balance": row[0], "reserved": row[1], "available": row[0] - row[1]}


@router.get("/transactions")
def get_transactions(
    limit: int = Query(default=25, ge=1, le=100),
    user: dict = Depends(require_user),
) -> dict[str, list[dict[str, Any]]]:
    with _connect() as conn:
        with conn.transaction():
            _ensure_wallet(conn, user["uid"])
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, amount, transaction_type, reference_id, created_at
                    FROM credit_transactions
                    WHERE user_id = %s
                    ORDER BY created_at DESC, id DESC
                    LIMIT %s
                    """,
                    (user["uid"], limit),
                )
                rows = cur.fetchall()
    return {
        "transactions": [
            {
                "id": row[0],
                "amount": row[1],
                "type": row[2],
                "reference_id": row[3],
                "created_at": row[4].isoformat() if isinstance(row[4], datetime) else row[4],
            }
            for row in rows
        ]
    }
