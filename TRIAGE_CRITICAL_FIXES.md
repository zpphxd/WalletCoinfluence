# CRITICAL TRIAGE - Fixes to Make System Actually Work

**Goal**: Get from "demo" to "functional MVP" that can onboard first 10 paying customers

**Timeline**: 2-3 weeks of focused work

---

# 🚨 BLOCKING ISSUES - System Literally Broken

## Issue #1: Blockchain Data is Fake
**Current State**: All trades have `price_usd=0`, `value_usd=0`, `amount=0`

**Why It's Broken**:
```python
# src/clients/alchemy.py line 64-66
"price_usd": 0,  # HARDCODED
"value_usd": 0,  # HARDCODED
"dex": "unknown",  # HARDCODED
```

**Impact**:
- ❌ PnL calculations return $0
- ❌ Being-Early scores are meaningless
- ❌ Alerts show no dollar amounts
- ❌ Users can't verify if wallets are actually profitable

**Fix Required**:
**Option A (Quick - 2 days)**: Use DexScreener API for prices
```python
# After fetching transfers, enrich with prices
async def enrich_trade_prices(trades: List[Dict]) -> List[Dict]:
    for trade in trades:
        # Get current price from DexScreener
        token_data = await dexscreener.get_token(trade["token_address"])
        trade["price_usd"] = token_data["priceUsd"]
        trade["value_usd"] = trade["amount"] * trade["price_usd"]
    return trades
```

**Option B (Proper - 1-2 weeks)**: Parse actual DEX swaps
```python
# Use Defined.fi API to get real swap data
async def get_token_swaps(token_address: str) -> List[Dict]:
    response = await defined_api.get_swaps(
        token_address=token_address,
        limit=100
    )

    swaps = []
    for swap in response["data"]["swaps"]:
        swaps.append({
            "tx_hash": swap["transactionHash"],
            "wallet_address": swap["maker"],
            "token_address": token_address,
            "side": "buy" if swap["tokenIn"] == "WETH" else "sell",
            "amount": float(swap["amountOut"]),
            "price_usd": float(swap["priceUsd"]),
            "value_usd": float(swap["amountInUsd"]),
            "dex": swap["exchange"]["name"],
            "timestamp": swap["timestamp"]
        })
    return swaps
```

**Recommendation**: Start with Option A, upgrade to Option B later

**Files to Change**:
- `src/clients/alchemy.py` - Add price enrichment
- `src/clients/helius.py` - Add price enrichment
- `src/ingest/wallet_discovery.py` - Call enrichment before saving
- `src/monitoring/wallet_monitor.py` - Call enrichment before alerts

**Testing**:
```bash
# Verify trades have real prices
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
SELECT
    wallet_address,
    token_address,
    price_usd,
    usd_value
FROM trades
WHERE price_usd > 0
LIMIT 5;
"
```

**Priority**: 🔴 P0 - BLOCKS ALL FUNCTIONALITY
**Effort**: 2 days (quick fix) or 1-2 weeks (proper fix)

---

## Issue #2: Database Column Name Mismatch (Runtime Crashes)
**Current State**: Models use `wallet_address`, code uses `wallet`

**Where It's Broken**:
```python
# src/analytics/pnl.py line 42
.filter(and_(Trade.wallet == wallet_address, ...))  # ❌ AttributeError

# src/scheduler/jobs.py line 67
WalletStats30D.wallet == wallet.address  # ❌ AttributeError

# src/watchlist/rules.py line 57
WalletStats30D.wallet == wallet_address  # ❌ AttributeError
```

**Impact**:
- ❌ Stats rollup job crashes every hour
- ❌ Watchlist maintenance crashes
- ❌ PnL calculations fail silently

**Fix Required**: Global find/replace

**Files to Change**:
1. `src/analytics/pnl.py`:
   - Line 42: `Trade.wallet` → `Trade.wallet_address`
   - Line 90: `Trade.wallet` → `Trade.wallet_address`
   - Line 168: `Position.wallet` → `Position.wallet_address`
   - Line 194: `Position.wallet` → `Position.wallet_address`
   - Line 223: `Trade.wallet` → `Trade.wallet_address`

2. `src/scheduler/jobs.py`:
   - Line 67: `WalletStats30D.wallet` → `WalletStats30D.wallet_address`
   - Line 90: `Trade.wallet` → `Trade.wallet_address`
   - Line 99: `WalletStats30D.wallet` → `WalletStats30D.wallet_address`

3. `src/watchlist/rules.py`:
   - Line 57: `WalletStats30D.wallet` → `WalletStats30D.wallet_address`
   - Line 100: `WalletStats30D.wallet` → `WalletStats30D.wallet_address`
   - Line 204: `WalletStats30D.wallet` → `WalletStats30D.wallet_address`

**Testing**:
```bash
# Run stats rollup manually
docker exec wallet_scout_worker python3 -c "
import asyncio
from src.db.session import SessionLocal
from src.scheduler.jobs import stats_rollup_job

asyncio.run(stats_rollup_job())
print('✅ Stats rollup succeeded')
"
```

**Priority**: 🔴 P0 - CRASHES HOURLY JOBS
**Effort**: 30 minutes

---

## Issue #3: Duplicate Trade Insertion Errors
**Current State**: Same wallet buying same token creates duplicate key violations

**Why It's Broken**:
```python
# src/ingest/wallet_discovery.py line 136-148
trade = Trade(tx_hash=tx.get("tx_hash"), ...)
self.db.add(trade)  # ❌ Crashes if trade already exists
```

**Impact**:
- ❌ Wallet discovery job fails after first run
- ❌ Can't re-discover same wallets
- ❌ Missing trades from subsequent ingestions

**Fix Required**: Add upsert logic (same as tokens)

**File to Change**: `src/ingest/wallet_discovery.py`

```python
# Line 135-155, replace with:
try:
    # Check if trade exists
    existing_trade = self.db.query(Trade).filter_by(
        tx_hash=tx.get("tx_hash")
    ).first()

    if not existing_trade:
        trade = Trade(
            tx_hash=tx.get("tx_hash"),
            ts=tx.get("timestamp", datetime.utcnow()),
            chain_id=chain_id,
            wallet_address=wallet_address,
            token_address=token_address,
            side="buy",
            qty_token=float(tx.get("amount", 0)),
            price_usd=float(tx.get("price_usd", 0)),
            usd_value=float(tx.get("value_usd", 0)),
            venue=tx.get("dex"),
        )
        self.db.add(trade)
        self.db.flush()  # Catch errors early

except Exception as e:
    logger.warning(f"Error processing transaction: {str(e)}")
    self.db.rollback()
    continue
```

**Same fix needed in**: `src/monitoring/wallet_monitor.py` (if it creates trades)

**Testing**:
```bash
# Run discovery twice, should not crash
docker exec wallet_scout_worker python3 -c "
import asyncio
from src.db.session import SessionLocal
from src.ingest.wallet_discovery import WalletDiscovery

async def test():
    db = SessionLocal()
    discovery = WalletDiscovery(db)

    # First run
    count1 = await discovery.discover_from_seed_tokens(hours_back=24)
    print(f'First run: {count1} wallets')

    # Second run (should not crash)
    count2 = await discovery.discover_from_seed_tokens(hours_back=24)
    print(f'Second run: {count2} wallets')
    print('✅ No duplicate key errors')

asyncio.run(test())
"
```

**Priority**: 🔴 P0 - PREVENTS RE-RUNNING JOBS
**Effort**: 1 hour

---

## Issue #4: No Way to Identify Actual DEX Swaps
**Current State**: Treating ALL ERC20 transfers as "buys"

**Why It's Broken**:
```python
# src/clients/alchemy.py line 61
"type": "buy",  # ❌ ASSUMES all transfers are buys
```

**Impact**:
- ❌ Counting internal transfers as trades
- ❌ Counting sends to exchanges as buys
- ❌ Counting token migrations as trades
- ❌ PnL includes garbage data

**Real Example**:
```
Transfer: 0x123 → 0x456 (1000 PEPE)
Current code: "Wallet 0x123 BOUGHT 1000 PEPE" ❌
Reality: Just moving tokens between wallets
```

**Fix Required**: Filter for DEX router addresses

**File to Change**: `src/clients/alchemy.py`

```python
# Known DEX routers (Ethereum)
DEX_ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d",  # Uniswap V2
    "0xe592427a0aece92de3edee1f18e0157c05861564",  # Uniswap V3
    "0x1111111254fb6c44bac0bed2854e76f90643097d",  # 1inch
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff",  # 0x
    # Add more...
}

async def get_token_transfers(self, token_address: str, chain_id: str, limit: int = 100):
    # ... existing code ...

    for transfer in response.get("result", {}).get("transfers", []):
        # Only count if interacting with DEX router
        to_address = transfer.get("to", "").lower()
        from_address = transfer.get("from", "").lower()

        # Skip if not DEX-related
        if to_address not in DEX_ROUTERS and from_address not in DEX_ROUTERS:
            continue

        # Determine buy vs sell
        side = "buy" if from_address in DEX_ROUTERS else "sell"

        transfers.append({
            "tx_hash": transfer.get("hash"),
            "from_address": transfer.get("from"),
            "type": side,  # ✅ Actual buy/sell detection
            ...
        })
```

**Alternative (Better)**: Use Defined.fi API which already filters for swaps

**Priority**: 🔴 P0 - FALSE SIGNALS
**Effort**: 4 hours (router filtering) or 2 days (Defined.fi integration)

---

# ⚠️ CRITICAL USABILITY - System Works But Unusable

## Issue #5: No Multi-User Support
**Current State**: Single hardcoded Telegram chat ID

**Why It's Blocking**:
- ❌ Can't onboard any paying customers
- ❌ Can't test with beta users
- ❌ Can't charge money

**Fix Required**: User table + broadcast to multiple chat IDs

**Files to Create/Change**:

1. **New Model** - `src/db/models.py`:
```python
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    email = Column(String(255), unique=True, nullable=False)
    telegram_chat_id = Column(String(50), unique=True, nullable=True)
    tier = Column(String(20), default="free")  # free, pro, elite
    api_key = Column(String(100), unique=True, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Quota tracking
    alerts_sent_today = Column(Integer, default=0)
    last_alert_reset = Column(DateTime, default=datetime.utcnow)
```

2. **Migration**:
```bash
alembic revision --autogenerate -m "add_users_table"
alembic upgrade head
```

3. **Update Alert System** - `src/alerts/telegram.py`:
```python
class TelegramAlerter:
    async def send_to_all_users(self, message: str, tier_filter: str = None):
        """Send alert to all active users (or specific tier)."""
        db = SessionLocal()

        query = db.query(User).filter(User.is_active == True)
        if tier_filter:
            query = query.filter(User.tier == tier_filter)

        users = query.all()

        for user in users:
            # Check quota
            if not self._check_quota(user):
                continue

            # Send message
            await self.send_message(message, chat_id=user.telegram_chat_id)

            # Increment quota
            user.alerts_sent_today += 1

        db.commit()
        db.close()

    def _check_quota(self, user: User) -> bool:
        # Reset daily counter
        if user.last_alert_reset.date() < datetime.utcnow().date():
            user.alerts_sent_today = 0
            user.last_alert_reset = datetime.utcnow()

        # Check tier limits
        limits = {"free": 5, "pro": 999999, "elite": 999999}
        return user.alerts_sent_today < limits[user.tier]
```

4. **Update Monitoring** - `src/monitoring/wallet_monitor.py`:
```python
# Line 239, replace:
await self.telegram.send_message(message)

# With:
await self.telegram.send_to_all_users(message, tier_filter="pro")  # Pro+ only
```

5. **Manual User Management** (for MVP):
```python
# Add user via Docker exec
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
INSERT INTO users (email, telegram_chat_id, tier, is_active)
VALUES ('customer@example.com', '1234567890', 'pro', true);
"
```

**Testing**:
```bash
# Add 2 test users
docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
INSERT INTO users (email, telegram_chat_id, tier) VALUES
('test1@test.com', '8416972017', 'free'),
('test2@test.com', '1111111111', 'pro');
"

# Send test alert
docker exec wallet_scout_worker python3 -c "
import asyncio
from src.alerts.telegram import TelegramAlerter

async def test():
    telegram = TelegramAlerter()
    await telegram.send_to_all_users('🧪 Test alert for all users')

asyncio.run(test())
"
```

**Priority**: 🔴 P0 - CAN'T MONETIZE
**Effort**: 1 day

---

## Issue #6: No Payment Collection
**Current State**: No way to take money

**Fix Required**: Manual Stripe links (automated later)

**Quick MVP Solution**:

1. **Create Stripe Products** (in Stripe dashboard):
   - Pro Monthly: $49/mo
   - Elite Monthly: $149/mo

2. **Generate Payment Links**:
   - Go to Stripe → Payment Links → Create
   - Link to product
   - Copy link: `https://buy.stripe.com/test_xxxxx`

3. **Manual Process**:
   ```
   User emails: "I want Pro tier"

   You reply: "Great! Subscribe here: https://buy.stripe.com/pro-monthly
   After payment, send me your Telegram username and I'll activate your account."

   User pays

   You run:
   docker exec wallet_scout_db psql -U wallet_scout -d wallet_scout -c "
   UPDATE users
   SET tier = 'pro'
   WHERE email = 'customer@example.com';
   "
   ```

4. **Set up Webhook** (for automation later):
   - Stripe → Webhooks → Add endpoint
   - URL: `https://yourdomain.com/api/webhooks/stripe`
   - Events: `checkout.session.completed`, `customer.subscription.deleted`

5. **Create Webhook Handler** - `src/api/routes.py`:
```python
import stripe

@app.post("/api/webhooks/stripe")
async def stripe_webhook(request: Request):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except ValueError:
        raise HTTPException(status_code=400)

    if event.type == "checkout.session.completed":
        session = event.data.object

        # Upgrade user
        db = SessionLocal()
        user = db.query(User).filter_by(email=session.customer_email).first()
        if user:
            user.tier = session.metadata.get("tier", "pro")
            db.commit()
        db.close()

    return {"status": "success"}
```

**Priority**: 🟠 P1 - NEEDED FOR REVENUE (but can be manual at first)
**Effort**: 2 hours (manual) or 1 day (automated webhooks)

---

## Issue #7: No Way to See What System is Doing
**Current State**: Logs only in Docker stdout, no visibility

**Fix Required**: Simple status dashboard

**Quick Fix**: Add API endpoint

**File to Change**: `src/api/routes.py`

```python
@app.get("/api/status")
async def get_status():
    """System status and recent activity."""
    db = SessionLocal()

    # Get counts
    token_count = db.query(Token).count()
    wallet_count = db.query(Wallet).count()
    trade_count = db.query(Trade).count()
    alert_count = db.query(Alert).count()
    user_count = db.query(User).count()

    # Get recent activity
    recent_tokens = db.query(SeedToken).order_by(
        SeedToken.snapshot_ts.desc()
    ).limit(10).all()

    recent_wallets = db.query(Wallet).order_by(
        Wallet.first_seen_at.desc()
    ).limit(10).all()

    recent_alerts = db.query(Alert).order_by(
        Alert.ts.desc()
    ).limit(10).all()

    # Top wallets by PnL
    top_wallets = db.query(WalletStats30D).order_by(
        WalletStats30D.realized_pnl_usd.desc()
    ).limit(10).all()

    db.close()

    return {
        "counts": {
            "tokens": token_count,
            "wallets": wallet_count,
            "trades": trade_count,
            "alerts": alert_count,
            "users": user_count,
        },
        "recent_tokens": [{"symbol": t.token.symbol, "source": t.source} for t in recent_tokens],
        "recent_wallets": [{"address": w.address[:10] + "...", "chain": w.chain_id} for w in recent_wallets],
        "recent_alerts": [{"type": a.type, "token": a.token_address[:10] + "..."} for a in recent_alerts],
        "top_wallets": [{"address": w.wallet_address[:10] + "...", "pnl": w.realized_pnl_usd} for w in top_wallets],
    }
```

**Access**: `http://localhost:8000/api/status`

**Later**: Build simple HTML page to display this

**Priority**: 🟡 P2 - NICE TO HAVE (but helps debugging)
**Effort**: 2 hours

---

# 📋 WORKING FIX LIST (Prioritized)

## WEEK 1: Make System Functional

### Day 1 (4 hours)
- [ ] **Fix #2**: Column name mismatches (30 min)
- [ ] **Fix #3**: Duplicate trade upsert (1 hour)
- [ ] **Fix #4**: Filter for DEX routers only (2 hours)
- [ ] **Test**: Run discovery + stats rollup, verify no crashes

### Day 2-3 (2 days)
- [ ] **Fix #1 (Quick)**: DexScreener price enrichment
  - [ ] Add price lookup function
  - [ ] Update wallet_discovery.py to enrich trades
  - [ ] Update wallet_monitor.py to enrich trades
  - [ ] Test: Verify trades have real prices

### Day 4 (1 day)
- [ ] **Fix #5**: Multi-user support
  - [ ] Add User table (migration)
  - [ ] Update TelegramAlerter for broadcast
  - [ ] Manually add 3 test users
  - [ ] Test: Send alert to all users

### Day 5 (4 hours)
- [ ] **Fix #7**: Status dashboard endpoint
- [ ] **Fix #6 (Manual)**: Create Stripe payment links
- [ ] **Document**: Manual user onboarding process

## WEEK 2: Test + Polish

### Day 6-7 (2 days)
- [ ] End-to-end testing with real data
  - [ ] Verify token ingestion (prices populated)
  - [ ] Verify wallet discovery (no duplicates)
  - [ ] Verify stats rollup (no crashes)
  - [ ] Verify alerts (sent to all users)
  - [ ] Manually test payment flow

### Day 8-10 (3 days)
- [ ] Fix bugs found in testing
- [ ] Add database indexes (if queries slow)
- [ ] Set up Sentry error tracking
- [ ] Add health check endpoint
- [ ] Deploy to production server

## WEEK 3: Beta Launch

### Day 11-15 (5 days)
- [ ] Onboard 10 beta users (5 free, 5 paid)
- [ ] Monitor for errors/issues
- [ ] Iterate based on feedback
- [ ] Fix critical bugs
- [ ] Document lessons learned

---

# SUCCESS CRITERIA

After these fixes, system should:

✅ **Ingest tokens** with real prices (not $0)
✅ **Discover wallets** without duplicate errors
✅ **Calculate PnL** with accurate numbers
✅ **Send alerts** to multiple users
✅ **Enforce quotas** (5 alerts/day for free tier)
✅ **Collect payments** (manual Stripe links)
✅ **Run 24/7** without crashing

---

# WHAT TO SKIP (For Now)

❌ Full web dashboard (use API endpoint + Postman)
❌ Automated Stripe webhooks (manual onboarding OK for first 10 users)
❌ LLM integration (preliminary scores sufficient)
❌ Custom watchlists (everyone gets same alerts)
❌ Mobile app (Telegram is mobile)
❌ Advanced analytics (focus on core alerts)

---

# NEXT STEPS AFTER TRIAGE

Once these 7 fixes are done (2-3 weeks):

1. **Soft launch** with 10 paid beta users
2. **Collect feedback** (are alerts valuable? accurate?)
3. **Measure retention** (do users stay subscribed?)
4. **Then decide**:
   - If retention good → Scale marketing
   - If retention bad → Fix product issues first

---

**Estimated Timeline**: 2-3 weeks to functional MVP
**First Dollar**: Week 2 (manual Stripe payments)
**First 10 Customers**: Week 3-4

Ready to start?
