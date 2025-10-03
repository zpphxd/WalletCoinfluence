# Alpha Wallet Scout - MVP Project Status

**Date:** 2025-10-03
**Version:** 0.1-MVP
**Status:** ✅ **COMPLETE - Ready for Testing**

---

## ✅ Completed Components

### 1. Core Infrastructure ✓
- [x] Repository structure and scaffolding
- [x] Database models (SQLAlchemy)
- [x] Alembic migrations setup
- [x] Configuration management (Pydantic Settings)
- [x] Docker Compose setup
- [x] Makefile for common operations

### 2. Data Ingestion ✓
- [x] DEX Screener client (trending tokens)
- [x] GeckoTerminal client (trending pools)
- [x] Birdeye client (Solana trending)
- [x] Runner seed job (every 15 minutes)
- [x] Token metadata normalization

### 3. Analytics Engine ✓
- [x] FIFO PnL calculator (realized/unrealized)
- [x] Being-Early score (0-100 metric)
- [x] Wallet stats rollup (30D window)
- [x] Best trade multiple calculation
- [x] Stats aggregation job (hourly)

### 4. Risk Filters ✓
- [x] Honeypot.is client (scam detection)
- [x] TokenSniffer client (additional checks)
- [x] Bot filter heuristics
  - Short hold times
  - Same-block flips
  - Single buy-sell patterns

### 5. Watchlist Management ✓
- [x] Add criteria evaluation
  - Min trades (configurable)
  - Min PnL threshold
  - Best trade multiple requirement
- [x] Remove criteria evaluation
  - Negative PnL
  - High drawdown
  - Inactivity
- [x] Nightly maintenance job

### 6. Alert System ✓
- [x] Telegram bot integration
- [x] Single wallet alerts
- [x] Confluence detection (Redis sorted sets)
- [x] Alert formatting and delivery
- [x] Deduplication logic

### 7. API Endpoints ✓
- [x] Health check
- [x] Watchlist retrieval
- [x] Top wallets stats
- [x] Recent alerts
- [x] Authentication (Bearer token)
- [x] CORS configuration

### 8. Scheduling ✓
- [x] APScheduler setup
- [x] Runner seed job (15 min intervals)
- [x] Stats rollup job (hourly)
- [x] Watchlist maintenance (nightly at 2 AM)

### 9. Testing ✓
- [x] Unit tests for PnL FIFO
- [x] Unit tests for EarlyScore
- [x] Unit tests for Confluence
- [x] Pytest configuration
- [x] Mock fixtures

### 10. Documentation ✓
- [x] Comprehensive README
- [x] Detailed USAGE guide
- [x] Environment variable examples
- [x] Telegram setup instructions
- [x] Troubleshooting guide

---

## 📁 Repository Structure

```
alpha-wallet-scout/
├── src/
│   ├── api/              # FastAPI endpoints
│   ├── alerts/           # Telegram + confluence
│   ├── analytics/        # PnL, EarlyScore, bot filter
│   ├── clients/          # External API clients
│   ├── db/               # Models, session, migrations
│   ├── ingest/           # Runner token ingestion
│   ├── scheduler/        # Job scheduling
│   ├── watchlist/        # Add/remove rules
│   └── config.py         # Settings management
├── tests/
│   ├── unit/             # Unit tests
│   └── integration/      # Integration tests
├── alembic/              # Database migrations
├── docker-compose.yml    # Service orchestration
├── Dockerfile.api        # API container
├── Dockerfile.worker     # Worker container
├── Makefile              # Common commands
├── README.md             # Overview
├── USAGE.md              # Detailed guide
└── .env.example          # Config template
```

---

## 🚀 Quick Start

### 1. Setup
```bash
cd "/Users/zachpowers/Wallet Signal"
cp .env.example .env
# Edit .env with your API keys
```

### 2. Start Services
```bash
make up
```

### 3. Verify
```bash
curl http://localhost:8000/health
```

---

## 🔑 Required Configuration

### Mandatory
- `TELEGRAM_BOT_TOKEN` - Create via @BotFather
- `TELEGRAM_CHAT_ID` - Get from getUpdates API
- `ALCHEMY_API_KEY` - For EVM chains
- `HELIUS_API_KEY` - For Solana

### Optional (Enhanced Features)
- `BIRDEYE_API_KEY` - Better Solana trending
- `BITQUERY_API_KEY` - Historical trades
- `TOKENSNIFFER_API_KEY` - Advanced scam detection

---

## 📊 Key Metrics Explained

### Being-Early Score (0-100)
```
EarlyScore = 40 × (1 - rank_percentile)     # Buy timing
           + 40 × (1M - mc_at_buy) / 1M     # Market cap
           + 20 × volume_participation       # Position size
```

**Interpretation:**
- 80-100: Very early entry (top 10% of buyers)
- 60-80: Early entry (top 25%)
- 40-60: Mid-range
- <40: Late entry

### 30D PnL (FIFO)
- **Realized**: Closed trades only
- **Unrealized**: Current open positions
- Uses First-In-First-Out accounting

---

## ⚙️ Default Thresholds

### Watchlist Add
```
MIN_TRADES_30D=5
MIN_REALIZED_PNL_30D_USD=50000
MIN_BEST_TRADE_MULTIPLE=3
```

### Watchlist Remove
```
REALIZED_PNL_30D_LT=0 (negative)
MAX_DRAWDOWN_PCT_GT=50
TRADES_30D_LT=2
```

### Filters
```
MIN_UNIQUE_BUYERS_24H=30
MAX_TAX_PCT=10
CONFLUENCE_MINUTES=30
```

---

## 🎯 Data Flow

```
1. Runner Seed (15 min)
   ↓
2. Token Discovery (DEX Screener, GeckoTerminal, Birdeye)
   ↓
3. Buyer Wallet Extraction
   ↓
4. 30D Trade Backfill
   ↓
5. PnL + EarlyScore Calculation
   ↓
6. Bot/Scam Filtering
   ↓
7. Watchlist Update (nightly)
   ↓
8. Real-time Trade Monitoring
   ↓
9. Alert Delivery (Telegram)
```

---

## 🧪 Testing

```bash
# Run all tests
make test

# Specific test file
poetry run pytest tests/unit/test_pnl.py -v

# With coverage
poetry run pytest --cov=src --cov-report=html
```

---

## 📝 What's NOT Included (Out of Scope for MVP)

- ❌ Web dashboard (basic API only)
- ❌ ML-based bot detection (heuristics only)
- ❌ Slippage/MEV analytics
- ❌ Multi-user support
- ❌ Webhook ingestion (polling only)
- ❌ Advanced wallet clustering
- ❌ Discord integration

---

## 🛠️ Next Steps for Production

### Phase 1: Testing (Week 1)
1. Configure API keys
2. Run for 24-48 hours
3. Monitor logs and alerts
4. Tune thresholds based on results

### Phase 2: Optimization (Week 2)
1. Add webhook support (reduce polling)
2. Implement caching layer
3. Add monitoring/alerting (Grafana/Prometheus)
4. Load test with realistic data

### Phase 3: Enhancement (Week 3+)
1. Web dashboard (Streamlit/Next.js)
2. Multi-user support
3. Discord integration
4. Advanced analytics

---

## 🔒 Security & Compliance

### Built-in Safety
- ✅ API authentication (Bearer token)
- ✅ No private key storage
- ✅ Read-only blockchain access
- ✅ Rate limiting on external APIs
- ✅ SQL injection protection (SQLAlchemy)

### Disclaimers
- ⚠️ Not financial advice
- ⚠️ Experimental software
- ⚠️ DYOR always required
- ⚠️ No guarantees on accuracy

---

## 💰 Cost Estimates (Monthly)

### Free Tier (Possible)
- Alchemy: 300M compute units/mo
- Helius: 100k requests/mo
- DEX Screener: Unlimited (public API)
- GeckoTerminal: Unlimited (public API)

### Paid Tier (Recommended)
- Alchemy: $49/mo (Growth)
- Helius: $99/mo (Pro)
- Birdeye: $50/mo (Starter)
- TokenSniffer: $30/mo (Basic)
- **Total: ~$230/mo**

### Infrastructure
- VPS/Cloud: $20-50/mo
- Database: Included in VPS or $10/mo managed
- Redis: Included or $10/mo managed

---

## 📈 Performance Expectations

### Initial Setup
- First alerts: **1-2 hours**
- Full watchlist: **24-48 hours**
- Stable operation: **72 hours**

### Ongoing
- Alert latency: **< 5 minutes**
- Stats refresh: **Every hour**
- Watchlist churn: **Nightly**

### Scale
- Wallets tracked: **1,000-10,000**
- Tokens monitored: **500-2,000**
- Alerts/day: **10-100** (depends on market)

---

## 🐛 Known Limitations

1. **Chain Support**: Only Ethereum, Base, Arbitrum, Solana
2. **Data Lag**: 5-15 min delay from on-chain to alert
3. **Bot Detection**: Heuristic-based (not ML)
4. **Scam Filters**: Not 100% accurate
5. **Market Cap Proxy**: Uses liquidity × 3 estimate

---

## 🎓 Learning Resources

- [FIFO Accounting](https://www.investopedia.com/terms/f/fifo.asp)
- [DEX Screener API Docs](https://docs.dexscreener.com/)
- [Telegram Bot API](https://core.telegram.org/bots/api)
- [Solana DEX Trading](https://docs.solana.com/)

---

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-repo/issues)
- **Docs**: README.md, USAGE.md
- **Community**: Discord (coming soon)

---

## ✨ Built With

- **Python 3.11+**
- **FastAPI** - Web framework
- **SQLAlchemy** - ORM
- **Alembic** - Migrations
- **Redis** - Caching/windows
- **APScheduler** - Job scheduling
- **python-telegram-bot** - Telegram integration
- **Docker** - Containerization

---

**Status**: ✅ All core components implemented and tested. Ready for initial deployment and user testing.

**Next Action**: Configure `.env` with API keys and run `make up` to start services.
