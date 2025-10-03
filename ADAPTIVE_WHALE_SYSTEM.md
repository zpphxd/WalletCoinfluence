# 🐋 Adaptive Whale Management System

## Overview

The Alpha Wallet Scout uses a **self-improving whale tracking system** that:
1. **Discovers** wallets buying trending tokens
2. **Scores** them using composite metrics (PnL + Activity + Timing)
3. **Monitors** top 30 whales for confluence
4. **Learns** from signal outcomes to improve weights
5. **Removes** whales that lose their edge

---

## Core Philosophy

> **Once profitable, always tracked. Once unprofitable, immediately dropped.**

The system continuously evaluates whale performance and adapts its scoring to maximize signal quality.

---

## Adaptive Scoring System

### Composite Whale Score

```
Score = (W_pnl × PnL_percentile) +
        (W_activity × Activity_percentile) +
        (W_early × EarlyScore_percentile)
```

**Default Weights**:
- W_pnl = 30% (profitability)
- W_activity = 30% (consistency)
- W_early = 40% (timing skill)

**Adaptive Weights** (learned from alert performance):
- If win_rate < 50%: Increase early weight to 50% (timing matters more)
- If win_rate > 70%: Increase PnL weight to 40% (follow proven winners)

### Percentile Ranking

Each whale is ranked against ALL discovered wallets on the same chain:

```python
# Example: Whale with $50k PnL
all_wallets = [0, 5k, 10k, 20k, 50k, 100k, 200k]
wallet_at_50k = 4th out of 7 = 57th percentile
```

Higher percentile = better performance relative to peers.

---

## Whale Lifecycle

### 1. Discovery
- Wallet buys trending token
- System fetches last 100 transactions
- Calculates initial stats (PnL, EarlyScore, activity)

### 2. Evaluation
- Calculate composite score
- Compare to all other wallets
- If in top 30: Add to watchlist

### 3. Monitoring
- Track every trade (every 5 min)
- Record in Redis for confluence detection
- Alert on 2+ whale confluence

### 4. Re-evaluation (Nightly)
- Recalculate all scores
- Adjust weights based on alert win rate
- Remove underperforming whales
- Add new high-scoring whales

### 5. Removal
- Whale meets any removal criteria
- Stop monitoring
- Free up resources for better whales

---

## Removal Criteria (Adaptive)

A whale is **automatically removed** if ANY of these conditions are met:

### 1. Negative PnL
```
Total PnL (realized + unrealized) < -$5,000
```
**Reason**: Losing money = not a good trader

### 2. Inactive
```
Trades in last 30 days = 0
```
**Reason**: Not trading = no signals to follow

### 3. Poor Timing
```
EarlyScore median < 20
```
**Reason**: Consistently buying late = FOMO, not alpha

### 4. No Big Wins
```
Best trade multiple < 2.0x
```
**Reason**: Can't identify 10x opportunities

### 5. Declining Performance
```
Last 7 days PnL < 50% of 30-day average
```
**Reason**: Edge is fading, signals getting worse

---

## Learning Feedback Loop

### Data Collection (Every Alert)

When confluence alert is sent:
```json
{
  "alert_id": "abc123",
  "token_address": "0x...",
  "whale_count": 3,
  "avg_whale_pnl": 75000,
  "alert_time": "2025-10-03T14:00:00Z",
  "whales": ["0xAAA...", "0xBBB...", "0xCCC..."]
}
```

### Performance Measurement (24h later)

Check token price change:
```json
{
  "alert_id": "abc123",
  "price_at_alert": 0.00123,
  "price_24h": 0.00185,
  "return_pct": 50.4,
  "pumped": true,  // >10% gain
  "time_to_pump_min": 18
}
```

### Weight Adjustment (Weekly)

Analyze last 7 days of alerts:
```python
if win_rate < 50%:
    # Signals not working - focus on better timing
    weights = {
        "pnl": 0.25,
        "activity": 0.25,
        "early": 0.50  # Increased
    }
elif win_rate > 70%:
    # Signals working - focus on proven winners
    weights = {
        "pnl": 0.40,  # Increased
        "activity": 0.25,
        "early": 0.35
    }
```

### Continuous Improvement

```
Week 1: 45% win rate → Adjust weights → Focus on timing
Week 2: 55% win rate → Slight improvement
Week 3: 62% win rate → Working! Keep these weights
Week 4: 68% win rate → Optimize further, track top performers
```

---

## Example: Whale Evaluation

### Discovery
```
Wallet: 0xABC...
Discovered: Bought $PEPE @ $0.000001
Initial Stats:
  - 30d PnL: $0 (just discovered)
  - Trades: 1
  - EarlyScore: 45 (medium-early)
```

### After Backfill
```
Fetched last 100 transactions:
  - 30d PnL: $47,500 (realized) + $12,300 (unrealized) = $59,800 total
  - Trades: 23
  - EarlyScore median: 67
  - Best trade: 8.2x ($500 → $4,100)
```

### Scoring (Against 84 Wallets)
```
PnL Percentile: $59,800 ranks #3 = 96th percentile
Activity Percentile: 23 trades ranks #8 = 90th percentile
Early Percentile: Score 67 ranks #12 = 85th percentile

Composite Score = 0.30(96) + 0.30(90) + 0.40(85) = 89.8
```

### Watchlist Decision
```
Top 30 threshold: Score > 75
This wallet: 89.8
Decision: ADD TO WATCHLIST ✅
```

### 7 Days Later
```
New Stats:
  - 30d PnL: $52,100 (down from $59,800)
  - Last 7d: Only 1 trade, lost $3,200
  - Trend: DECLINING

Re-evaluation:
  - Recent performance: 7d PnL / (30d avg) = -$3,200 / $2,000 = -160%
  - Meets removal criteria: "Declining performance"

Decision: REMOVE FROM WATCHLIST ❌
Reason: "Performance declining (last 7d worse than 30d avg)"
```

---

## Signal Quality Evolution

### Target Metrics

| Metric | Week 1 | Week 4 | Week 12 | Target |
|--------|--------|--------|---------|--------|
| Win Rate | 40% | 55% | 68% | >60% |
| Avg Return | 15% | 22% | 31% | >25% |
| Time to Pump | 45min | 32min | 18min | <30min |
| Whales Tracked | 69 | 42 | 30 | 20-30 |

### How We Get There

**Week 1-2**: Discovery phase
- Track many wallets (50-100)
- Learn which metrics correlate with pumps
- High noise, low win rate (~40%)

**Week 3-4**: Refinement phase
- Remove bottom 50% performers
- Adjust weights based on outcomes
- Win rate improves to 50-60%

**Week 5-8**: Optimization phase
- Track only top 30 whales
- Fine-tune removal criteria
- Win rate hits 60-70%

**Week 9+**: Maintenance phase
- Continuous improvement
- Add new whales as discovered
- Remove declining performers
- Stable 65-75% win rate

---

## Technical Implementation

### Nightly Maintenance Job

Runs at 2:00 AM UTC every day:

```python
def run_nightly_maintenance():
    # 1. Recalculate all wallet stats
    for wallet in all_wallets:
        calculate_stats(wallet)

    # 2. Measure recent alert performance
    performance = evaluate_last_7_days_alerts()

    # 3. Adjust scoring weights
    new_weights = adjust_weights(performance)

    # 4. Re-rank all whales
    ranked = rank_all_whales(weights=new_weights)

    # 5. Update watchlist (top 30)
    top_30 = ranked[:30]

    # 6. Remove underperformers
    for whale in current_watchlist:
        should_remove, reason = evaluate_removal(whale)
        if should_remove:
            remove_from_watchlist(whale, reason)

    # 7. Add new high-performers
    for whale in top_30:
        if whale not in current_watchlist:
            add_to_watchlist(whale)
```

### Monitoring Loop

Runs every 5 minutes:

```python
def monitor_watchlist():
    whales = get_top_30_whales()

    for whale in whales:
        new_trades = check_for_new_trades(whale, lookback='24h')

        for trade in new_trades:
            # Record in Redis
            record_buy(trade)

            # Check confluence
            if check_confluence(trade.token, min_wallets=2):
                send_confluence_alert(trade)
            else:
                send_single_alert(trade)
```

---

## FAQ

### Why remove whales at all?

**Past performance ≠ future performance.** A wallet that was profitable in Q1 might lose its edge in Q2. We want to follow CURRENT winners, not historical ones.

### Won't we miss out if a removed whale starts performing again?

No! The system re-evaluates ALL discovered wallets daily. If a previously removed whale starts crushing it again, they'll rank back into the top 30 and get re-added automatically.

### How many whales should we track?

**Quality > Quantity.** Tracking 1000 mediocre wallets = noise. Tracking 30 proven winners = alpha. The top 30 generates enough confluence signals (2-5 per day) without overwhelming users.

### What if all alerts fail?

The adaptive system will:
1. Detect low win rate (<40%)
2. Aggressively re-weight scoring (increase EarlyScore to 60%)
3. Remove bottom 50% of whales
4. Discover new whales from trending tokens
5. Test new top 30 next week

### How long until the system is "trained"?

**4-6 weeks** to reach optimal performance:
- Week 1-2: Learning phase (collecting data)
- Week 3-4: Refinement (removing noise)
- Week 5-6: Optimization (fine-tuning weights)
- Week 7+: Stable performance (65-75% win rate)

---

## Success Story Example

### Before Adaptive System
```
Tracking: 150 wallets
Win Rate: 38%
Avg Return: 12%
User Feedback: "Too many bad signals, hard to trust"
```

### After 8 Weeks
```
Tracking: 28 whales (removed 122)
Win Rate: 71%
Avg Return: 34%
User Feedback: "3 out of 4 alerts pump, this actually works!"
```

### What Changed?
- Removed 100+ wallets with negative PnL
- Removed 15 whales with declining performance
- Removed 7 inactive wallets
- Kept only the 28 consistently profitable traders
- Adjusted weights to favor early timing (40% → 55%)

**Result**: Fewer alerts, but MUCH higher quality.

---

## Conclusion

The Adaptive Whale Management System ensures we're always following the **current best performers**, not past winners who've lost their edge.

**Key Principles**:
1. **Earn your spot**: New whales must prove profitability
2. **Keep performing**: Stats recalculated daily
3. **Lose your edge**: Immediate removal
4. **Learn continuously**: Weights adapt to outcomes
5. **Quality over quantity**: Top 30 only

This creates a **self-improving signal engine** that gets better over time as it learns which whale characteristics actually lead to profitable alerts.

🐋 **Track the best. Drop the rest. Improve continuously.**
