# Alpha Wallet Scout - Learning Phase

**Started**: October 3, 2025 at 9:00 PM UTC
**Duration**: 24-48 hours
**Status**: 🔕 Alerts PAUSED - Building whale pool

---

## 🎯 What's Happening Now

The system is in **LEARNING MODE** - discovering wallets, calculating real PnL, and identifying the BEST whales.

### Active Processes (Every Few Minutes)
- ✅ **Token Ingestion** (5 min) - Finding trending tokens
- ✅ **Wallet Discovery** (10 min) - Finding buyers of trending tokens
- ✅ **Whale Discovery** (5 min) - Finding $10k+ trades
- ✅ **Stats Rollup** (15 min) - **CALCULATING REAL PnL WITH LIVE PRICES**
- ✅ **Monitoring** (2 min) - Tracking TOP 30 whales (but NOT sending alerts)

### What's Being Built
1. **Whale Pool** - Database of wallets that have traded trending tokens
2. **PnL History** - Unrealized gains/losses for each whale's open positions
3. **Performance Metrics** - EarlyScore, best trade multiple, activity level
4. **TOP 30 Rankings** - Composite score to identify the BEST whales

---

## 📊 How to Monitor Progress

### Check Current Whale Pool Size
```bash
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    COUNT(*) as total_wallets,
    COUNT(CASE WHEN ws.unrealized_pnl_usd > 0 THEN 1 END) as profitable_whales,
    COUNT(CASE WHEN ws.unrealized_pnl_usd < 0 THEN 1 END) as losing_whales
FROM wallet_stats_30d ws;
"
```

### Check TOP 10 Whales (Current Leaders)
```bash
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    wallet_address,
    ROUND(unrealized_pnl_usd::numeric, 2) as unrealized_pnl,
    trades_count,
    ROUND(earlyscore_median::numeric, 1) as early_score,
    ROUND((unrealized_pnl_usd * 0.3 + trades_count * 3 + earlyscore_median * 0.4)::numeric, 1) as composite_score
FROM wallet_stats_30d
WHERE unrealized_pnl_usd > 0
ORDER BY composite_score DESC
LIMIT 10;
"
```

### Check Recent Activity (Last Hour)
```bash
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    COUNT(*) as total_trades,
    COUNT(CASE WHEN side = 'buy' THEN 1 END) as buys,
    COUNT(CASE WHEN side = 'sell' THEN 1 END) as sells,
    COUNT(DISTINCT wallet_address) as unique_wallets,
    COUNT(DISTINCT token_address) as unique_tokens
FROM trades
WHERE ts > NOW() - INTERVAL '1 hour';
"
```

### Check Which Tokens Whales Are Trading
```bash
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    tok.symbol,
    COUNT(DISTINCT t.wallet_address) as whale_count,
    COUNT(*) as total_trades,
    ROUND(AVG(t.usd_value)::numeric, 2) as avg_trade_size
FROM trades t
JOIN tokens tok ON t.token_address = tok.token_address
WHERE t.ts > NOW() - INTERVAL '24 hours'
GROUP BY tok.symbol
ORDER BY whale_count DESC
LIMIT 10;
"
```

---

## 🧪 Success Indicators (What to Look For)

### After 6 Hours:
- [ ] At least **20-30 profitable whales** (unrealized_pnl > $0)
- [ ] TOP 10 whales have **unrealized PnL > $1,000**
- [ ] Whales are actively trading (5+ trades each)
- [ ] Multiple whales buying same tokens

### After 24 Hours:
- [ ] At least **50-100 profitable whales** discovered
- [ ] TOP 30 whales have **strong composite scores** (>100)
- [ ] Seeing **confluence patterns** (2+ whales buying same token)
- [ ] No whales with negative PnL in TOP 30

### After 48 Hours:
- [ ] **Vetted whale pool** ready for monitoring
- [ ] Clear differentiation between good/bad whales
- [ ] Sufficient trade history for PnL validation
- [ ] Ready to re-enable alerts

---

## 🔬 Performance Tracking (Positive/Negative Reinforcement)

The system will track its own performance:

### ✅ REWARDS (What Makes a Good Whale)
- **+100 points**: Whale's token pumped >50% within 1 hour of their buy
- **+75 points**: Whale's token pumped >30% within 2 hours
- **+50 points**: Whale's token pumped >20% within 4 hours
- **+25 points**: Whale's token pumped >10% within 24 hours
- **+10 points**: Whale is actually profitable (positive unrealized PnL)
- **+5 points**: Whale has high EarlyScore (>60)

### ❌ PUNISHMENTS (What Makes a Bad Whale)
- **-50 points**: Whale's token dumped >20% within 1 hour
- **-25 points**: Whale's token dumped >10% within 4 hours
- **-10 points**: Whale has negative unrealized PnL
- **-5 points**: Whale's EarlyScore is low (<30)
- **-100 points**: Missed a >100% pump from a tracked whale

### Self-Scoring Output
After 24-48 hours, run:
```bash
docker exec wallet_scout_worker python3 -c "
from src.analytics.performance_tracker import PerformanceTracker
from src.db.session import SessionLocal

db = SessionLocal()
tracker = PerformanceTracker(db)

# Evaluate all tracked wallets
for wallet in db.query(Wallet).limit(100):
    tracker.evaluate_wallet_performance(wallet.address)

# Get report
report = tracker.get_performance_report()
print(report)
"
```

---

## 🚀 What Happens After Learning Phase

### When We're Ready (24-48 hours):
1. **Review TOP 30 whales** - Are they consistently profitable?
2. **Check confluence patterns** - Are multiple whales buying same tokens?
3. **Validate with real data** - Did their past trades actually pump?

### Then Re-Enable Alerts:
```bash
# Edit .env file
# Uncomment Telegram credentials:
# TELEGRAM_BOT_TOKEN=8482390902:AAHFiGq9q9Gt-P7ErpZL0FDs9PyEYIwmN_c
# TELEGRAM_CHAT_ID=8416972017

# Restart worker
docker compose restart worker
```

### You'll Start Getting:
- **BUY signals** when 2+ vetted whales buy same token within 30 min
- **SELL signals** when 2+ vetted whales exit a position
- Only from **PROVEN** profitable whales (not random traders)

---

## 📈 Expected Timeline

| Time | What Should Be Happening |
|------|--------------------------|
| **Now** | System discovering wallets, no alerts |
| **+1 hour** | First PnL calculations with live prices |
| **+6 hours** | 20-30 profitable whales identified |
| **+12 hours** | 50+ whales, clear TOP 30 rankings |
| **+24 hours** | 100+ whales, ready to review performance |
| **+48 hours** | Vetted whale pool, ready for live alerts |

---

## 🔍 Troubleshooting

### If No Profitable Whales After 6 Hours:
1. Check if stats_rollup is running every 15 min:
   ```bash
   docker logs wallet_scout_worker --tail 100 | grep "Stats rollup"
   ```

2. Check if live prices are being fetched:
   ```bash
   docker logs wallet_scout_worker --tail 100 | grep "Current price"
   ```

3. Check DexScreener/Birdeye APIs aren't ALL failing:
   ```bash
   docker logs wallet_scout_worker --tail 100 | grep "price sources failed"
   ```

### If Too Many Whales Have Negative PnL:
- This is NORMAL early on - some traders lose money
- System will filter them out automatically
- Only TOP 30 profitable whales get monitored
- After 24-48 hours, losers will drop out naturally

---

## 💡 Key Insight

**The longer we wait, the better the whale pool becomes.**

- Day 1: Finding whales
- Day 2: Identifying winners
- Day 3: **PROVEN** winners (multiple profitable trades)
- Day 4+: **Elite** whale pool (only the best)

**Patience during learning = Better alerts later!**

---

## 📝 Next Steps

1. ✅ Let system run for 24-48 hours (alerts paused)
2. ⏳ Monitor whale pool growth every 6 hours
3. ⏳ Check TOP 30 rankings improve over time
4. ⏳ Validate confluence patterns are appearing
5. ⏳ Re-enable alerts when whale pool is vetted

**Current Status**: Learning mode active, building whale pool 🐋📊
