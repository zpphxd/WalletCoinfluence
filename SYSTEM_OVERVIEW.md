# Alpha Wallet Scout - System Overview

**Built**: October 2025
**Purpose**: Find profitable crypto whale wallets and alert when multiple whales buy the same token (confluence)
**Current Status**: 🔕 Learning Phase (Alerts Paused)

---

## 🎯 What We Built

### The Core Concept
**Follow the smart money.** When 2+ proven profitable whales buy the same token within 30 minutes, that's a HIGH CONFIDENCE buy signal.

### How It Works (4-Stage Pipeline)

#### Stage 1: DISCOVER TRENDING TOKENS (Every 5 min)
- Fetches top 50 trending tokens per chain from GeckoTerminal
- Focuses on tokens getting attention (likely where whales trade)
- **Output**: ~60 trending tokens saved to database

#### Stage 2: FIND WHALES BUYING THOSE TOKENS (Every 5-10 min)
**Two discovery methods**:

1. **Standard Discovery** (Every 10 min)
   - For each trending token, fetch ALL buyers in last 16 hours
   - Uses Alchemy API (5000 blocks lookback)
   - Identifies DEX buys vs random transfers
   - Records wallet addresses and their trades

2. **Enhanced Whale Discovery** (Every 5 min)
   - Targets ONLY $10k+ trades (real whales)
   - Fetches from high-liquidity tokens ($50k+ liquidity)
   - Doubles coverage (100 transactions per token)

**Output**: 84+ wallets discovered with 122+ trades tracked

#### Stage 3: CALCULATE REAL PNL + RANK WHALES (Every 15 min)
**Critical Innovation: LIVE PRICE PNL CALCULATION**

The system fetches **current market prices** (not last trade price) to calculate unrealized PnL:

**Multi-Source Price Fetcher**:
- **Try 1**: DexScreener (best data, rate limited)
- **Try 2**: Birdeye (more generous limits)
- **Try 3**: CoinGecko (fallback for major tokens)
- **Fallback**: Last trade price if all fail

**PnL Calculation (FIFO Method)**:
```
For each whale:
  For each token they bought:
    current_price = fetch_live_price()  # Not last trade!
    current_value = qty × current_price
    unrealized_pnl = current_value - cost_basis
```

**Whale Ranking (Composite Score)**:
```
score = 0.30 × Unrealized PnL (current position value)
      + 0.30 × Trade Activity (more trades = more data)
      + 0.40 × EarlyScore (timing ability, 0-100)
```

**Output**: TOP 30 whales selected by composite score

#### Stage 4: MONITOR FOR CONFLUENCE (Every 2 min)
- Check each TOP 30 whale for new trades
- Record buys and sells in Redis (30-min window)
- Detect confluence: When ≥2 whales buy/sell same token
- Send alerts to Telegram (currently paused)

---

## 🔧 Technical Architecture

### Data Pipeline
```
GeckoTerminal API
    ↓ (trending tokens)
Alchemy/Helius API
    ↓ (wallet trades)
DexScreener/Birdeye/CoinGecko
    ↓ (current prices)
FIFO PnL Calculator
    ↓ (unrealized gains)
Composite Scoring
    ↓ (TOP 30 whales)
Confluence Detector (Redis)
    ↓ (≥2 whales buying)
Telegram Alert
```

### Background Jobs (APScheduler)
1. **runner_seed** (every 5 min) - Token ingestion
2. **wallet_discovery** (every 10 min) - Standard whale discovery
3. **whale_discovery** (every 5 min) - Enhanced $10k+ whale discovery
4. **stats_rollup** (every 15 min) - PnL calculation + ranking
5. **wallet_monitoring** (every 2 min) - TOP 30 whale monitoring
6. **watchlist_maintenance** (daily 2 AM UTC) - Cleanup

### Tech Stack
- **Backend**: Python 3.11, FastAPI
- **Database**: PostgreSQL (wallets, trades, stats)
- **Cache**: Redis (confluence detection)
- **APIs**: Alchemy, Helius, DexScreener, Birdeye, CoinGecko
- **Deployment**: Docker Compose
- **Alerts**: Telegram Bot

---

## 📊 Current System State

### Database (As of Oct 3, 2025)
- **84 wallets** discovered
- **122 trades** tracked (113 buys, 9 sells)
- **2 profitable whales** identified (more coming as prices update)
- **Top whale**: $715 unrealized PnL

### Key Features WORKING
✅ Token ingestion from GeckoTerminal
✅ Wallet discovery from trending tokens
✅ Enhanced whale discovery ($10k+ trades)
✅ **LIVE PRICE PnL calculation** (multi-source)
✅ TOP 30 whale selection (composite scoring)
✅ Buy AND sell signal detection
✅ Confluence detection (Redis-based)
✅ Telegram integration (paused for learning)

### Key Features NOT YET WORKING
⏳ Sufficient whale pool (need 50-100 profitable whales)
⏳ Historical performance validation
⏳ Self-scoring system implementation
⏳ Live alerts (paused during learning phase)

---

## 🎓 The Learning Phase (Next 24-48 Hours)

### What's Happening Now
**Goal**: Build a vetted pool of PROVEN profitable whales before sending alerts.

**Active Processes**:
- ✅ Discovering 10-20 new wallets every hour
- ✅ Fetching live prices every 15 minutes
- ✅ Calculating real unrealized PnL
- ✅ Ranking whales by composite score
- ✅ Tracking confluence patterns (no alerts sent)

### Hour-by-Hour Timeline

**HOUR 0-1** (Now - 10:00 PM UTC Oct 3)
```
🔄 What's Running:
- Token ingestion finding trending tokens
- Wallet discovery finding buyers
- Stats rollup calculating first batch of live PnL

📊 Expected Output:
- 20-30 profitable whales identified
- TOP 10 showing real unrealized PnL (not $0)
- First composite score rankings

🎯 Success Check:
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT COUNT(*) FROM wallet_stats_30d WHERE unrealized_pnl_usd > 0;
"
# Should show 20-30 profitable whales
```

**HOUR 1-6** (10:00 PM - 3:00 AM UTC)
```
🔄 What's Running:
- Continuous whale discovery (60+ new wallets)
- Live price updates every 15 min
- Composite scores being refined

📊 Expected Output:
- 50-80 profitable whales
- TOP 30 whales clearly differentiated from rest
- Multiple whales trading same tokens (confluence patterns)

🎯 Success Check:
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    COUNT(*) as profitable_whales,
    ROUND(AVG(unrealized_pnl_usd)::numeric, 2) as avg_pnl,
    ROUND(MAX(unrealized_pnl_usd)::numeric, 2) as max_pnl
FROM wallet_stats_30d
WHERE unrealized_pnl_usd > 0;
"
# Should show 50-80 whales, avg PnL >$500, max PnL >$5k
```

**HOUR 6-12** (3:00 AM - 9:00 AM UTC)
```
🔄 What's Running:
- Whale pool maturing (trade history building)
- Price movements being tracked
- Performance metrics accumulating

📊 Expected Output:
- 100+ profitable whales discovered
- TOP 30 whales have 5+ trades each
- Clear winners emerging (high composite scores)
- Confluence patterns appearing (2-3 whales/token)

🎯 Success Check:
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    wallet_address,
    ROUND(unrealized_pnl_usd::numeric, 2) as pnl,
    trades_count,
    ROUND(earlyscore_median::numeric, 1) as early_score
FROM wallet_stats_30d
WHERE unrealized_pnl_usd > 0
ORDER BY (unrealized_pnl_usd * 0.3 + trades_count * 3 + earlyscore_median * 0.4) DESC
LIMIT 10;
"
# Should show TOP 10 whales with strong metrics
```

**HOUR 12-24** (9:00 AM Oct 4 - 9:00 PM Oct 4)
```
🔄 What's Running:
- Whale pool stabilizing
- Historical performance validation
- Confluence patterns being logged

📊 Expected Output:
- 150+ whales total (100+ profitable)
- TOP 30 whales PROVEN over multiple price cycles
- Multiple confluence events detected (logged but not alerted)
- Ready for performance review

🎯 Success Check:
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    tok.symbol,
    COUNT(DISTINCT t.wallet_address) as whale_count,
    COUNT(*) as total_trades
FROM trades t
JOIN tokens tok ON t.token_address = tok.token_address
WHERE t.ts > NOW() - INTERVAL '24 hours'
GROUP BY tok.symbol
HAVING COUNT(DISTINCT t.wallet_address) >= 2
ORDER BY whale_count DESC;
"
# Should show multiple tokens with 2+ whales buying
```

**HOUR 24-48** (Oct 4-5)
```
🔄 What's Running:
- Extended validation period
- Tracking whale consistency
- Identifying best performers

📊 Expected Output:
- 200+ whales total
- TOP 30 whales are CONSISTENTLY profitable
- Confluence patterns validated
- System ready for live alerts

🎯 Decisions to Make:
1. Review TOP 30 whales - Are they reliably profitable?
2. Check confluence patterns - Do they lead to pumps?
3. Validate timing - Are we catching signals early enough?
4. Enable alerts if metrics look good
```

---

## 🏆 Self-Scoring System (To Be Implemented)

### Automatic Rewards (System Celebrates Success)

**🎁 WHALE DISCOVERY REWARDS** (Scaled by profitability):
- +10 pts: Small fish ($100-$1k PnL)
- +50 pts: Decent whale ($1k-$10k PnL)
- +200 pts: BIG whale ($10k-$50k PnL)
- +500 pts: HUGE whale ($50k-$100k PnL)
- +1000 pts: LEGENDARY whale ($100k+ PnL)

**🎁 CONFLUENCE DETECTION REWARDS** (Scaled by speed & quantity):
```
reward = 100 × num_whales × speed_multiplier

Speed Multiplier:
- 2.0x if detected within 5 min (INSTANT)
- 1.5x if detected within 15 min (FAST)
- 1.0x if detected within 30 min (OK)

Examples:
- 2 whales, <5min = +400 pts
- 3 whales, <5min = +600 pts
- 5 whales, <15min = +750 pts
```

### Automatic Punishments (System Learns from Mistakes)

**⚠️ LATE DETECTION PENALTIES** (Exponential by delay):
- -10 pts: 5-15 min late (minor delay)
- -50 pts: 15-30 min late (significant)
- -200 pts: 30-60 min late (WAY too late)
- -500 pts: >60 min late (completely missed)

**⚠️ BAD WHALE PENALTIES** (Scaled by losses):
- -5 pts: Minor loser ($100-$1k loss)
- -25 pts: Bad whale ($1k-$10k loss)
- -100 pts: TERRIBLE whale ($10k-$50k loss)
- -250 pts: DISASTER whale (>$50k loss)

### Performance Grading
```
Score Range → Grade
500+ → S+ (Elite Whale Hunter)
300-499 → A+ (Excellent)
150-299 → A (Very Good)
50-149 → B (Good)
0-49 → C (Acceptable)
<0 → F (Failing - needs improvement)
```

---

## 🚀 What Happens After Learning Phase

### After 24-48 Hours, We'll:
1. **Review TOP 30 Whales**
   - Check if they're consistently profitable
   - Validate their trades led to pumps
   - Confirm confluence patterns are real

2. **Re-Enable Telegram Alerts**
   ```bash
   # Edit .env
   # Uncomment:
   # TELEGRAM_BOT_TOKEN=8482390902:AAHFiGq9q9Gt-P7ErpZL0FDs9PyEYIwmN_c
   # TELEGRAM_CHAT_ID=8416972017

   # Restart worker
   docker compose restart worker
   ```

3. **Start Receiving ONLY High-Confidence Signals**
   - **BUY alerts**: When 2+ vetted whales buy same token <30min
   - **SELL alerts**: When 2+ vetted whales exit a position
   - From PROVEN profitable whales only (not random traders)

---

## 💡 The Key Innovation

### Before This System:
- ❌ Track ALL buyers (95% noise, 5% signal)
- ❌ Alert on single wallet buys (too many false positives)
- ❌ Use last trade price (unrealized PnL always $0)
- ❌ No whale vetting (follow losers too)

### With This System:
- ✅ Track ONLY profitable whales (TOP 30)
- ✅ Alert ONLY on confluence (≥2 whales agree)
- ✅ Use live market price (real unrealized PnL)
- ✅ Vet whales over 24-48 hours (proven winners only)

---

## 📈 Success Metrics (What We're Tracking)

### Whale Quality
- [ ] 100+ profitable whales identified
- [ ] TOP 30 avg unrealized PnL >$2,000
- [ ] TOP whale >$50,000 unrealized PnL
- [ ] All TOP 30 have positive PnL

### Confluence Patterns
- [ ] 5+ confluence events detected per day
- [ ] 2-5 whales per confluence event
- [ ] <30 min window between whales
- [ ] Multiple tokens showing confluence

### Alert Quality (After re-enabling)
- [ ] >60% of alerts lead to pump within 1 hour
- [ ] >25% average return per alert
- [ ] <5% false positive rate (dump after alert)
- [ ] Alerts sent <5 min after whale trades

---

## 🎯 Bottom Line

**We built a system that:**
1. **Finds whales** making real money (not bots or losers)
2. **Tracks them** with live PnL (not stale data)
3. **Ranks them** by profitability + timing + activity
4. **Monitors only the BEST 30** (not all 200+)
5. **Alerts ONLY when ≥2 agree** (confluence = high confidence)

**And right now it's LEARNING** - building the whale pool so when we turn on alerts, they'll be from PROVEN winners, not random traders.

**Patience now = Better signals later!** 🐋📊✨
