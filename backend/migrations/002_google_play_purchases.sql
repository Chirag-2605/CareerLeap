-- Idempotency ledger for Google Play consumable credit packs.
-- Purchase tokens are globally unique and must never grant credits twice.

CREATE TABLE IF NOT EXISTS google_play_purchases (
    purchase_token TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES user_wallets(user_id),
    product_id TEXT NOT NULL,
    credits_added INTEGER NOT NULL CHECK (credits_added > 0),
    order_id TEXT,
    purchase_time TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_google_play_purchases_user_created
    ON google_play_purchases (user_id, created_at DESC);
