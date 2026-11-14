-- Apply once to the Neon PostgreSQL database before enabling credit endpoints.
-- Keep this migration additive; it does not alter analyzer data or Firebase identities.

CREATE TABLE IF NOT EXISTS user_wallets (
    user_id TEXT PRIMARY KEY,
    balance INTEGER NOT NULL DEFAULT 0 CHECK (balance >= 0),
    reserved_credits INTEGER NOT NULL DEFAULT 0 CHECK (reserved_credits >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CHECK (reserved_credits <= balance)
);

CREATE TABLE IF NOT EXISTS credit_transactions (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
    amount INTEGER NOT NULL CHECK (amount <> 0),
    transaction_type TEXT NOT NULL CHECK (
        transaction_type IN ('FREE_GRANT', 'PURCHASE', 'SCAN_DEBIT', 'REFUND', 'ADJUSTMENT')
    ),
    reference_id TEXT,
    idempotency_key TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_credit_transactions_idempotency UNIQUE (user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_credit_transactions_user_created
    ON credit_transactions (user_id, created_at DESC, id DESC);

CREATE TABLE IF NOT EXISTS scan_credit_reservations (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('RESERVED', 'COMMITTED', 'RELEASED')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT uq_scan_reservation_user_key UNIQUE (user_id, idempotency_key)
);

CREATE INDEX IF NOT EXISTS ix_scan_reservations_user_status
    ON scan_credit_reservations (user_id, status);
