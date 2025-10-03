# Alpha Wallet Scout - SaaS Improvement Roadmap
**Comprehensive Technical Review & Production-Ready Checklist**

Generated: October 3, 2025

---

## Executive Summary

**Current Status**: MVP functional with core workflow operational (token ingestion → wallet discovery → monitoring → alerts)

**Assessment**: The system demonstrates proof-of-concept viability but requires **critical production hardening** before launching as a paid SaaS product.

**Priority Rating System**:
- 🔴 **P0 (Blocker)**: Must fix before ANY paying customers
- 🟠 **P1 (Critical)**: Must fix before scaling beyond 100 users
- 🟡 **P2 (Important)**: Must fix before $1M ARR
- 🟢 **P3 (Nice-to-have)**: Post-PMF optimization

---

# 🔴 P0 BLOCKERS - Fix Before Launch

## 1. Data Quality & Reliability

### Issue: Blockchain Data is Incomplete/Inaccurate
**Current State**:
- Alchemy API returns transfers but NOT actual DEX swaps
- No price data, no DEX venue, no actual buy/sell detection
- Helius API returns raw transactions, not parsed swap data
- All transaction amounts/prices are hardcoded to 0

**Impact**: 🔴 **CRITICAL - System cannot identify real trades**
- Wallet PnL calculations will be 100% wrong
- Being-Early scores will be meaningless
- Alerts will fire on irrelevant transfers (not actual buys)

**Fix Required**:
```python
# Current (WRONG):
{
    "amount": float(transfer.get("value", 0)),  # Just token transfer amount
    "price_usd": 0,  # HARDCODED
    "value_usd": 0,  # HARDCODED
    "type": "buy",  # Assumes ALL transfers are buys (WRONG)
}

# Need (CORRECT):
{
    "amount": parse_swap_output_amount(tx),  # Actual tokens received
    "price_usd": calculate_price_from_reserves(pool_state),  # Real price
    "value_usd": input_amount_usd,  # USD value of swap
    "type": detect_swap_direction(tx),  # Actual buy/sell
    "dex": identify_dex_from_router(tx),  # Uniswap/Raydium/etc
}
```

**Solution Options**:

**Option A: Use Proper DEX APIs (RECOMMENDED)**
- **Alchemy Enhanced API**: `alchemy_getTokenTransactions` with `transfers` category
- **Helius DAS API**: `getAssetsByOwner` + `getSignaturesForAddress` with swap parsing
- **DEX Aggregators**:
  - DexScreener API (has transaction endpoints)
  - Defined.fi API (free tier, swap data)
  - Jupiter API (Solana swaps)

**Option B: Parse Logs/Receipts Directly**
- Decode ERC20 Transfer events + Uniswap Swap events
- Match Transfer IN (buy) vs Transfer OUT (sell)
- Calculate price from reserves (requires pool state lookups)
- **Complexity**: High, error-prone, rate-limit intensive

**Recommendation**:
Use **Defined.fi** (free 100k calls/month) for EVM swaps + **Jupiter API** for Solana
- Defined.fi endpoint: `GET /tokens/{address}/swaps` returns parsed swaps with prices
- Jupiter API: Transaction parsing service

**Estimated Effort**: 2-3 days
**Priority**: 🔴 P0 - Blocks all functionality

---

### Issue: No Token Price/Market Data Integration
**Current State**:
- Token table has `last_price_usd` column but never populated
- Position unrealized PnL calculation uses last trade price (stale)
- No market cap, liquidity, or holder data for filtering

**Impact**: 🔴 **CRITICAL - Cannot calculate PnL or filter scams**

**Fix Required**:
1. **Real-time Price Feed**:
   - DexScreener WebSocket for live prices
   - OR CoinGecko/Birdeye REST API polling (5-min intervals)

2. **Market Data Enrichment**:
   ```python
   # Add to token ingestion
   token_data = await dexscreener.get_token_info(address, chain)
   token.last_price_usd = token_data["priceUsd"]
   token.liquidity_usd = token_data["liquidity"]["usd"]
   token.market_cap_usd = token_data["fdv"]  # NEW COLUMN
   token.volume_24h_usd = token_data["volume"]["h24"]  # NEW COLUMN
   ```

3. **Scam Filtering**:
   - Integrate TokenSniffer API (honeypot detection)
   - Check `is_honeypot`, `buy_tax_pct`, `sell_tax_pct` before adding to seed tokens

**Estimated Effort**: 2 days
**Priority**: 🔴 P0

---

## 2. Database Schema & Data Integrity Issues

### Issue: Column Name Mismatches Still Exist
**Current State**:
- [models.py:42](src/db/models.py#L42): `Trade.wallet` should be `Trade.wallet_address` (ALREADY FIXED IN MODELS)
- [pnl.py:42](src/analytics/pnl.py#L42): Still references `Trade.wallet` (NOT FIXED)
- [jobs.py:67](src/scheduler/jobs.py#L67): Still references `WalletStats30D.wallet` (NOT FIXED)
- [watchlist/rules.py:57](src/watchlist/rules.py#L57): Still references `WalletStats30D.wallet` (NOT FIXED)

**Impact**: 🔴 **CRITICAL - Runtime errors, stats rollup will fail**

**Fix Required**: Global find/replace in ALL files:
```bash
# Fix all references
grep -r "Trade\.wallet[^_]" src/ | grep -v "wallet_address"
grep -r "WalletStats30D\.wallet[^_]" src/ | grep -v "wallet_address"
grep -r "Position\.wallet[^_]" src/ | grep -v "wallet_address"
```

**Files to update**:
- src/analytics/pnl.py (lines 42, 90, 168, 194, 223)
- src/scheduler/jobs.py (lines 67, 90, 99, 204)
- src/watchlist/rules.py (lines 57, 100, 204)

**Estimated Effort**: 1 hour
**Priority**: 🔴 P0 - Blocks stats calculation

---

### Issue: Missing Database Constraints & Indexes
**Current State**:
- No unique constraint on `(wallet_address, token_address, tx_hash)` in trades
- No index on `trades.ts` (timestamp) - queries will be slow
- No foreign key cascades - orphaned data risk
- Position table has no relationship to Token table

**Impact**: 🟠 **CRITICAL at scale - Duplicate data, slow queries**

**Fix Required**:
```python
# Add to models.py
class Trade(Base):
    __table_args__ = (
        CheckConstraint("side IN ('buy', 'sell')", name="check_trade_side"),
        Index("idx_trades_wallet_ts", "wallet_address", "ts"),
        Index("idx_trades_token_ts", "token_address", "ts"),
        Index("idx_trades_chain_ts", "chain_id", "ts"),
        UniqueConstraint("wallet_address", "token_address", "tx_hash", name="uq_trade"),  # NEW
    )

class Position(Base):
    token = relationship("Token")  # NEW - add relationship
```

Create Alembic migration:
```bash
alembic revision --autogenerate -m "add_missing_constraints"
alembic upgrade head
```

**Estimated Effort**: 2 hours
**Priority**: 🔴 P0 - Prevents duplicate trades

---

## 3. Missing Core Features for MVP

### Issue: No User Management System
**Current State**:
- Single Telegram chat ID hardcoded in .env
- No way to add multiple users
- No free vs paid tier enforcement
- No API authentication beyond single token

**Impact**: 🔴 **BLOCKER - Cannot onboard paying customers**

**Fix Required**:
1. **User Table**:
   ```python
   class User(Base):
       __tablename__ = "users"
       id = Column(Integer, primary_key=True)
       telegram_chat_id = Column(String(50), unique=True)
       email = Column(String(255), unique=True)
       tier = Column(String(20))  # free, pro, elite, institutional
       api_key = Column(String(100), unique=True)
       created_at = Column(DateTime, default=datetime.utcnow)
       subscription_ends_at = Column(DateTime, nullable=True)
       is_active = Column(Boolean, default=True)

       # Quota tracking
       alerts_sent_today = Column(Integer, default=0)
       last_alert_reset = Column(DateTime, default=datetime.utcnow)
   ```

2. **Tier Limits**:
   ```python
   TIER_LIMITS = {
       "free": {"alerts_per_day": 5, "chains": ["ethereum"]},
       "pro": {"alerts_per_day": 999999, "chains": ["ethereum", "base", "arbitrum", "solana"]},
       "elite": {"alerts_per_day": 999999, "chains": ["all"], "custom_watchlists": True},
   }
   ```

3. **Alert Quota Check**:
   ```python
   async def send_alert(user_id: int, message: str):
       user = db.query(User).get(user_id)

       # Reset daily counter
       if user.last_alert_reset.date() < datetime.utcnow().date():
           user.alerts_sent_today = 0
           user.last_alert_reset = datetime.utcnow()

       # Check quota
       tier_limit = TIER_LIMITS[user.tier]["alerts_per_day"]
       if user.alerts_sent_today >= tier_limit:
           return False  # Quota exceeded

       # Send alert
       await telegram.send_message(user.telegram_chat_id, message)
       user.alerts_sent_today += 1
       db.commit()
   ```

**Estimated Effort**: 3-4 days
**Priority**: 🔴 P0 - Cannot monetize without this

---

### Issue: No Payment/Subscription Integration
**Current State**: No way to collect money

**Fix Required**:
1. **Stripe Integration**:
   ```python
   import stripe
   stripe.api_key = settings.stripe_secret_key

   @app.post("/api/checkout/create-session")
   async def create_checkout(tier: str, email: str):
       session = stripe.checkout.Session.create(
           payment_method_types=["card"],
           line_items=[{
               "price": STRIPE_PRICE_IDS[tier],  # Pre-created in Stripe dashboard
               "quantity": 1,
           }],
           mode="subscription",
           success_url=f"{settings.base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
           cancel_url=f"{settings.base_url}/cancel",
       )
       return {"checkout_url": session.url}

   @app.post("/api/webhooks/stripe")
   async def stripe_webhook(request: Request):
       event = stripe.Webhook.construct_event(
           await request.body(), request.headers["stripe-signature"], settings.stripe_webhook_secret
       )

       if event.type == "checkout.session.completed":
           session = event.data.object
           # Upgrade user tier
           user = db.query(User).filter_by(email=session.customer_email).first()
           user.tier = session.metadata["tier"]
           user.subscription_ends_at = datetime.utcnow() + timedelta(days=30)
           db.commit()
   ```

2. **Frontend Pricing Page**:
   - Simple React/Next.js page with pricing tiers
   - "Subscribe" button → Stripe Checkout
   - Webhook updates user tier in DB

**Estimated Effort**: 3 days (Stripe setup + webhook handling)
**Priority**: 🔴 P0 - Cannot launch SaaS without payments

---

### Issue: No Web Dashboard/UI
**Current State**: Telegram-only, no way to view wallet stats, trade history, or analytics

**Impact**: 🟠 **CRITICAL for retention - Users want to verify data**

**Fix Required**:
1. **Minimal Dashboard** (React + Tailwind):
   - `/login` - Telegram OAuth or email/password
   - `/dashboard` - Top performing wallets this week
   - `/wallets/{address}` - Wallet detail page (30D PnL, trades, positions)
   - `/alerts` - Alert history with filters
   - `/settings` - Notification preferences, API key

2. **API Endpoints**:
   ```python
   @app.get("/api/wallets/top")
   async def get_top_wallets(limit: int = 50):
       return db.query(WalletStats30D).order_by(
           WalletStats30D.realized_pnl_usd.desc()
       ).limit(limit).all()

   @app.get("/api/wallets/{address}")
   async def get_wallet_detail(address: str):
       wallet = db.query(Wallet).filter_by(address=address).first()
       stats = db.query(WalletStats30D).filter_by(wallet_address=address).first()
       trades = db.query(Trade).filter_by(wallet_address=address).order_by(Trade.ts.desc()).limit(100).all()
       return {"wallet": wallet, "stats": stats, "trades": trades}
   ```

**Estimated Effort**: 1-2 weeks (full dashboard)
**Priority**: 🟠 P1 - Can launch without, but needed for retention

---

## 4. Monitoring & Observability Gaps

### Issue: No Error Tracking or Alerting
**Current State**:
- Errors logged to stdout, lost when container restarts
- No way to know if jobs are failing
- No monitoring of API rate limits

**Impact**: 🟠 **CRITICAL - Silent failures, data loss**

**Fix Required**:
1. **Sentry Integration**:
   ```python
   import sentry_sdk
   from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

   sentry_sdk.init(
       dsn=settings.sentry_dsn,
       integrations=[SqlalchemyIntegration()],
       traces_sample_rate=0.1,
   )
   ```

2. **Health Check Endpoint**:
   ```python
   @app.get("/health")
   async def health_check():
       # Check DB connection
       db_ok = db.execute("SELECT 1").scalar() == 1

       # Check Redis
       redis_ok = redis_client.ping()

       # Check last job run
       last_ingestion = redis_client.get("last_job:runner_seed")
       job_ok = last_ingestion and (time.time() - float(last_ingestion) < 1800)

       if not all([db_ok, redis_ok, job_ok]):
           raise HTTPException(status_code=503, detail="System unhealthy")

       return {"status": "ok", "db": db_ok, "redis": redis_ok, "jobs": job_ok}
   ```

3. **UptimeRobot Monitoring**:
   - Monitor `/health` endpoint every 5 min
   - Alert via email/Telegram if down

**Estimated Effort**: 1 day
**Priority**: 🟠 P1 - Needed for production reliability

---

### Issue: No Metrics/Analytics on System Performance
**Current State**: No visibility into:
- How many tokens ingested per source
- How many wallets discovered per job run
- Alert delivery success rate
- API error rates

**Fix Required**:
1. **Prometheus Metrics**:
   ```python
   from prometheus_client import Counter, Histogram, Gauge

   tokens_ingested = Counter("tokens_ingested_total", "Total tokens ingested", ["source"])
   wallets_discovered = Counter("wallets_discovered_total", "Wallets discovered")
   alerts_sent = Counter("alerts_sent_total", "Alerts sent", ["type"])
   job_duration = Histogram("job_duration_seconds", "Job duration", ["job_name"])
   api_errors = Counter("api_errors_total", "API errors", ["api_name", "error_type"])

   # In code:
   tokens_ingested.labels(source="geckoterminal").inc(count)
   ```

2. **Grafana Dashboard**:
   - Tokens ingested/hour (by source)
   - Wallets discovered/day
   - Alerts sent/day (single vs confluence)
   - API error rate by source

**Estimated Effort**: 2 days
**Priority**: 🟡 P2 - Nice to have for debugging

---

# 🟠 P1 CRITICAL - Fix Before Scaling

## 5. Performance & Scalability Issues

### Issue: Database Queries Not Optimized
**Current State**:
- Wallet monitoring loops through ALL watchlist wallets sequentially
- Stats rollup calculates PnL for EVERY wallet from scratch hourly
- No query result caching

**Impact**: 🟠 **CRITICAL at 10k+ wallets - Jobs will timeout**

**Fix Required**:
1. **Batch Processing**:
   ```python
   # Current (SLOW):
   for wallet in watchlist:
       new_trades = await check_wallet(wallet)

   # Optimized (FAST):
   wallet_batches = chunk(watchlist, size=100)
   for batch in wallet_batches:
       tasks = [check_wallet(w) for w in batch]
       results = await asyncio.gather(*tasks)
   ```

2. **Incremental Stats Updates**:
   ```python
   # Instead of recalculating full 30D PnL:
   # Store daily snapshots, sum last 30 days
   class DailyWalletSnapshot(Base):
       date = Column(Date, primary_key=True)
       wallet_address = Column(String(100), primary_key=True)
       realized_pnl_usd = Column(Float)

   # Hourly job: Only update today's snapshot
   # When reading stats: SUM(last 30 days of snapshots)
   ```

3. **Redis Caching**:
   ```python
   @cache_result(ttl=300)  # 5 min cache
   async def get_wallet_stats(address: str):
       return db.query(WalletStats30D).filter_by(wallet_address=address).first()
   ```

**Estimated Effort**: 3 days
**Priority**: 🟠 P1 - Needed at 1,000+ wallets

---

### Issue: No Rate Limiting on External APIs
**Current State**:
- Alchemy free tier: 300M compute units/month (~100k calls)
- No backoff/retry logic
- Could hit rate limits and break discovery

**Fix Required**:
```python
from tenacity import retry, stop_after_attempt, wait_exponential

class AlchemyClient(BaseAPIClient):
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def get_token_transfers(self, ...):
        try:
            response = await self.post(...)
        except RateLimitError:
            logger.warning("Alchemy rate limit hit, backing off...")
            raise  # Tenacity will retry
```

**Estimated Effort**: 4 hours
**Priority**: 🟠 P1 - Prevents outages

---

## 6. Security & Compliance

### Issue: API Keys Exposed in .env File (Checked into Git?)
**Current State**: .env file with sensitive keys

**Impact**: 🔴 **CRITICAL - Security breach risk**

**Fix Required**:
1. **Secrets Management**:
   - Use AWS Secrets Manager or HashiCorp Vault
   - OR environment variables in hosting platform (Railway/Render)

2. **Rotate All Keys**:
   - Generate new Telegram bot token
   - Generate new Alchemy/Helius keys

3. **Add .env to .gitignore**:
   ```bash
   echo ".env" >> .gitignore
   git rm --cached .env
   git commit -m "Remove .env from git"
   ```

**Estimated Effort**: 1 hour
**Priority**: 🔴 P0 - Do this NOW

---

### Issue: No SQL Injection Protection in Raw Queries
**Current State**: Using SQLAlchemy ORM (safe), but some string formatting

**Fix Required**: Audit all queries, ensure parameterized:
```python
# BAD:
db.execute(f"SELECT * FROM trades WHERE wallet = '{address}'")

# GOOD:
db.query(Trade).filter(Trade.wallet_address == address).all()
```

**Estimated Effort**: 2 hours audit
**Priority**: 🟠 P1

---

### Issue: No Terms of Service / Privacy Policy
**Current State**: No legal docs

**Impact**: 🟠 **CRITICAL for compliance - GDPR, CCPA**

**Fix Required**:
1. Create TOS (use TermsFeed generator)
2. Create Privacy Policy (what data we collect, how we use it)
3. Add checkbox to signup form
4. Add `/api/users/{id}/delete` endpoint for GDPR deletion requests

**Estimated Effort**: 1 day (with legal template tool)
**Priority**: 🟠 P1 - Needed before launch in EU/CA

---

# 🟡 P2 IMPORTANT - Fix Before $1M ARR

## 7. Data Quality Improvements

### Issue: Bot Detection is Stub Implementation
**Current State**: `is_bot_flag` column exists but never set

**Fix Required**:
1. **Heuristic Bot Detection**:
   ```python
   def is_likely_bot(wallet_address: str, trades: List[Trade]) -> bool:
       # MEV bots: 100+ trades/day
       trades_per_day = len(trades) / 30
       if trades_per_day > 100:
           return True

       # Arbitrage bots: <1 min between buy and sell
       for i in range(len(trades) - 1):
           if trades[i].side == "buy" and trades[i+1].side == "sell":
               time_diff = (trades[i+1].ts - trades[i].ts).total_seconds()
               if time_diff < 60:
                   return True

       # Snipers: Buys within 1 block of token creation
       # (Requires on-chain data)

       return False
   ```

2. **Label Known Bots**:
   - Maintain list of known MEV/arb bot addresses
   - Cross-reference with Etherscan labels API

**Estimated Effort**: 2 days
**Priority**: 🟡 P2 - Improves signal quality

---

### Issue: No Token Metadata Enrichment
**Current State**: Only `symbol` stored, no name, logo, socials

**Fix Required**:
```python
class Token(Base):
    name = Column(String(255))  # "Pepe the Frog"
    logo_url = Column(String(500))  # For UI
    website = Column(String(500))
    twitter = Column(String(100))
    telegram = Column(String(100))
    description = Column(Text)

# Fetch from CoinGecko or DexScreener on token creation
```

**Estimated Effort**: 1 day
**Priority**: 🟢 P3 - Nice for UX

---

## 8. Feature Completeness

### Issue: No LLM Integration (Mentioned in Deck but Not Implemented)
**Current State**: Ollama container exists but unused

**Fix Required**:
1. **Pull Phi-3 Model**:
   ```bash
   docker exec wallet_scout_ollama ollama pull phi3
   ```

2. **Implement LLM Analyzer**:
   ```python
   # src/analytics/llm_analyzer.py already exists (stub)
   class LLMAnalyzer:
       async def analyze_signal(self, trade_data: dict, wallet_stats: dict, token_data: dict):
           prompt = f"""
           Analyze this crypto trade signal:

           Wallet 30D Stats:
           - PnL: ${wallet_stats['pnl']:,.0f}
           - Best Trade: {wallet_stats['best_multiple']:.1f}x
           - Early Score: {wallet_stats['early_score']}

           Token:
           - Symbol: {token_data['symbol']}
           - Market Cap: ${token_data['mcap']:,.0f}
           - Liquidity: ${token_data['liquidity']:,.0f}
           - Holder Concentration: {token_data['top10_share']}%

           Trade:
           - Amount: ${trade_data['value_usd']:,.2f}
           - Price: ${trade_data['price_usd']:.8f}

           Assess:
           1. Signal confidence (0-100)
           2. Recommendation (BUY/HOLD/AVOID)
           3. Key risk factors
           4. One-sentence reasoning
           """

           response = await ollama.generate(model="phi3", prompt=prompt)
           return self._parse_llm_response(response)
   ```

3. **Activate LLM for High Scores**:
   ```python
   # In wallet_monitor.py
   if prelim_score > 75 or is_confluence:
       llm_result = await llm.analyze_signal(trade, stats, token)
       message += f"\n🤖 AI: {llm_result['recommendation']} ({llm_result['confidence']}/100)\nReason: {llm_result['reason']}"
   ```

**Estimated Effort**: 2 days
**Priority**: 🟡 P2 - Differentiator but not MVP blocker

---

### Issue: No Custom Watchlists (Elite Tier Feature)
**Current State**: Single global watchlist

**Fix Required**:
```python
class UserWatchlist(Base):
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(100))  # "DeFi Whales", "Memecoin Snipers"
    wallet_addresses = Column(JSON)  # ["0x123...", "0x456..."]

# API endpoints
@app.post("/api/watchlists")
async def create_watchlist(user_id: int, name: str, wallets: List[str]):
    ...

# Monitor custom lists
async def monitor_user_watchlist(user_id: int, watchlist_id: int):
    ...
```

**Estimated Effort**: 3 days
**Priority**: 🟡 P2 - Elite tier feature, can launch without

---

## 9. Infrastructure & DevOps

### Issue: No CI/CD Pipeline
**Current State**: Manual Docker builds and deploys

**Fix Required**:
1. **GitHub Actions**:
   ```yaml
   # .github/workflows/deploy.yml
   name: Deploy to Production
   on:
     push:
       branches: [main]
   jobs:
     test:
       runs-on: ubuntu-latest
       steps:
         - uses: actions/checkout@v3
         - run: pytest tests/

     deploy:
       needs: test
       runs-on: ubuntu-latest
       steps:
         - run: docker build -t wallet-scout:latest .
         - run: docker push registry/wallet-scout:latest
         - run: ssh user@prod "docker-compose pull && docker-compose up -d"
   ```

**Estimated Effort**: 1 day
**Priority**: 🟡 P2 - QoL improvement

---

### Issue: No Backup/Disaster Recovery
**Current State**: PostgreSQL data in Docker volume, no backups

**Fix Required**:
```bash
# Automated daily backups to S3
0 2 * * * docker exec wallet_scout_db pg_dump -U wallet_scout wallet_scout | gzip > /backups/$(date +\%Y\%m\%d).sql.gz
0 3 * * * aws s3 sync /backups/ s3://wallet-scout-backups/
```

**Estimated Effort**: 4 hours
**Priority**: 🟠 P1 - Critical for production

---

# 🟢 P3 NICE-TO-HAVE - Post-PMF

## 10. Advanced Features

- **Backtesting**: Let users test "what if I followed this wallet last month"
- **Portfolio Tracking**: Sync user's wallets, track their own PnL
- **Copy Trading Integration**: One-click follow (via API to DEX aggregators)
- **Mobile App**: React Native app with push notifications
- **Discord Bot**: Alternative to Telegram
- **Whale Labeling**: Automatic detection of known whales (Tetranode, etc.)
- **Multi-Language Support**: Alerts in Spanish, Chinese, etc.

---

# PRIORITIZED 30-DAY SPRINT PLAN

## Week 1: Fix Data Pipeline (P0 Blockers)
**Day 1-2**:
- [ ] Fix column name mismatches (Trade.wallet → wallet_address everywhere)
- [ ] Add database constraints (unique trade constraint, indexes)
- [ ] Migrate .env secrets to environment variables

**Day 3-5**:
- [ ] Integrate Defined.fi API for real DEX swap data (EVM)
- [ ] Integrate Jupiter API for Solana swap data
- [ ] Update wallet discovery to parse actual swaps (not transfers)
- [ ] Add token price enrichment (DexScreener API)

**Day 6-7**:
- [ ] Add TokenSniffer honeypot detection
- [ ] Test full pipeline: trending tokens → wallet discovery → PnL calc
- [ ] Verify PnL calculations are accurate

## Week 2: User Management & Payments (P0 Blockers)
**Day 8-10**:
- [ ] Create User table + API endpoints (signup, login)
- [ ] Implement tier-based quota enforcement
- [ ] Update alert system to support multiple users

**Day 11-14**:
- [ ] Stripe integration (checkout, webhooks)
- [ ] Simple pricing page (React + Tailwind)
- [ ] Test full payment flow: signup → pay → upgrade tier → receive alerts

## Week 3: Production Hardening (P1 Critical)
**Day 15-16**:
- [ ] Add Sentry error tracking
- [ ] Create health check endpoint
- [ ] Set up UptimeRobot monitoring

**Day 17-19**:
- [ ] Optimize database queries (batch processing, caching)
- [ ] Add API rate limiting + retry logic
- [ ] Set up daily PostgreSQL backups to S3

**Day 20-21**:
- [ ] Create Terms of Service + Privacy Policy
- [ ] Add GDPR user deletion endpoint
- [ ] Security audit (SQL injection, secrets exposure)

## Week 4: Dashboard & Launch Prep (P1 Critical)
**Day 22-25**:
- [ ] Build minimal dashboard (top wallets, wallet detail, alert history)
- [ ] Add user settings page (API key, notification prefs)
- [ ] Connect frontend to backend API

**Day 26-28**:
- [ ] End-to-end testing with 10 beta users
- [ ] Fix bugs found in testing
- [ ] Load testing (simulate 1000 users)

**Day 29-30**:
- [ ] Create onboarding docs (how to use, FAQ)
- [ ] Deploy to production (Railway/Render)
- [ ] Soft launch (Twitter announcement, first 100 users)

---

# ESTIMATED TOTAL EFFORT

**Must-Fix Before Launch (P0 + P1)**:
- Engineering Time: **4-6 weeks** (1 full-time developer)
- Infrastructure Costs: $200-500/month (hosting, APIs, monitoring)
- Legal/Compliance: $500-1000 (TOS/Privacy templates)

**Post-Launch Improvements (P2)**:
- LLM integration: 2 days
- Bot detection: 2 days
- Custom watchlists: 3 days
- **Total**: 1-2 weeks

**Long-Term (P3)**:
- Advanced features: 2-3 months

---

# RISK ASSESSMENT

## Technical Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Blockchain API rate limits hit | High | Critical | Multi-source fallbacks, caching, paid tiers |
| Inaccurate PnL calculations | Medium | Critical | Extensive testing, comparison with known wallets |
| Database performance degrades at scale | Medium | High | Optimize queries, add read replicas |
| Scam tokens bypass filters | High | Medium | Multi-layered filtering (honeypot + manual review) |

## Business Risks
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Users don't convert to paid | High | Critical | Strong free tier (5 alerts/day), viral growth |
| Competition from Nansen/Arkham | Medium | High | Price advantage ($49 vs $150), memecoin focus |
| Regulatory crackdown on crypto signals | Low | Critical | Disclaimer: "Educational only, not financial advice" |
| Churn due to false signals | Medium | High | Transparency (show wallet stats), AI validation |

---

# LAUNCH READINESS CHECKLIST

## Must Have (MVP)
- [ ] Real DEX swap data (not transfers)
- [ ] Accurate PnL calculations
- [ ] Multi-user support with tiers
- [ ] Stripe payment integration
- [ ] Basic web dashboard
- [ ] Error tracking (Sentry)
- [ ] Database backups
- [ ] Terms of Service

## Should Have (Within 30 Days)
- [ ] Health monitoring
- [ ] Performance optimizations
- [ ] Security audit
- [ ] Load testing
- [ ] Onboarding docs

## Nice to Have (Post-Launch)
- [ ] LLM integration
- [ ] Custom watchlists
- [ ] Mobile app
- [ ] Backtesting

---

# FINAL RECOMMENDATION

**Current Assessment**: System is ~40% production-ready

**Blocker Count**:
- 🔴 P0: **8 blockers** (data quality, user mgmt, payments, security)
- 🟠 P1: **6 critical** (performance, monitoring, dashboard)

**Recommendation**:
1. **DO NOT LAUNCH** with current codebase
2. Spend **4-6 weeks** fixing P0/P1 issues
3. Soft launch with **50-100 beta users** (free tier only)
4. Iterate based on feedback for 2-4 weeks
5. Launch paid tiers after validation

**Fastest Path to Revenue**:
1. Week 1-2: Fix data pipeline + Add multi-user support
2. Week 3: Add Stripe + Simple dashboard
3. Week 4: Beta testing with 50 users
4. Week 5-6: Fix bugs, launch paid tiers

**Expected Timeline to First Dollar**: 6-8 weeks from today

**Confidence Level**:
- **Technical Feasibility**: 90% (core workflow proven)
- **Time Estimate Accuracy**: 75% (could be 8-10 weeks with unknowns)
- **Product-Market Fit Risk**: 60% (need user validation)

---

## Next Steps

1. **Prioritize P0 fixes** - Start with data quality issues
2. **Set up project tracker** - Use Linear/GitHub Projects for this roadmap
3. **Hire if needed** - 6 weeks is aggressive for solo dev
4. **Beta program** - Recruit 50 testers from crypto Twitter NOW (build audience while building)

---

**Document Owner**: Claude (AI Assistant)
**Last Updated**: October 3, 2025
**Next Review**: After Week 1 Sprint
