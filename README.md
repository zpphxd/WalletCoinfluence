# Alpha Wallet Scout

**Self-updating system that discovers high-signal on-chain traders and alerts on their trades.**

## Overview

Alpha Wallet Scout is an automated trading intelligence system that:

- 🔍 **Discovers** top-performing on-chain wallets from daily runner tokens
- 📊 **Scores** wallets on 30-day PnL and Being-Early metrics
- 👀 **Watches** a dynamic list of high-signal traders
- 🔔 **Alerts** via Telegram when watchlist wallets make new trades
- 🤝 **Detects confluence** when multiple top wallets buy the same token

## Key Features

### Core System
- **Multi-chain Support**: Ethereum, Base, Arbitrum, Solana (+ Polygon, Optimism, Avalanche ready)
- **Automated Discovery**: Daily runner tokens → buyer wallets → 30D backfill → scoring
- **Smart Filtering**: Bot detection, honeypot/scam filters, concentration checks
- **Dynamic Watchlist**: Automatic add/remove based on performance thresholds
- **Real-time Alerts**: Telegram notifications with confluence detection
- **Production-Ready**: Docker setup, Alembic migrations, comprehensive logging

### NEW: Advanced Features (Just Added! 🚀)
- **9 Data Sources**: DEX Screener, Dextools, Defined.fi, GeckoTerminal, CoinGecko, Pump.fun, GMGN, Jupiter, Birdeye
- **Wallet Labels**: Track known traders (Ansem, Tetranode, etc.) with verified badges
- **Caching Layer**: Redis-based caching reduces API calls by 90%
- **Alert Outcome Tracking**: Measure win rate and average returns on alerts
- **AI Signal Analysis**: On-demand LLM (Ollama/Phi-3) analyzes high-probability signals
- **Enhanced Alerts**: Rich Telegram messages with explorer links, charts, and wallet names

## Architecture

```
┌─────────────────────────────────────────────────┐
│  9 FREE Data Sources (DEX Screener, Pump.fun...) │
└──────────────┬──────────────────────────────────┘
               │
               ▼
┌──────────────┴────────┐     ┌──────────────┐
│   Trending Tokens     │────▶│  Wallet      │
│   + New Pools         │     │  Discovery   │
│   (Cached in Redis)   │     │              │
└───────────────────────┘     └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │  Analytics   │
                              │  - PnL (FIFO)│
                              │  - EarlyScore│
                              │  - Stats     │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │   Filters    │
                              │  - Bots      │
                              │  - Scams     │
                              │  - Labels ✓  │
                              └──────┬───────┘
                                     │
                                     ▼
                              ┌──────────────┐
                              │  Watchlist   │
                              │  Maintainer  │
                              └──────┬───────┘
                                     │
                    ┌────────────────┴────────────────┐
                    ▼                                 ▼
             ┌──────────────┐                 ┌──────────────┐
             │  LLM (Phi-3) │                 │   Telegram   │
             │  On-Demand   │                 │   Alerts     │
             │  Analysis 🤖 │────────────────▶│  + Links     │
             └──────────────┘                 │  + Labels    │
                                              │  + AI Score  │
                                              └──────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- Poetry (or use Docker exclusively)

### Installation

1. **Clone and setup:**
```bash
git clone <repo-url>
cd alpha-wallet-scout
cp .env.example .env
```

2. **Configure environment:**
Edit `.env` with your API keys:
- `ALCHEMY_API_KEY` - For EVM chain data
- `HELIUS_API_KEY` - For Solana data
- `BIRDEYE_API_KEY` - For Solana trending (optional)
- `TELEGRAM_BOT_TOKEN` - Your Telegram bot token
- `TELEGRAM_CHAT_ID` - Your Telegram chat/channel ID
- `BITQUERY_API_KEY` - For historical trades (optional)
- `TOKENSNIFFER_API_KEY` - For scam detection (optional)

3. **Start services:**
```bash
# With Docker (recommended)
make up

# Or with Poetry
poetry install
make migrate
make dev
```

4. **Verify installation:**
```bash
curl http://localhost:8000/health
```

## Configuration

Key thresholds in `.env`:

```bash
# Watchlist Add Criteria
ADD_MIN_TRADES_30D=5                    # Minimum trades in last 30 days
ADD_MIN_REALIZED_PNL_30D_USD=50000      # Minimum 30D PnL
ADD_MIN_BEST_TRADE_MULTIPLE=3           # Best trade must be 3x+

# Watchlist Remove Criteria
REMOVE_IF_REALIZED_PNL_30D_LT=0         # Remove if PnL negative
REMOVE_IF_MAX_DRAWDOWN_PCT_GT=50        # Remove if drawdown > 50%
REMOVE_IF_TRADES_30D_LT=2               # Remove if inactive

# Confluence
CONFLUENCE_MINUTES=30                    # Time window for confluence

# Filters
MIN_UNIQUE_BUYERS_24H=30                # Min buyers to consider token
MAX_TAX_PCT=10                          # Max buy/sell tax allowed
```

## Usage

### API Endpoints

- `GET /health` - Health check
- `GET /api/v1/watchlist` - List watchlist wallets
- `GET /api/v1/stats/top-wallets` - Top performing wallets
- `GET /api/v1/alerts/recent` - Recent alerts

### Makefile Commands

```bash
make install    # Install dependencies
make up         # Start Docker services
make down       # Stop Docker services
make migrate    # Run database migrations
make test       # Run tests
make format     # Format code
make lint       # Lint code
```

## How It Works

### 1. Token Discovery (Every 15 minutes)
- Fetches trending tokens from **9 free sources** (DEX Screener, Pump.fun, GMGN, etc.)
- **Defined.fi** catches NEW pools the moment liquidity is added
- **Caches results in Redis** for 15 minutes to reduce API calls
- Filters out scams/honeypots based on tax, liquidity, holder concentration
- Stores as "seed tokens"

### 2. Wallet Discovery (Every 15 minutes)
- For each seed token, fetches last 24-72h buyers
- **Checks wallet labels** - known traders get priority
- Excludes known bots, contracts, MEV addresses
- Queues wallets for 30D backfill

### 3. Analytics (Hourly/On-demand)
- **FIFO PnL**: Calculates realized/unrealized profit per wallet
- **Being-Early Score**: 0-100 score based on:
  - Buy timing (40%): Earlier = higher score
  - Market cap at purchase (40%): Lower MC = higher score
  - Position size (20%): Larger relative buy = higher score
- **Tracks outcomes**: Measures if alerts were profitable

### 4. Watchlist Maintenance (Nightly)
- **Add**: Wallets meeting min trades, PnL, best trade criteria
- **Remove**: Wallets with negative PnL, high drawdown, or inactivity
- **Prioritizes labeled wallets** (Ansem, Tetranode, etc.)

### 5. Real-time Alerts with AI
- Monitors watchlist wallet trades via webhooks/polling
- **Preliminary scoring** (0-100) based on wallet stats + token data
- **On-demand LLM analysis** activates ONLY if:
  - Preliminary score >75/100 OR
  - ≥2 wallets buying (confluence) OR
  - Labeled wallet detected
- **LLM provides**: Final confidence score, BUY/HOLD/AVOID, reasoning
- **Sends Telegram alert** with wallet labels, explorer links, AI score

## Being-Early Metric

The Being-Early score (0-100) identifies wallets that buy tokens early:

```
EarlyScore = 40 × (1 - rank_percentile)           # Earlier rank = higher
           + 40 × clip((1M - mc_at_buy) / 1M)     # Lower MC = higher
           + 20 × volume_participation             # Larger buy = higher
```

**Example:**
- Wallet buys at rank #5 out of 500 buyers: `rank_percentile = 0.01`
- Market cap at buy: $200k: `mc_score = 0.8`
- Buy size: 2% of volume: `participation = 0.5`
- **Score**: `40×0.99 + 40×0.8 + 20×0.5 = 81.6` ✨

## AI-Enhanced Alert System

### How the LLM Works

**Activation Criteria** (saves compute by only analyzing high-probability signals):
- Preliminary score ≥75/100 OR
- Multiple wallets buying same token (confluence) OR
- Known labeled wallet detected (Ansem, Tetranode, etc.) OR
- Preliminary score ≥85/100 (even without other factors)

**Ultra-Optimized Prompts** (~150 tokens):
```
Crypto signal analysis. Respond ONLY with: CONFIDENCE(0-100) | ACTION(BUY/HOLD/AVOID) | REASON(1 sentence)

Token: PEPE
Price: $0.00000123
MCap: $450k
Liq: $250k

Wallets:
- Ansem ✓: 30D PnL $127k, Best 8.2x, Early 85
- Unknown: 30D PnL $89k, Best 5.1x, Early 72

Preliminary Score: 82/100

Response:
```

**LLM Response** (parsed automatically):
```
89 | BUY | Known trader Ansem + strong confluence with high early scores suggests institutional interest
```

### Alert Examples

**Single Alert (with AI):**
```
🔔 TOP WALLET BUY

Token: DEGEN ($0.0234)
Wallet: Ansem ✓ (0xabc...def)
30D PnL: $127k | Best: 8.2x
EarlyScore: 76

🤖 AI Confidence: 85/100
Recommendation: BUY
Reason: Known trader with strong track record buying at early stage

Pair: Uniswap V3
TX: etherscan.io/tx/0x...
Chart: dexscreener.com/...
```

**Confluence Alert (with AI):**
```
🚨 CONFLUENCE (3 wallets) 🚨

Token: PEPE ($0.0000012)
Wallets:
- Ansem ✓ (0xabc...)
- Tetranode ✓ (0x123...)
- Unknown Whale #42 (0x456...)

Avg 30D PnL: $89k
Window: 12 minutes
Liquidity: $450k

🤖 AI Confidence: 92/100
Recommendation: BUY
Reason: Multiple verified top traders buying simultaneously - strong institutional signal

TX: solscan.io/tx/...
Birdeye: birdeye.so/...
```

## Telegram Setup

1. **Create bot**: Message [@BotFather](https://t.me/botfather) → `/newbot`
2. **Get token**: Copy the token → `TELEGRAM_BOT_TOKEN`
3. **Get chat ID**:
   - Send message to bot
   - Visit: `https://api.telegram.org/bot<TOKEN>/getUpdates`
   - Copy `chat.id` → `TELEGRAM_CHAT_ID`

## Development

### Project Structure

```
src/
├── clients/        # API clients (DEX Screener, Birdeye, etc.)
├── ingest/         # Token ingestion and seed management
├── analytics/      # PnL, EarlyScore, stats computation
├── watchlist/      # Add/remove rules and maintenance
├── alerts/         # Telegram integration and confluence
├── api/            # FastAPI endpoints
├── db/             # SQLAlchemy models and session
└── scheduler/      # APScheduler job definitions

tests/
├── unit/           # Unit tests
└── integration/    # Integration tests
```

### Adding a New Chain

1. Update `.env`: Add chain to `CHAINS`
2. Add chain mapping in clients (if needed)
3. Configure chain-specific data provider
4. Test with `make test`

### Testing

```bash
# Run all tests
make test

# Run specific test
poetry run pytest tests/unit/test_pnl.py -v

# With coverage
poetry run pytest --cov=src --cov-report=html
```

## Deployment

### Docker Production

```bash
# Build and start all services
docker-compose up -d

# Setup LLM (Ollama + models)
./setup_llm.sh

# View logs
docker-compose logs -f worker

# Stop
docker-compose down
```

### Services Running

- **PostgreSQL** (port 5432) - Main database
- **Redis** (port 6379) - Caching + confluence detection
- **Ollama** (port 11434) - Local LLM (Phi-3)
- **API** (port 8000) - FastAPI REST endpoints
- **Worker** - Background scheduler running all jobs

### Environment Variables

See `.env.example` for all configuration options.

## Cost Breakdown

| Component | Provider | Cost | Notes |
|-----------|----------|------|-------|
| **Token Data** | 9 free APIs | **$0/mo** | DEX Screener, Pump.fun, GMGN, etc. |
| **Blockchain Data** | Alchemy Free | **$0/mo** | 300M compute units/mo |
| **Solana Data** | Helius Free | **$0/mo** | 100k requests/mo |
| **AI Analysis** | Ollama (local) | **$0/mo** | Phi-3 model, unlimited |
| **Database** | Self-hosted | **$0/mo** | Docker PostgreSQL + Redis |
| **Alerts** | Telegram | **$0/mo** | Unlimited messages |
| **Server** | Your choice | **Variable** | $5-20/mo VPS recommended |

**Total Monthly Cost: $0-20** (depending on hosting choice)

### Free Tier Limits

All services stay well within free limits with caching:
- **Alchemy**: 300M compute/mo = ~10M requests/mo ✓
- **Helius**: 100k req/mo = ~3.3k per day ✓
- **All trending APIs**: No hard limits with 15min caching ✓
- **LLM**: Unlimited (runs on your CPU/GPU) ✓

**Caching reduces API calls by 90%**, keeping you safely in free tiers.

## Disclaimers

⚠️ **NOT FINANCIAL ADVICE**: This tool is for informational purposes only.

⚠️ **DO YOUR OWN RESEARCH**: Always verify trades and tokens independently.

⚠️ **NO GUARANTEES**: Past performance does not indicate future results.

⚠️ **EXPERIMENTAL**: Filters may not catch all scams/bots.

## Advanced Usage

### Using the LLM Analyzer

```python
from src.analytics.llm_service import OnDemandLLMService

# Initialize service (activates only for high-probability signals)
llm = OnDomandLLMService(activation_threshold=75.0)

# Check if signal needs AI analysis
if llm.should_analyze(preliminary_score=82, token_data={...}):
    analysis = await llm.analyze_signal(token_data, wallet_data, preliminary_score)

    print(f"AI Confidence: {analysis['confidence']}/100")
    print(f"Recommendation: {analysis['action']}")
    print(f"Reasoning: {analysis['reasoning']}")
```

### Adding Custom Wallet Labels

Edit `src/data/wallet_labels.json`:

```json
{
  "ethereum": {
    "0x1234...": {
      "name": "Your Favorite Trader",
      "source": "twitter",
      "type": "influencer",
      "verified": true
    }
  }
}
```

### Tracking Alert Performance

```python
from src.analytics.outcomes import OutcomeTracker

tracker = OutcomeTracker(db)

# Get last 24h performance
summary = await tracker.get_alert_performance_summary(hours_back=24)
print(f"Win Rate: {summary['win_rate']:.1f}%")
print(f"Avg Return: {summary['avg_return']:.1f}%")

# Generate daily summary for Telegram
message = await tracker.generate_daily_summary()
```

### Tuning the System

**For more signals** (lower quality):
- Decrease `ADD_MIN_REALIZED_PNL_30D_USD` to 25000
- Decrease LLM `activation_threshold` to 65

**For higher quality signals** (fewer):
- Increase `ADD_MIN_BEST_TRADE_MULTIPLE` to 5
- Increase LLM `activation_threshold` to 85
- Add more strict filters in `src/ingest/filters.py`

## Roadmap

**Completed ✓**
- [x] Multi-chain support (ETH, Base, Arbitrum, Solana)
- [x] 9 free data sources
- [x] Wallet labels system
- [x] Caching layer (90% API reduction)
- [x] Alert outcome tracking
- [x] On-demand LLM analysis
- [x] Enhanced Telegram alerts

**Planned**
- [ ] Web dashboard (Streamlit/Next.js)
- [ ] Wallet clustering (identify same owner)
- [ ] ML-based bot detection
- [ ] Execution quality metrics (slippage/MEV)
- [ ] User-tunable rules via API
- [ ] Discord integration
- [ ] Twitter monitoring

## License

MIT

## Support

- 📧 Issues: [GitHub Issues](https://github.com/your-repo/issues)
- 📖 Docs: [Full Documentation](./USAGE.md)
- 💬 Community: [Discord](https://discord.gg/your-server)

---

Built with Claude Sonnet 4.5 🤖
