CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    last_seen_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS watchlists (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, symbol)
);

CREATE TABLE IF NOT EXISTS user_session_snapshots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    symbol TEXT NOT NULL,
    price NUMERIC(18, 4),
    volume BIGINT,
    rsi NUMERIC(8, 4),
    nifty_price NUMERIC(18, 4),
    sector_price NUMERIC(18, 4),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS signals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    symbol TEXT NOT NULL,
    attention_score NUMERIC(8, 4) NOT NULL,
    priority TEXT NOT NULL,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_watchlists_user_id ON watchlists (user_id);
CREATE INDEX IF NOT EXISTS idx_watchlists_symbol ON watchlists (symbol);
CREATE INDEX IF NOT EXISTS idx_snapshots_user_symbol ON user_session_snapshots (user_id, symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_symbol_created ON signals (symbol, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_signals_priority ON signals (priority, created_at DESC);
