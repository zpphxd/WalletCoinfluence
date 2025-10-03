# Alpha Wallet Scout - System Goal & Design

## 🎯 CORE GOAL

**Find profitable crypto whale wallets and alert when 2+ of them buy the same token within 30 minutes (confluence).**

The entire system exists to answer one question:
> **"When do multiple successful traders buy the same token at the same time?"**

When this happens, it's a strong buy signal - we alert the user immediately so they can buy too.

---

## 🏗️ HOW IT WORKS (4 Stages)

### Stage 1: DISCOVER TRENDING TOKENS (Every 5 min)
**Job**: `runner_seed_job()`
**What it does**: Fetches top 50 trending tokens per chain from GeckoTerminal
**Why**: These tokens are getting attention - likely where whales are trading
**Output**: ~60 tokens/run saved to `seed_tokens` table

### Stage 2: FIND WHALES BUYING THOSE TOKENS (Every 10 min)
**Job**: `wallet_discovery_job()` + `whale_discovery_job()`
**What it does**:
- For each trending token, fetch ALL buyers in last 16 hours (Alchemy API)
- Filter for DEX buys only (not transfers/migrations)
- Record each wallet address and their trade
- Fetch their complete 30-day trade history
- Calculate PnL, best trade multiple, EarlyScore

**Why**: We want to identify which wallets are WINNERS (profitable, good timing)
**Output**: ~84 wallets discovered with 122 trades tracked

### Stage 3: RANK TOP 30 WHALES (Every 15 min)
**Job**: `stats_rollup_job()` + `watchlist_maintenance_job()`
**What it does**:
- Calculate stats for all discovered wallets:
  - Realized PnL (sold positions)
  - Unrealized PnL (current open positions)
  - Best trade multiple (e.g., 4x return)
  - EarlyScore median (0-100, timing metric)
- Rank wallets by composite score:
  - 30% weight: Unrealized PnL (current position value)
  - 30% weight: Trade activity (more trades = more data)
  - 40% weight: EarlyScore (ability to buy early)
- Select TOP 30 WHALES ONLY

**Why**: We only want alerts from the BEST whales, not random traders
**Output**: Top 30 whale watchlist (e.g., wallet with $715 unrealized PnL, 4x return)

### Stage 4: MONITOR FOR CONFLUENCE (Every 2 min)
**Job**: `wallet_monitoring_job()`
**What it does**:
- For each of the TOP 30 whales:
  - Check Alchemy API for any new trades (last 100 transactions)
  - If they bought a token → record in Redis with timestamp
  - Check: Did ≥2 whales buy this SAME token within 30 minutes?
  - If YES → **SEND CONFLUENCE ALERT** to Telegram
  - If NO → do nothing (no single wallet alerts)

**Why**: Confluence = multiple smart traders agreeing on a trade = high probability
**Output**: Telegram alert with:
- Token contract address (to buy)
- Direct buy links (Uniswap, 1inch, etc.)
- All whale stats (PnL, best multiple, EarlyScore)
- Chart and explorer links

---

## 📊 EXAMPLE ALERT (Confluence)

```
🚨 CONFLUENCE (2 WHALES) 🚨

💰 TOKEN: PEPE ($0.00000123)
MCap: $450M | Liquidity: $2.5M

🔗 CONTRACT ADDRESS:
0x6982508145454ce325ddbe47a25d4ec3d2311933

🐋 WHALE #1:
Address: 0x9c22836e...
30D PnL: $715
Best Trade: 4.0x
Early Score: 47/100

🐋 WHALE #2:
Address: 0xe101e63e...
30D PnL: $523
Best Trade: 3.2x
Early Score: 52/100

⏰ Window: 12 minutes
📊 Avg 30D PnL: $619

🚀 QUICK BUY:
💎 Uniswap: https://app.uniswap.org/#/swap?outputCurrency=0x6982...
🔗 1inch: https://app.1inch.io/#/1/simple/swap/ETH/0x6982...

📊 Chart: https://dexscreener.com/ethereum/0x6982...
🔍 TX: https://etherscan.io/tx/0xabc123...
```

User sees this → Copies contract address → Buys on Uniswap → Profits when token pumps

---

## 🛡️ GUARDRAILS (Why We Don't Get Banned/Spammed)

### 1. Rate Limiting (DexScreener)
**Problem**: Hitting DexScreener API too fast = banned
**Solution**: 2-second delay between all DexScreener calls
**Impact**: Slightly slower data but no bans

### 2. Top 30 Whale Filter (Quality)
**Problem**: Too many wallets = too many alerts = noise
**Solution**: Only monitor the TOP 30 most profitable whales
**Impact**: Only get alerts from proven winners

### 3. Confluence-Only Alerts (Signal Quality)
**Problem**: Single wallet buys could be wrong/luck
**Solution**: ONLY alert when ≥2 whales buy same token within 30 min
**Impact**: Much higher win rate (multiple smart traders agreeing)

### 4. Profitable Whales Only (PnL Filter)
**Problem**: Some wallets are losers or bots
**Solution**: Only track wallets with unrealized_pnl_usd > $0
**Impact**: Only follow wallets that are currently making money

### 5. 16-Hour Lookback (Alchemy)
**Problem**: Too far back = stale data, too recent = miss early entries
**Solution**: 5000 blocks (~16 hours) for token transfers
**Impact**: Catch early buyers without drowning in old data

### 6. DEX Pool Detection (Buy Validation)
**Problem**: Not all transfers are buys (could be migrations, airdrops, etc.)
**Solution**: Heuristic detection of DEX pools (addresses sending tokens multiple times)
**Impact**: Only record real DEX buys, filter out noise

---

## 📈 SUCCESS METRICS

**Win Rate**: >60% of confluence alerts should pump within 24h
**Average Return**: >25% per alert
**Time to Pump**: <30 minutes (whale bought early, we buy shortly after)
**Alert Frequency**: 1-3 confluence alerts per day (not spam)

---

## 🔧 KEY PARAMETERS (Tunable)

```python
# Whale Selection
ADD_MIN_TRADES_30D = 1  # At least 1 trade in 30 days
ADD_MIN_REALIZED_PNL_30D_USD = -10000  # Can be negative (testing)
ADD_MIN_BEST_TRADE_MULTIPLE = 1.0  # At least 1x return

# Confluence Detection
CONFLUENCE_MINUTES = 30  # Window for multiple whales buying
MIN_WHALES_FOR_ALERT = 2  # Minimum 2 whales required

# Monitoring Frequency
RUNNER_SEED_JOB = 5 min  # Token ingestion
WHALE_DISCOVERY_JOB = 5 min  # Find whales making $10k+ trades
WALLET_DISCOVERY_JOB = 10 min  # Find all buyers of trending tokens
WALLET_MONITORING_JOB = 2 min  # Check top 30 whales for new trades
STATS_ROLLUP_JOB = 15 min  # Recalculate whale rankings

# API Rate Limits
DEXSCREENER_DELAY = 2.0 sec  # Prevent bans
ALCHEMY_LOOKBACK = 5000 blocks  # ~16 hours
```

---

## 🚀 NEXT STEPS (Production)

1. **Let system run for 4-6 hours** to build up whale pool
2. **Monitor logs** for confluence detection (`check_confluence()` calls)
3. **First real alert** should come when 2 top whales buy same token
4. **Track performance** with self-scoring system (rewards/punishments)
5. **Iterate on thresholds** based on win rate data

---

## 💡 WHY THIS WORKS

**The Edge**: We're not predicting pumps. We're FOLLOWING the smart money.

Once a wallet proves it's profitable (real PnL data), we track them forever. When multiple proven winners buy the same token at the same time, that's our signal.

It's like having 30 professional traders working for you - when 2+ agree on a trade, you follow them in.

**The compound effect**:
- Week 1: Find 30 good whales
- Week 2: Add 10 more good whales (40 total)
- Week 3: Add 10 more (50 total)
- Week 4: Top 30 are now HIGHLY vetted (4 weeks of PnL data)

Over time, the watchlist quality improves exponentially.
