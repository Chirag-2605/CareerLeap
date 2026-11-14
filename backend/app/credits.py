from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List
from uuid import uuid4

import psycopg
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .google_play import verify_product_purchase

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
                    raise HTTPException(status_code=409, detail="This scan request is already reserved or has been processed.")
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
def get_balance(user: dict = Depends(require_user)) -> Dict[str, int]:
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
) -> Dict[str, List[Dict[str, Any]]]:
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


class GooglePlayPurchaseRequest(BaseModel):
    product_id: str = Field(min_length=1, max_length=100)
    purchase_token: str = Field(min_length=1, max_length=4096)


@router.post("/google-play/verify")
def verify_google_play_purchase(
    payload: GooglePlayPurchaseRequest,
    user: dict = Depends(require_user),
):
    """Verify a Play purchase and credit its wallet exactly once."""
    user_id = user["uid"]

    # A retry after the app has consumed the Play purchase must still be safe.
    with _connect() as conn:
        with conn.transaction():
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT user_id, credits_added
                    FROM google_play_purchases
                    WHERE purchase_token = %s
                    """,
                    (payload.purchase_token,),
                )
                existing = cur.fetchone()
                if existing:
                    if existing[0] != user_id:
                        raise HTTPException(status_code=409, detail="This purchase has already been linked to another account.")
                    cur.execute(
                        "SELECT balance, reserved_credits FROM user_wallets WHERE user_id = %s",
                        (user_id,),
                    )
                    wallet = cur.fetchone()
                    if not wallet:
                        raise HTTPException(status_code=409, detail="Credit wallet could not be found.")
                    return {
                        "credited": 0,
                        "already_processed": True,
                        "balance": wallet[0],
                        "available": wallet[0] - wallet[1],
                    }

    verified = verify_product_purchase(payload.product_id, payload.purchase_token, user_id)
    purchase_time = None
    if verified.get("purchase_time_millis"):
        from datetime import datetime, timezone
        purchase_time = datetime.fromtimestamp(
            int(verified["purchase_time_millis"]) / 1000,
            tz=timezone.utc,
        )

    with _connect() as conn:
        with conn.transaction():
            _ensure_wallet(conn, user_id)
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO google_play_purchases
                        (purchase_token, user_id, product_id, credits_added, order_id, purchase_time)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (purchase_token) DO NOTHING
                    RETURNING purchase_token
                    """,
                    (
                        payload.purchase_token,
                        user_id,
                        verified["product_id"],
                        verified["credits"],
                        verified.get("order_id"),
                        purchase_time,
                    ),
                )
                inserted = cur.fetchone()
                if not inserted:
                    cur.execute(
                        "SELECT user_id FROM google_play_purchases WHERE purchase_token = %s",
                        (payload.purchase_token,),
                    )
                    existing_user = cur.fetchone()
                    if not existing_user or existing_user[0] != user_id:
                        raise HTTPException(status_code=409, detail="This purchase has already been linked to another account.")
                    cur.execute(
                        "SELECT balance, reserved_credits FROM user_wallets WHERE user_id = %s",
                        (user_id,),
                    )
                    wallet = cur.fetchone()
                    return {
                        "credited": 0,
                        "already_processed": True,
                        "balance": wallet[0],
                        "available": wallet[0] - wallet[1],
                    }

                cur.execute(
                    """
                    UPDATE user_wallets
                    SET balance = balance + %s, updated_at = NOW()
                    WHERE user_id = %s
                    """,
                    (verified["credits"], user_id),
                )
                cur.execute(
                    """
                    INSERT INTO credit_transactions
                        (user_id, amount, transaction_type, reference_id, idempotency_key)
                    VALUES (%s, %s, 'PURCHASE', %s, %s)
                    """,
                    (
                        user_id,
                        verified["credits"],
                        verified.get("order_id") or "google-play-credit-pack",
                        "google-play-purchase:" + payload.purchase_token,
                    ),
                )
                cur.execute(
                    "SELECT balance, reserved_credits FROM user_wallets WHERE user_id = %s",
                    (user_id,),
                )
                wallet = cur.fetchone()

    return {
        "credited": verified["credits"],
        "already_processed": False,
        "balance": wallet[0],
        "available": wallet[0] - wallet[1],
    }
