-- Migration: Add custom_watchlist_wallets table
-- Date: October 6, 2025
-- Purpose: Allow users to manually add specific wallets to monitor for confluence

CREATE TABLE IF NOT EXISTS custom_watchlist_wallets (
    address VARCHAR(100) NOT NULL,
    chain_id VARCHAR(20) NOT NULL,
    added_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    added_by VARCHAR(100) DEFAULT 'user',
    label VARCHAR(200),
    is_active BOOLEAN DEFAULT TRUE,
    notes TEXT,

    PRIMARY KEY (address, chain_id)
);

CREATE INDEX idx_custom_watchlist_active ON custom_watchlist_wallets(is_active);
CREATE INDEX idx_custom_watchlist_added ON custom_watchlist_wallets(added_at);

-- Example inserts (commented out):
-- INSERT INTO custom_watchlist_wallets (address, chain_id, label, notes)
-- VALUES ('0x1234...', 'ethereum', 'My favorite whale', 'Consistently profitable on meme coins');
