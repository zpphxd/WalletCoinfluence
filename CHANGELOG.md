# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- **Sell Detection in AlchemyClient**: `get_wallet_transactions` now detects SELL trades in addition to BUY trades
  - Queries both `toAddress` (receives tokens = BUY) and `fromAddress` (sends tokens = SELL)
  - Uses the same DEX pool heuristic (addresses with multiple transfers) for both buy and sell detection
  - Returns transactions with correct `"type": "buy"` or `"type": "sell"` field
  - Calculates USD value using DexScreener prices for both buy and sell transactions
  - Enables accurate PnL calculation by matching buy and sell trades

### Changed
- **AlchemyClient.get_wallet_transactions**: Method now returns both buys and sells instead of only buys
  - Makes two separate API queries: one for incoming transfers (buys), one for outgoing transfers (sells)
  - Improved logging to show count of buys and sells fetched

### Technical Details
- DEX pool detection: Addresses that appear >1 time in transfers are identified as DEX pools
- For buys: Transfer FROM DEX pool TO wallet
- For sells: Transfer FROM wallet TO DEX pool
- Each transaction includes: tx_hash, timestamp, type (buy/sell), token_address, amount, price_usd, value_usd, dex

### Impact
- PnL calculations will now properly match sell trades with buy trades
- Wallets with realized profits will be correctly identified
- Better tracking of trader behavior (entry and exit points)
