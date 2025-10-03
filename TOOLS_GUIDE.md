# 🛠️ Tools & Data Sources Guide

Complete guide to all free tools and APIs integrated into Alpha Wallet Scout.

---

## 📊 Data Sources (All FREE)

### **Trending Token Sources**

| Source | Coverage | Rate Limit | Data Quality |
|--------|----------|------------|--------------|
| **DEX Screener** | All chains | Unlimited | ⭐⭐⭐⭐⭐ |
| **GeckoTerminal** | All chains | Unlimited | ⭐⭐⭐⭐⭐ |
| **Dextools** | EVM chains | Generous | ⭐⭐⭐⭐ |
| **Defined.fi** | Multi-chain | GraphQL | ⭐⭐⭐⭐⭐ |
| **CoinGecko** | Popular tokens | 50 req/min | ⭐⭐⭐⭐ |
| **Pump.fun** | Solana only | Unlimited | ⭐⭐⭐⭐ |
| **GMGN.ai** | Solana only | Generous | ⭐⭐⭐⭐⭐ |
| **Jupiter** | Solana only | Unlimited | ⭐⭐⭐⭐ |
| **Birdeye** | Solana only | 100 req/day | ⭐⭐⭐⭐⭐ |

---

## 🔧 How to Use Each Tool

### 1. DEX Screener (Already Active)
```python
from src.clients.dexscreener import DexScreenerClient

client = DexScreenerClient()
tokens = await client.get_trending_tokens("ethereum")
```

**What it provides:**
- Trending tokens across all chains
- Real-time price, liquidity, volume
- Pair addresses and DEX info

---

### 2. Dextools (NEW - Just Added)
```python
from src.clients.dextools import DextoolsClient

client = DextoolsClient()
hot_tokens = await client.get_hot_pairs("ether")
```

**What it provides:**
- Hot/trending pairs
- Community engagement metrics
- Wallet holder data

---

### 3. Defined.fi (NEW - Just Added)
```python
from src.clients.defined import DefinedClient

client = DefinedClient()
new_pools = await client.get_new_pools(
    network_filter=[1, 8453],  # Ethereum, Base
    limit=50
)
```

**What it provides:**
- NEW pools (super early catches!)
- GraphQL flexibility
- Cross-chain data

**Why it's powerful:** Catches tokens RIGHT when liquidity is added

---

### 4. CoinGecko (NEW - Just Added)
```python
from src.clients.coingecko import CoinGeckoClient

client = CoinGeckoClient()
trending = await client.get_trending_coins()
```

**What it provides:**
- Trending coins (different algorithm than DEX screener)
- Market cap data
- Cross-platform visibility

---

### 5. Pump.fun (NEW - Solana Memecoins)
```python
from src.clients.pumpfun import PumpFunClient

client = PumpFunClient()

# Get brand new tokens
new_tokens = await client.get_new_tokens(limit=50)

# Get trending
trending = await client.get_trending_tokens()

# Get trades for a specific token
trades = await client.get_token_trades("MINT_ADDRESS")
```

**What it provides:**
- NEW Solana memecoins (instant launches)
- Creator wallets
- Trade history per token
- Bonding curve info

**Why it's powerful:** Pump.fun is where most Solana memecoins launch first

---

### 6. GMGN.ai (NEW - Solana Analytics)
```python
from src.clients.gmgn import GMGNClient

client = GMGNClient()

# Trending by volume
trending = await client.get_trending_tokens(order_by="volume_24h")

# New tokens
new = await client.get_new_tokens()

# Top holders
holders = await client.get_token_holders("TOKEN_ADDRESS")
```

**What it provides:**
- Advanced Solana analytics
- Smart money labels
- Holder distribution
- Creation timestamps

---

### 7. Jupiter (NEW - Solana DEX Aggregator)
```python
from src.clients.jupiter import JupiterClient

client = JupiterClient()

# Get price
price = await client.get_token_price("MINT_ADDRESS")

# Get verified tokens
tokens = await client.get_token_list()
```

**What it provides:**
- Real-time Solana prices
- Verified token list
- Routing data

---

## 🏷️ Wallet Labels (NEW Feature)

Track known wallets with custom labels:

```python
from src.utils.wallet_labels import wallet_labels

# Check if wallet is labeled
if wallet_labels.is_labeled(wallet_address, "ethereum"):
    name = wallet_labels.get_name(wallet_address, "ethereum")
    print(f"This is {name}!")

# Add a new label
wallet_labels.add_label(
    wallet_address="0x123...",
    chain_id="ethereum",
    name="Ansem",
    source="twitter",
    wallet_type="influencer",
    verified=True
)

# Save labels
wallet_labels.save_labels()
```

**Pre-loaded labels:**
- Ansem (ETH & SOL)
- Tetranode
- Machi Big Brother
- Toly (Solana founder)

**Add your own!** Edit: `src/data/wallet_labels.json`

---

## 💾 Caching Layer (NEW - Reduce API Calls)

Automatically cache API responses:

```python
from src.utils.cache import cache

# Use decorator
@cache.cached(ttl=900)  # 15 min cache
async def get_trending_tokens(chain):
    # This will only hit API every 15 min
    return await client.get_trending_tokens(chain)

# Manual cache
cache.set("my_key", {"data": "value"}, ttl=300)
value = cache.get("my_key")
```

**Benefits:**
- Stay within free API limits
- 10x faster repeated requests
- Automatic expiry

---

## 📈 Alert Outcome Tracking (NEW)

Track if your alerts are profitable:

```python
from src.analytics.outcomes import OutcomeTracker

tracker = OutcomeTracker(db)

# Track a specific alert
outcome = await tracker.track_alert_outcome(alert_id=123, hours_after=24)

# Get performance summary
summary = await tracker.get_alert_performance_summary(hours_back=24)
print(f"Win rate: {summary['win_rate']:.1f}%")

# Generate daily summary for Telegram
message = await tracker.generate_daily_summary()
```

**What it tracks:**
- Price change after alert
- Win/loss ratio
- Average return
- Alert precision

---

## 🤖 LLM Signal Analysis (NEW - POWERFUL!)

Use AI to analyze signals:

```python
from src.analytics.llm_analyzer import LLMSignalAnalyzer

analyzer = LLMSignalAnalyzer(model="phi3:latest")

# Analyze a token buy signal
analysis = await analyzer.analyze_token_signal(
    token_data={
        "symbol": "PEPE",
        "price_usd": 0.000001,
        "liquidity_usd": 500000,
        "volume_24h_usd": 2000000,
        "holder_count": 15000,
    },
    wallet_data=[
        {"pnl_30d": 125000, "best_multiple": 8.2, "earlyscore": 85},
        {"pnl_30d": 89000, "best_multiple": 5.1, "earlyscore": 72},
    ],
)

print(f"Signal Strength: {analysis['signal_strength']}/100")
print(f"Recommendation: {analysis['recommendation']}")
print(f"Reasoning: {analysis['reasoning']}")
print(f"Red Flags: {analysis['red_flags']}")
```

**LLM analyzes:**
- Wallet quality
- Token fundamentals
- Risk factors
- Market conditions

**Returns:**
- Signal strength (0-100)
- Recommendation (BUY/HOLD/AVOID)
- Detailed reasoning
- Red flags & positive signals

---

### Setup Ollama (Local LLM)

**Option 1: Docker (Included)**
```bash
# Start Ollama
docker-compose up -d ollama

# Install models
./setup_llm.sh

# Models will be downloaded:
# - llama3.2:latest (3B) - Fast
# - phi3:latest (3.8B) - Best for structured output
# - qwen2.5:3b (3B) - Alternative
```

**Option 2: Use OpenAI/Claude (if you have API key)**
```python
from src.analytics.llm_analyzer import OpenAIAnalyzer

analyzer = OpenAIAnalyzer(
    api_key="your-key",
    model="gpt-4o-mini"  # Cheap: $0.15/1M tokens
)
```

---

## 🎯 Recommended Tool Stack

### **For Maximum Coverage (FREE):**
1. ✅ DEX Screener (all chains)
2. ✅ Defined.fi (catch NEW pools)
3. ✅ GMGN + Pump.fun (Solana)
4. ✅ Local LLM analysis (Ollama)

### **For Best Data Quality:**
1. ✅ All trending sources (aggregate signals)
2. ✅ Wallet labels (know WHO is buying)
3. ✅ Outcome tracking (validate system)
4. ✅ LLM analysis (AI insights)

---

## 💡 Pro Tips

### 1. Aggregate Multiple Sources
```python
# Get trending from ALL sources
all_trending = []
all_trending.extend(await dexscreener.get_trending_tokens("ethereum"))
all_trending.extend(await dextools.get_hot_pairs("ether"))
all_trending.extend(await defined.get_new_pools([1]))

# Deduplicate and rank by appearance count
```

### 2. Use LLM for Final Filter
```python
# After your filters, use LLM as final check
if passes_basic_filters(token):
    llm_analysis = await analyzer.analyze_token_signal(...)

    if llm_analysis['signal_strength'] > 70:
        send_alert(token)
```

### 3. Track Everything
```python
# Log all signals (not just alerts sent)
# This lets you backtest different thresholds
log_signal(token, score, sent_alert=True/False)
```

### 4. Label Wallets Continuously
```python
# When you see a wallet perform well, label it!
if wallet_pnl > 100000:
    wallet_labels.add_label(
        wallet, chain, f"Unknown Whale #{count}",
        source="system", verified=False
    )
```

---

## 📊 Cost Breakdown

| Tool | Cost | Rate Limit | Notes |
|------|------|-----------|-------|
| All trending APIs | **$0/mo** | Generous | Stay under limits with caching |
| Ollama (local LLM) | **$0/mo** | Unlimited | Uses your CPU/GPU |
| Helius FREE | **$0/mo** | 100k req/mo | Plenty for webhooks |
| Alchemy FREE | **$0/mo** | 300M compute | More than enough |

**Total: $0/month** 🎉

---

## 🚀 Next Steps

1. **Enable all sources** in `src/ingest/runners.py`
2. **Add wallet labels** to `src/data/wallet_labels.json`
3. **Setup Ollama** with `./setup_llm.sh`
4. **Enable outcome tracking** in scheduler
5. **Test LLM analysis** on a few signals

---

## 📚 API Documentation Links

- [DEX Screener](https://docs.dexscreener.com/)
- [GeckoTerminal](https://www.geckoterminal.com/dex-api)
- [Defined GraphQL](https://docs.defined.fi/)
- [Pump.fun API](https://docs.pump.fun/)
- [Ollama](https://ollama.ai/docs)

---

**Questions? Check the main [README.md](README.md) or [USAGE.md](USAGE.md)**
