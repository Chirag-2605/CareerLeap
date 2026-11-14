from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import uuid4

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


def reserve_scan_credit(user_id: str, idempotency_key: str) -> str:
    """Reserve one available credit under a row lock; retries reuse the same reservation."""
    if not idempotency_key or len(idempotency_key) > 200:
        raise HTTPException(status_code=400, detail="A valid Idempotency-Key header is required.")
    with _connect() as conn:
        with conn.transaction():
            _ensure_wallet(conn, user_id)
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, status FROM scan_credit_reservations WHERE user_id = %s AND idempotency_key = %s",
                    (user_id, idempotency_key),
                )
                existing = cur.fetchone()
                if existing:
                    if existing[1] == "RESERVED":
                        return str(existing[0])
                    raise HTTPException(status_code=409, detail="This scan request has already been processed.")
                cur.execute(
                    "SELECT balance, reserved_credits FROM user_wallets WHERE user_id = %s FOR UPDATE",
                    (user_id,),
                )
                balance, reserved = cur.fetchone()
                if balance - reserved < 1:
                    raise HTTPException(status_code=402, detail="No scan credits remaining.")
                reservation_id = str(uuid4())
                cur.execute(
                    """
                    INSERT INTO scan_credit_reservations (id, user_id, idempotency_key, status)
                    VALUES (%s, %s, %s, 'RESERVED')
                    """,
                    (reservation_id, user_id, idempotency_key),
                )
                cur.execute(
                    "UPDATE user_wallets SET reserved_credits = reserved_credits + 1, updated_at = NOW() WHERE user_id = %s",
                    (user_id,),
                )
    return reservation_id


def commit_scan_credit(user_id: str, reservation_id: str) -> None:
    with _connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM scan_credit_reservations WHERE id = %s AND user_id = %s FOR UPDATE",
                    (reservation_id, user_id),
                )
                row = cur.fetchone()
                if not row:
                    raise HTTPException(status_code=404, detail="Credit reservation not found.")
                if row[0] == "COMMITTED":
                    return
                if row[0] != "RESERVED":
                    raise HTTPException(status_code=409, detail="Credit reservation is no longer active.")
                cur.execute(
                    """
                    UPDATE user_wallets
                    SET balance = balance - 1, reserved_credits = reserved_credits - 1, updated_at = NOW()
                    WHERE user_id = %s AND balance >= 1 AND reserved_credits >= 1
                    """,
                    (user_id,),
                )
                if cur.rowcount != 1:
                    raise HTTPException(status_code=409, detail="Wallet state changed; scan credit was not charged.")
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (user_id, amount, transaction_type, reference_id, idempotency_key)
                    VALUES (%s, -1, 'SCAN_DEBIT', %s, %s)
                    ON CONFLICT (user_id, idempotency_key) DO NOTHING
                    """,
                    (user_id, reservation_id, "scan-debit:" + reservation_id),
                )
                cur.execute(
                    "UPDATE scan_credit_reservations SET status = 'COMMITTED', updated_at = NOW() WHERE id = %s",
                    (reservation_id,),
                )


def release_scan_credit(user_id: str, reservation_id: str) -> None:
    with _connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT status FROM scan_credit_reservations WHERE id = %s AND user_id = %s FOR UPDATE",
                    (reservation_id, user_id),
                )
                row = cur.fetchone()
                if not row or row[0] == "RELEASED":
                    return
                if row[0] == "COMMITTED":
                    return
                cur.execute(
                    """
                    UPDATE user_wallets
                    SET reserved_credits = reserved_credits - 1, updated_at = NOW()
                    WHERE user_id = %s AND reserved_credits >= 1
                    """,
                    (user_id,),
                )
                if cur.rowcount != 1:
                    raise HTTPException(status_code=409, detail="Wallet reservation state is inconsistent.")
                cur.execute(
                    "UPDATE scan_credit_reservations SET status = 'RELEASED', updated_at = NOW() WHERE id = %s",
                    (reservation_id,),
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
