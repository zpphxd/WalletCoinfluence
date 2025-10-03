## Alpha Wallet Scout - Usage Guide

### Table of Contents

1. [Getting Started](#getting-started)
2. [Telegram Setup](#telegram-setup)
3. [Configuration](#configuration)
4. [Running the System](#running-the-system)
5. [Understanding Metrics](#understanding-metrics)
6. [Tuning Thresholds](#tuning-thresholds)
7. [API Usage](#api-usage)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Prerequisites

- Docker & Docker Compose (recommended)
- OR Python 3.11+ and Poetry
- Telegram account
- API keys (see below)

### Required API Keys

1. **Alchemy** (EVM chains) - [Get key](https://www.alchemy.com/)
2. **Helius** (Solana) - [Get key](https://www.helius.dev/)
3. **Telegram Bot** - [Create bot](#telegram-setup)

### Optional API Keys

- **Birdeye** - Enhanced Solana data
- **Bitquery** - Historical trade data
- **TokenSniffer** - Advanced scam detection

---

## Telegram Setup

### Step 1: Create Your Bot

1. Open Telegram and message [@BotFather](https://t.me/botfather)
2. Send `/newbot` command
3. Follow prompts to name your bot
4. Copy the **bot token** (looks like `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)
5. Save this as `TELEGRAM_BOT_TOKEN` in your `.env`

### Step 2: Get Your Chat ID

**Option A: Personal Messages**
```bash
# 1. Send any message to your bot
# 2. Visit this URL (replace <TOKEN>):
https://api.telegram.org/bot<TOKEN>/getUpdates

# 3. Find "chat":{"id": 123456789}
# 4. Save as TELEGRAM_CHAT_ID
```

**Option B: Channel/Group**
```bash
# 1. Add your bot to the channel/group
# 2. Give it admin rights
# 3. Send a message in the channel
# 4. Use the getUpdates URL above
# 5. Look for negative ID (e.g., -1001234567890)
```

### Step 3: Test
```bash
# With your .env configured:
curl -X POST "https://api.telegram.org/bot<TOKEN>/sendMessage" \
  -d "chat_id=<CHAT_ID>" \
  -d "text=Test from Alpha Wallet Scout!"
```

---

## Configuration

### Environment Variables

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

### Essential Settings

```bash
# Database
DATABASE_URL=postgresql://wallet_scout:wallet_scout_pass@localhost:5432/wallet_scout

# Telegram
TELEGRAM_BOT_TOKEN=your_bot_token_here
TELEGRAM_CHAT_ID=your_chat_id_here

# EVM Data
ALCHEMY_API_KEY=your_alchemy_key

# Solana Data
HELIUS_API_KEY=your_helius_key
```

### Chain Selection

Enable/disable chains:
```bash
# All chains
CHAINS=ethereum,base,arbitrum,solana

# Just EVM
CHAINS=ethereum,base,arbitrum

# Just Solana
CHAINS=solana
```

---

## Running the System

### With Docker (Recommended)

```bash
# Start all services
make up

# View logs
docker-compose logs -f worker

# Stop
make down
```

### With Poetry (Development)

```bash
# Install
poetry install

# Run migrations
make migrate

# Terminal 1: API
make dev

# Terminal 2: Worker/Scheduler
poetry run python -m src.scheduler.main
```

### First Run

The system will:
1. ✅ Create database tables
2. ✅ Start fetching trending tokens
3. ✅ Discover wallet buyers
4. ✅ Begin calculating stats
5. ✅ Build initial watchlist

**Wait 1-2 hours** for meaningful data.

---

## Understanding Metrics

### 30D PnL (Realized)

- Actual profit from **closed trades** (bought and sold)
- Calculated using **FIFO** (First In, First Out)
- Excludes unrealized gains

**Example:**
```
Buy 1000 tokens @ $0.10 = $100
Sell 500 tokens @ $0.30 = $150
Realized PnL = $150 - $50 = $100
```

### Best Trade Multiple

- Highest return on any single trade
- `multiple = sell_price / buy_price`

**Example:**
```
Buy @ $0.01, Sell @ $0.05 = 5x
Best Trade Multiple = 5.0
```

### Being-Early Score (0-100)

Composite score measuring how early a wallet buys:

**Formula:**
```
EarlyScore = 40 × (1 - rank_percentile)     # Buy rank
           + 40 × (1M - mc_at_buy) / 1M     # Market cap
           + 20 × volume_participation       # Size
```

**Interpretation:**
- **80-100**: Very early (top 10% of buyers, low MC)
- **60-80**: Early (top 25%, < $500k MC)
- **40-60**: Mid-entry
- **< 40**: Late

---

## Tuning Thresholds

### Watchlist Add Criteria

**Conservative** (fewer, higher quality):
```bash
ADD_MIN_TRADES_30D=10
ADD_MIN_REALIZED_PNL_30D_USD=100000
ADD_MIN_BEST_TRADE_MULTIPLE=5
```

**Aggressive** (more wallets, more noise):
```bash
ADD_MIN_TRADES_30D=3
ADD_MIN_REALIZED_PNL_30D_USD=25000
ADD_MIN_BEST_TRADE_MULTIPLE=2
```

**Recommended** (balanced):
```bash
ADD_MIN_TRADES_30D=5
ADD_MIN_REALIZED_PNL_30D_USD=50000
ADD_MIN_BEST_TRADE_MULTIPLE=3
```

### Watchlist Remove Criteria

**Strict** (remove quickly):
```bash
REMOVE_IF_REALIZED_PNL_30D_LT=0
REMOVE_IF_MAX_DRAWDOWN_PCT_GT=30
REMOVE_IF_TRADES_30D_LT=3
```

**Lenient** (give wallets more time):
```bash
REMOVE_IF_REALIZED_PNL_30D_LT=-10000
REMOVE_IF_MAX_DRAWDOWN_PCT_GT=60
REMOVE_IF_TRADES_30D_LT=1
```

### Scam/Bot Filters

**Strict** (fewer false positives, may miss some good tokens):
```bash
MIN_UNIQUE_BUYERS_24H=50
MAX_TAX_PCT=5
```

**Relaxed** (more tokens, more risk):
```bash
MIN_UNIQUE_BUYERS_24H=20
MAX_TAX_PCT=15
```

### Confluence Window

**Short** (5-15 min):
```bash
CONFLUENCE_MINUTES=10
```
- Tighter correlation
- Fewer alerts
- Higher confidence

**Long** (30-60 min):
```bash
CONFLUENCE_MINUTES=60
```
- More alerts
- Looser correlation

---

## API Usage

### Authentication

Include bearer token:
```bash
curl -H "Authorization: Bearer your_api_token" \
  http://localhost:8000/api/v1/watchlist
```

### Endpoints

**Get Watchlist**
```bash
GET /api/v1/watchlist?chain=ethereum&limit=50
```

**Top Wallets**
```bash
GET /api/v1/stats/top-wallets?min_pnl=50000&limit=20
```

**Recent Alerts**
```bash
GET /api/v1/alerts/recent?hours=24&type=confluence
```

### Example Response

```json
{
  "wallet": "0xabc123...",
  "chain_id": "ethereum",
  "trades_count": 47,
  "realized_pnl_usd": 125000.50,
  "best_trade_multiple": 8.2,
  "earlyscore_median": 76.5
}
```

---

## Troubleshooting

### No Alerts

**Check Telegram Config:**
```bash
# Test connection
docker-compose exec worker python -c "
from src.config import settings
print(f'Bot Token: {settings.telegram_bot_token[:10]}...')
print(f'Chat ID: {settings.telegram_chat_id}')
"
```

**Check Watchlist:**
```bash
curl http://localhost:8000/api/v1/watchlist
```

If empty, wait for stats to accumulate (1-2 hours).

### Database Connection Error

```bash
# Check Postgres is running
docker-compose ps

# View logs
docker-compose logs postgres

# Reset database
docker-compose down -v
docker-compose up -d
```

### API Rate Limits

**Symptoms:** HTTP 429 errors in logs

**Solutions:**
1. Increase `RUNNER_POLL_MINUTES` (e.g., 30 instead of 15)
2. Reduce number of chains
3. Use paid API tiers

### High Memory Usage

**Reduce window size:**
```bash
WALLET_BACKFILL_DAYS=15  # Instead of 30
```

**Limit chains:**
```bash
CHAINS=ethereum  # Focus on one chain
```

---

## Advanced Usage

### Custom SQL Queries

```bash
# Connect to database
docker-compose exec postgres psql -U wallet_scout

# Top 10 wallets by PnL
SELECT wallet, realized_pnl_usd, best_trade_multiple
FROM wallet_stats_30d
ORDER BY realized_pnl_usd DESC
LIMIT 10;
```

### Export Watchlist

```bash
# Get watchlist as JSON
curl http://localhost:8000/api/v1/watchlist?limit=500 > watchlist.json
```

### Scheduled Reports

Add to crontab:
```bash
# Daily summary at 9 AM
0 9 * * * curl http://localhost:8000/api/v1/stats/top-wallets | jq '.' | mail -s "Daily Alpha Report" you@example.com
```

---

## Performance Tips

1. **Use webhooks** instead of polling (requires Helius Pro for Solana)
2. **Cache trending tokens** - reduce API calls
3. **Limit backfill** - start with 15 days instead of 30
4. **Index frequently queried fields** in Postgres
5. **Use Redis for hot data** (confluence windows)

---

## Next Steps

1. ✅ Let system run for 24 hours
2. ✅ Review initial alerts
3. ✅ Tune thresholds based on results
4. ✅ Add more API keys for better coverage
5. ✅ Set up monitoring/alerting for system health

---

## Support

- 📖 [README](./README.md) - Project overview
- 📧 [GitHub Issues](https://github.com/your-repo/issues)
- 💬 [Discord Community](https://discord.gg/your-server)

---

**Remember:** This is alpha-quality software. Always DYOR (Do Your Own Research) before making trading decisions based on these alerts!
