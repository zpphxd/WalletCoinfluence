# Solana Whale Tracking Implementation Plan

## 🎯 Goal
Enable tracking of 5 Solana whales ($51.9M verified performance) to capture memecoin signals on the most active chain for memecoins.

---

## 📊 Current State

### What We Have
- ✅ 5 Solana whale addresses in database (deactivated)
- ✅ Solscan client skeleton created
- ✅ Multi-chain architecture ready
- ✅ Stablecoin filtering working
- ✅ Confluence detection system ready

### What's Blocking
- ❌ Helius API returning 401/404 errors
- ❌ No reliable way to fetch Solana wallet transactions
- ❌ No DEX swap detection for Solana (Raydium, Jupiter, Orca)
- ❌ Token price lookups incomplete for Solana tokens

---

## 🛠️ Implementation Strategy

### **Phase 1: API Research & Selection (2-3 hours)**

**Objective:** Find the best API(s) for Solana data

**Options to Test:**

#### Option A: Helius (Paid - $50-250/month)
- **Pros:** Enhanced transaction parsing, DeFi categorization
- **Cons:** Already tried and failed (401 errors)
- **Status:** Need to debug API key + endpoint
- **Test:** https://docs.helius.dev/solana-apis/enhanced-transactions-api

#### Option B: Solscan (Free → Paid)
- **Pros:** Public API, no key required for basic
- **Cons:** Limited to 100 requests/min, need transaction parsing
- **Status:** Client created but not fully implemented
- **Test:** https://public-api.solscan.io/docs

#### Option C: Birdeye (Free → Paid)
- **Pros:** Good price data, wallet portfolio API
- **Cons:** 1000 calls/day limit on free tier
- **Status:** Client exists, need to add wallet tracking
- **Test:** https://docs.birdeye.so/reference/get_defi_txs_token

#### Option D: Jupiter Aggregator (Free)
- **Pros:** Best for swap detection, no auth required
- **Cons:** Only shows swaps (not transfers)
- **Status:** Not implemented
- **Test:** https://station.jup.ag/api-v6/get-user-swap-history

#### Option E: Public Solana RPC (Free)
- **Pros:** No rate limits, official
- **Cons:** Need to parse raw transactions ourselves
- **Status:** Not implemented
- **Test:** https://docs.solana.com/api/http#getsignaturesforaddress

**Recommendation:** Try in order: **Jupiter → Birdeye → Solscan → Helius → Public RPC**

---

### **Phase 2: Implement Transaction Fetching (4-6 hours)**

**Step 1: Jupiter Integration (2 hours)**
```python
# /Users/zachpowers/Wallet Signal/src/clients/jupiter.py

class JupiterClient(BaseAPIClient):
    """Jupiter Aggregator API for Solana swap history."""

    def __init__(self):
        super().__init__(base_url="https://api.jup.ag/v6")

    async def get_wallet_swaps(self, wallet_address: str, limit: int = 100):
        """Get recent swaps for a wallet (DEX trades only)."""
        response = await self.get(
            f"/swaps",
            params={
                "ownerAddress": wallet_address,
                "limit": min(limit, 100)
            }
        )

        # Parse Jupiter swap format into our standard format
        trades = []
        for swap in response.get("data", []):
            trades.append({
                "tx_hash": swap.get("signature"),
                "timestamp": datetime.fromtimestamp(swap.get("timestamp")),
                "token_address": swap.get("outputMint"),  # Token bought
                "side": "buy",  # Jupiter shows successful swaps
                "amount": float(swap.get("outputAmount", 0)),
                "price_usd": float(swap.get("priceUSD", 0)),
                "value_usd": float(swap.get("value", 0)),
                "dex": "jupiter",
            })

        return trades
```

**Step 2: Birdeye Wallet Transactions (2 hours)**
```python
# Update /Users/zachpowers/Wallet Signal/src/clients/birdeye.py

async def get_wallet_transactions(self, wallet_address: str, chain: str = "solana", limit: int = 100):
    """Get wallet's DeFi transactions."""
    response = await self.get(
        f"/defi/txs/wallet",
        params={
            "wallet": wallet_address,
            "tx_type": "swap",  # Only swaps (DEX trades)
            "limit": min(limit, 100)
        },
        headers={"X-API-KEY": self.api_key}  # Requires API key
    )

    # Parse Birdeye format
    trades = []
    for tx in response.get("data", {}).get("items", []):
        trades.append({
            "tx_hash": tx.get("txHash"),
            "timestamp": datetime.fromtimestamp(tx.get("blockUnixTime")),
            "token_address": tx.get("to", {}).get("address"),
            "side": "buy" if tx.get("side") == "buy" else "sell",
            "amount": float(tx.get("to", {}).get("amount", 0)),
            "price_usd": float(tx.get("to", {}).get("uiAmount", 0)) / float(tx.get("to", {}).get("amount", 1)),
            "value_usd": float(tx.get("volumeUSD", 0)),
            "dex": tx.get("source", "unknown"),
        })

    return trades
```

**Step 3: Fallback Chain (1 hour)**
Update wallet_monitor.py:
```python
if wallet.chain_id == "solana":
    # Try Jupiter first (free, swap-only)
    from src.clients.jupiter import JupiterClient
    client = JupiterClient()
    recent_txs = await client.get_wallet_swaps(wallet.address, limit=100)

    # Fallback to Birdeye if Jupiter returns nothing
    if not recent_txs:
        from src.clients.birdeye import BirdeyeClient
        client = BirdeyeClient()
        recent_txs = await client.get_wallet_transactions(wallet.address, limit=100)

    # Fallback to Solscan if both fail
    if not recent_txs:
        from src.clients.solscan import SolscanClient
        client = SolscanClient()
        recent_txs = await client.get_wallet_transactions(wallet.address, limit=100)

    logger.info(f"📍 Tracking Solana whale: {wallet.address[:16]}... ({len(recent_txs)} txs)")
```

**Step 4: Testing (1 hour)**
```bash
# Test each whale individually
docker exec wallet_scout_worker python3 -c "
import asyncio
from src.clients.jupiter import JupiterClient
from src.clients.birdeye import BirdeyeClient

SOLANA_WHALES = [
    '4EtAJ1p8RjqccEVhEhaYnEgQ6kA4JHR8oYqyLFwARUj6',  # Trump whale
    'EdCNh8EzETJLFphW8yvdY7rDd8zBiyweiz8DU5gUUka',   # WIF whale
    # ... etc
]

async def test():
    jupiter = JupiterClient()
    birdeye = BirdeyeClient()

    for whale in SOLANA_WHALES:
        print(f'\n🔍 Testing {whale[:16]}...')

        # Try Jupiter
        jup_txs = await jupiter.get_wallet_swaps(whale, limit=10)
        print(f'  Jupiter: {len(jup_txs)} swaps')

        # Try Birdeye
        bird_txs = await birdeye.get_wallet_transactions(whale, limit=10)
        print(f'  Birdeye: {len(bird_txs)} txs')

asyncio.run(test())
"
```

---

### **Phase 3: Solana-Specific Features (3-4 hours)**

**Step 1: DEX Detection for Solana (1 hour)**
Update `/Users/zachpowers/Wallet Signal/src/utils/dex_routers.py`:
```python
SOLANA_DEX_PROGRAMS = {
    # Raydium
    "675kpx9ma8prgnteknu24sj3xusezh1cr2g4d5gshttchzbaq4vx": "Raydium",
    # Jupiter
    "jupag6ctndsmknzxkglbwfdfzfqhrvq2r8vmdukevchz5zkz": "Jupiter Aggregator",
    # Orca
    "9w959d8ufeumk1hfb7fjhqkjp7wvccm5x9qqbfuahqxv3lzd": "Orca",
    # Meteora
    "meteoraag6aj3evrmgadcqxkhjlhdvvgqcrr8uxbsrwcxdqcg": "Meteora",
}

def is_solana_dex_swap(program_id: str) -> bool:
    """Check if Solana program is a DEX."""
    return program_id.lower() in SOLANA_DEX_PROGRAMS
```

**Step 2: Solana Stablecoin Filter (30 min)**
Update wallet_monitor.py:
```python
STABLECOINS_AND_WRAPPED = {
    # ... existing Ethereum/Base/Arbitrum

    # Solana
    "es9vmfrzacermjfrf4h2fyd4kconky11mcce8benwnyb",  # USDC (Solana)
    "eph6pci39uyewu5mccelbytzf4mxiwukjqgjdaedm1vvb",  # USDT (Solana)
    "so11111111111111111111111111111111111111112",  # SOL (wrapped)
}
```

**Step 3: Solana Token Price Lookups (1 hour)**
Already works - DexScreener supports Solana!

**Step 4: Add Solana-Specific Logging (30 min)**
```python
logger.info(f"🔸 Solana whale trade detected: {wallet.address[:8]}... bought {token_address[:8]}... for ${value_usd:.2f} on {dex}")
```

---

### **Phase 4: Activation & Testing (2-3 hours)**

**Step 1: Re-activate Solana Whales**
```sql
UPDATE custom_watchlist_wallets
SET is_active = true
WHERE chain_id = 'solana';
```

**Step 2: Monitor First Cycle (30 min)**
Watch logs for:
- ✅ "📍 Tracking Solana whale..." messages
- ✅ Transaction counts fetched
- ✅ No API errors
- ⚠️ Rate limit warnings

**Step 3: Validate Data Quality (1 hour)**
```bash
# Check Solana trades in database
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    wallet_address,
    token_address,
    side,
    usd_value,
    venue,
    ts
FROM trades
WHERE chain_id = 'solana'
ORDER BY ts DESC
LIMIT 20;
"
```

**Step 4: End-to-End Test (1 hour)**
- Wait for Solana whale confluence (5+ whales buying same token)
- Verify paper trading executes
- Check alert sent to logs
- Validate all data fields populated

---

## 📅 Timeline & Priorities

### **Option A: Quick Implementation (6-8 hours)**
- **Week 1:** Jupiter + Birdeye integration
- **Week 2:** Testing + activation
- **Result:** Basic Solana tracking working

### **Option B: Production-Grade (12-16 hours)**
- **Week 1:** All API options tested, best one chosen
- **Week 2:** Full DEX detection, comprehensive testing
- **Week 3:** Rate limit monitoring, optimization
- **Result:** Bulletproof Solana tracking

### **Option C: After Ethereum MVP Proves ROI (Recommended)**
- **Now:** Focus 100% on Ethereum whale validation
- **Week 3-4:** Once we have 5-10 profitable Ethereum signals
- **Then:** Implement Solana properly with proven architecture
- **Advantage:** Learn from Ethereum what works, apply to Solana

---

## 💰 Cost Analysis

### API Pricing (Monthly)

**Free Tier Options:**
- Jupiter API: FREE (unlimited swaps)
- Public Solana RPC: FREE (self-hosted node or public endpoint)
- Birdeye: FREE (1000 calls/day = ~300 whale checks/day)
- Solscan: FREE (100 calls/min = 144k/day)

**Paid Tier (If Needed):**
- Helius: $50-250/month (enhanced transactions)
- Birdeye Pro: $99/month (10k calls/day)
- Quicknode: $49-299/month (dedicated Solana RPC)

**Recommended Start:** FREE (Jupiter + Birdeye + Solscan)

**Upgrade Trigger:** When tracking >20 Solana whales

---

## 🎯 Success Criteria

### Phase 1 Complete When:
- ✅ Can fetch 100+ transactions for each Solana whale
- ✅ Trades parsed with token_address, amount, price, DEX
- ✅ No rate limit errors for 24 hours

### Phase 2 Complete When:
- ✅ Solana confluence detected (5+ whales buying same token)
- ✅ Paper trading executes on Solana memecoin
- ✅ All data matches Ethereum quality

### Production-Ready When:
- ✅ 3+ profitable Solana memecoin signals captured
- ✅ Win rate >50% on Solana trades
- ✅ Average Solana pump >20% within 30 min

---

## 🚨 Risks & Mitigations

### Risk 1: API Rate Limits
**Mitigation:**
- 60-second caching on all price lookups ✅
- Fallback chain: Jupiter → Birdeye → Solscan
- Monitor failure counts, auto-disable broken APIs

### Risk 2: Transaction Parsing Complexity
**Mitigation:**
- Start with Jupiter (pre-parsed swaps)
- Only parse successful DEX swaps
- Skip complex program interactions

### Risk 3: Solana Memecoin Spam
**Mitigation:**
- Stablecoin filter already implemented ✅
- Add SOL/WSOL filter
- Require $1k+ trade size minimum

### Risk 4: Cost Escalation
**Mitigation:**
- Start with free tiers
- Only upgrade when >20 whales tracked
- Calculate ROI: $99/month API << $1000s in alpha

---

## 📝 Implementation Checklist

### Pre-Implementation
- [ ] Choose primary API (Jupiter recommended)
- [ ] Test API with 1 whale manually
- [ ] Verify rate limits acceptable
- [ ] Check pricing if applicable

### Core Implementation
- [ ] Create Jupiter client (`src/clients/jupiter.py`)
- [ ] Update Birdeye client with wallet transactions
- [ ] Implement fallback chain in wallet_monitor.py
- [ ] Add Solana DEX detection to dex_routers.py
- [ ] Add Solana stablecoins to filter list

### Testing
- [ ] Test each API with 5 whale addresses
- [ ] Verify transaction counts match expectations
- [ ] Check data quality (all fields populated)
- [ ] Monitor for rate limit errors

### Activation
- [ ] Re-activate 5 Solana whales in database
- [ ] Monitor first 24 hours
- [ ] Validate first confluence detection
- [ ] Measure API usage vs limits

### Production
- [ ] Capture 3+ Solana memecoin signals
- [ ] Calculate win rate
- [ ] Document API costs
- [ ] Update system documentation

---

## 🎓 Key Learnings from Ethereum Implementation

### What Worked
1. ✅ **Multi-source fallback** - DexScreener → Birdeye → CoinGecko
2. ✅ **Aggressive caching** - 60s TTL reduced calls by 90%
3. ✅ **Stablecoin filtering early** - Blocked noise before processing
4. ✅ **1000 tx lookback** - Captures 24-48h of whale activity

### Apply to Solana
1. Use same fallback pattern: Jupiter → Birdeye → Solscan
2. Cache all Solana price lookups (60s TTL)
3. Filter SOL/USDC/USDT before confluence detection
4. Start with 100 tx lookback, increase if needed

---

## 💡 Recommended Approach

### **IMMEDIATE (This Week):**
**DO NOT implement Solana yet** - Focus on Ethereum MVP

### **AFTER Ethereum Proves ROI (Week 3-4):**

**Day 1-2:** API Selection & Testing
- Test Jupiter API with all 5 whales
- Verify data quality matches Ethereum
- Check rate limits sustainable

**Day 3-4:** Implementation
- Create Jupiter client
- Update wallet_monitor.py with Solana logic
- Add Solana stablecoin filters

**Day 5:** Testing & Activation
- Re-activate 5 Solana whales
- Monitor first 24 hours
- Fix any issues

**Day 6-7:** Validation
- Wait for first Solana confluence
- Verify paper trading works
- Document results

### **Total Time:** 1 week of focused work

### **Prerequisites:**
- ✅ Ethereum system proves >50% win rate
- ✅ Have 5-10 profitable Ethereum signals documented
- ✅ Understand what makes a good signal vs noise

---

## 📚 Resources & Documentation

### API Documentation
- Jupiter: https://station.jup.ag/docs/apis/swap-api
- Birdeye: https://docs.birdeye.so/docs/solana-wallet-portfolio
- Solscan: https://public-api.solscan.io/docs
- Helius: https://docs.helius.dev/solana-apis/enhanced-transactions-api
- Solana RPC: https://docs.solana.com/api/http

### Solana DEX Documentation
- Raydium: https://raydium.gitbook.io/
- Jupiter: https://docs.jup.ag/
- Orca: https://docs.orca.so/
- Meteora: https://docs.meteora.ag/

### Whale Addresses (To Verify)
```python
SOLANA_WHALES = {
    "4EtAJ1p8RjqccEVhEhaYnEgQ6kA4JHR8oYqyLFwARUj6": "Trump Memecoin Whale ($489k)",
    "EdCNh8EzETJLFphW8yvdY7rDd8zBiyweiz8DU5gUUka": "WIF Mega Holder ($17.4M)",
    "8zFZHuSRuDpuAR7J6FzwyF3vKNx4CVW3DFHJerQhc7Zd": "Active Smart Money ($14.8M)",
    "8mZYBV8aPvPCo34CyCmt6fWkZRFviAUoBZr1Bn993gro": "POPCAT Insider ($12M+)",
    "5CP6zv8a17mz91v6rMruVH6ziC5qAL8GFaJzwrX9Fvup": "Sniper Trader ($7.2M)",
}
```

---

## ✅ Next Steps

1. **Save this document** for reference when ready to implement
2. **Focus on Ethereum MVP** - Prove ROI first
3. **When ready (Week 3-4):**
   - Review this plan
   - Test Jupiter API
   - Implement in 1 week sprint

**The Solana whales will still be there.** Better to implement it RIGHT than implement it NOW.

---

**Document Status:** READY FOR IMPLEMENTATION
**Last Updated:** October 6, 2025
**Estimated Effort:** 6-12 hours (1 week sprint)
**Priority:** HIGH (after Ethereum MVP validation)
