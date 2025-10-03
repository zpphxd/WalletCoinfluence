---
title: "Alpha Wallet Scout"
subtitle: "AI-Powered Crypto Trading Intelligence"
author: "Wallet Signal"
date: "2025"
geometry: margin=1in
fontsize: 11pt
---

\newpage

# Executive Summary

**Alpha Wallet Scout** is a self-improving trading intelligence system that discovers high-performing on-chain traders and alerts users to their moves in real-time.

## The Opportunity

- **$2.4T+ crypto market** with millions of daily traders
- **Retail traders lose 90%+** of the time due to information asymmetry
- **Smart money wins consistently** - following them is the edge
- **No existing solution** offers automated wallet discovery + AI validation + multi-chain support at $0 cost

## Our Solution

A fully automated system that:

1. **Discovers** top-performing wallets from trending tokens across 9 data sources
2. **Analyzes** 30-day performance using FIFO PnL and proprietary "Being-Early" scoring
3. **Monitors** high-signal wallets in real-time across Ethereum, Solana, Base, Arbitrum
4. **Alerts** via Telegram with on-demand AI validation (Phi-3 LLM)
5. **Tracks** alert outcomes to measure real-world performance

## Key Metrics

| Metric | Value |
|--------|-------|
| **Monthly Operating Cost** | $0-20 (all free APIs + local AI) |
| **Alert Latency** | <5 seconds from trade to notification |
| **Data Sources** | 9 free APIs (DEX Screener, Pump.fun, GMGN, etc.) |
| **Chains Supported** | 4 (Ethereum, Base, Arbitrum, Solana) |
| **API Cost Reduction** | 90% via Redis caching |
| **AI Activation Rate** | 5-10% (on-demand for high-probability signals only) |

## Competitive Advantage

- ✅ **100% free infrastructure** (vs competitors charging $50-500/mo)
- ✅ **Local AI** (Ollama/Phi-3) with on-demand activation
- ✅ **Self-improving watchlist** (auto-add/remove based on performance)
- ✅ **Multi-chain from day 1** (most competitors are single-chain)
- ✅ **Outcome tracking** (measure alert performance, not just send alerts)
- ✅ **Open source** (transparency, community contributions, enterprise licensing)

\newpage

# The Problem

## Information Asymmetry in Crypto Markets

**Retail traders are always late:**

1. Token launches → Smart money buys → Price pumps → Retail hears about it → Smart money exits → Retail buys the top
2. By the time a token trends on Twitter/Discord, early buyers have already 5-10x'd
3. **Result**: Retail consistently loses money while smart wallets compound gains

## Current Solutions Are Inadequate

### Manual Wallet Tracking
- Time-consuming to find good wallets
- No systematic performance analysis
- Miss trades when not watching

### Paid Alert Services ($50-500/mo)
- Curated by humans (slow, biased)
- Black box scoring (no transparency)
- Single-chain only (miss opportunities)
- No outcome tracking (can't verify if alerts work)

### Social Media Alpha
- Low signal-to-noise ratio
- Conflicting opinions
- Often shilling bags
- No accountability

## The Core Insight

**Stop analyzing tokens. Start following wallets that consistently win.**

If someone turned $10k → $500k last month by buying tokens early, you want to know what they're buying **right now**.

\newpage

# Our Solution

## System Architecture

```
┌─────────────────────────────────────────────┐
│  9 FREE Data Sources (DEX Screener, etc.)   │
│  Cached 15min in Redis → 90% fewer calls    │
└──────────────┬──────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Token Discovery Engine (Every 15 min)       │
│  - Trending tokens across all chains         │
│  - NEW pools (Defined.fi catches earliest)   │
│  - Scam/honeypot filtering                   │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Wallet Discovery (Every 15 min)             │
│  - Fetch 24-72h buyers for each token        │
│  - Check wallet labels (Ansem, Tetranode...) │
│  - Filter bots, contracts, MEV               │
│  - Queue for 30-day backfill                 │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Analytics Engine (Hourly)                   │
│  - FIFO PnL calculation                      │
│  - Being-Early Score (0-100)                 │
│  - 30-day performance stats                  │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Watchlist Curator (Nightly)                 │
│  - Auto-add: ≥$50k PnL, ≥3x best trade       │
│  - Auto-remove: Negative PnL, >50% drawdown  │
│  - Result: 20-100 high-signal wallets        │
└──────────────┬───────────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────────┐
│  Real-Time Monitor (Webhooks + 30s polling)  │
│  - Detect watchlist wallet trades            │
│  - Confluence detection (≥2 wallets)         │
│  - Preliminary scoring (0-100)               │
└──────────────┬───────────────────────────────┘
               │
    ┌──────────┴──────────┐
    ▼                     ▼
┌──────────┐      ┌──────────────────────────┐
│  AI      │      │  Telegram Alert          │
│  Phi-3   │─────▶│  - Wallet names/labels   │
│  (local) │      │  - Explorer links        │
│          │      │  - AI confidence score   │
└──────────┘      │  - Recommendation        │
  ↑               └──────────────────────────┘
  │
  └─ Activates ONLY for:
     • Preliminary score ≥75
     • Confluence (≥2 wallets)
     • Labeled wallet detected
```

\newpage

## Key Innovations

### 1. On-Demand AI (Not Always-On)

**Problem**: Running AI on every signal is expensive and slow.

**Our Solution**: Smart activation logic

- Calculate **preliminary score** using traditional metrics (fast, free)
- LLM activates **only if**:
  - Preliminary score ≥75/100 **OR**
  - Multiple wallets buying (confluence) **OR**
  - Known labeled wallet involved **OR**
  - Preliminary score ≥85 (high confidence)

**Result**:
- 90-95% of signals never trigger LLM (low scores filtered out)
- High-probability signals get AI validation in <2 seconds
- **95% cost reduction** vs always-on AI
- Completely free with local Ollama/Phi-3

### 2. Being-Early Metric (Proprietary)

Most systems only look at PnL. We score **timing**.

```
Being-Early Score (0-100) =
    40 × (1 - buy_rank_percentile)          # How early they bought
  + 40 × clip((1M - market_cap) / 1M)       # How low the MC was
  + 20 × volume_participation               # How big their buy was
```

**Why this matters**:
- A wallet that makes $100k buying at $50k MC is **better** than one making $100k at $5M MC
- Early buyers have edge (alpha, research, insider info)
- High Being-Early scores identify **true alpha finders**

**Example**:
- Wallet buys at rank #5 out of 500 buyers → `rank_score = 39.6`
- Market cap at buy: $200k → `mc_score = 32`
- Buy size: 2% of volume → `size_score = 10`
- **Total: 81.6/100** ✨ (Exceptional timing)

### 3. Multi-Source Aggregation

**9 free data sources** working together:

| Source | Specialty | Latency |
|--------|-----------|---------|
| **Defined.fi** | NEW pools (catches earliest) | Minutes |
| **Pump.fun** | Solana memecoin launches | Real-time |
| **GMGN** | Solana smart money labels | Real-time |
| **DEX Screener** | Cross-chain trending | 5-15 min |
| **Dextools** | Hot pairs | 5-15 min |
| **GeckoTerminal** | Multi-DEX trending | 10-30 min |
| **CoinGecko** | Established trending | 30-60 min |
| **Jupiter** | Solana DEX aggregator | Real-time |
| **Birdeye** | Solana analytics | Real-time |

**Why multiple sources**:
- Different sources catch tokens at different lifecycle stages
- Defined.fi catches tokens **minutes** after launch
- GeckoTerminal catches tokens after initial pump (confirmation)
- Together: comprehensive coverage from launch → maturity

### 4. Wallet Labels Database

Pre-loaded with known traders:
- **Ansem** (Ethereum influencer, proven track record)
- **Tetranode** (Legendary ETH whale)
- **Other verified traders** from Twitter, Discord, on-chain analysis

**User-extensible**:
- Add your own wallets to track
- Tag wallets you discover
- System gives labeled wallets priority in scoring

### 5. Outcome Tracking (Accountability)

Most alert services send alerts but never check if they worked.

**We track**:
- Token price 1h, 6h, 24h after alert
- Win rate (% of alerts that went up)
- Average return per alert
- Best/worst performers

**Daily summary example**:
```
📊 Yesterday's Performance
Alerts sent: 7
Profitable: 5 (71% win rate)
Average return: +23%
Best performer: PEPE +127% (24h)
```

\newpage

# Business Model

## Current: Open Source

**Status**: Fully open-source (MIT license)

**Benefits**:
- Community contributions (new data sources, chains, features)
- Transparency builds trust
- Attract developer talent
- Viral growth via GitHub

## Revenue Streams (Future)

### 1. Premium Hosted Service ($29-99/mo)
- Fully managed cloud deployment
- 24/7 monitoring and alerts
- Priority support
- Custom webhook integrations
- Target: Retail traders who want zero setup

### 2. Enterprise API ($499-2,999/mo)
- REST API access to all data
- Real-time websocket feeds
- Custom watchlist management
- SLA guarantees
- Target: Trading firms, hedge funds, analytics platforms

### 3. White-Label Licensing ($5k-50k one-time)
- Deploy under your own brand
- Custom UI/branding
- On-premise deployment option
- Target: Crypto media companies, trading communities, Discord servers

### 4. Advanced Features (Freemium Add-Ons)
- **Copy Trading** ($49/mo): Auto-execute trades when wallets buy
- **Web Dashboard** ($19/mo): Visual analytics, backtesting
- **Discord Bot** ($29/mo): Alerts in Discord servers
- **Twitter Monitoring** ($39/mo): Track trader tweets + on-chain correlation

## Market Sizing

**TAM** (Total Addressable Market):
- 420M+ crypto users globally (2024)
- 50M+ active monthly traders
- Target: 1% penetration = **500k users**

**SAM** (Serviceable Addressable Market):
- English-speaking traders with $1k+ portfolios: ~10M
- Target: 5% penetration = **500k users**

**SOM** (Serviceable Obtainable Market - Year 3):
- Conservative: 10k free users, 1k paid users
- Revenue: 1k users × $50 avg/mo = **$50k MRR = $600k ARR**

## Unit Economics (Premium Tier)

**Assumptions**:
- Price: $49/mo
- Server cost per user: $2/mo (shared VPS, caching)
- Gross margin: **96%**

**Customer Lifetime Value** (conservative):
- Avg subscription: 8 months
- Churn: 12.5%/mo
- LTV: $49 × 8 = **$392**

**Customer Acquisition Cost**:
- Content marketing + SEO: $20/customer
- Paid ads: $50/customer
- Blended: **$30/customer**

**LTV:CAC Ratio**: 392/30 = **13:1** (excellent)

\newpage

# Competitive Landscape

## Direct Competitors

| Competitor | Price | Chains | AI | Open Source | Outcome Tracking |
|------------|-------|--------|-----|-------------|------------------|
| **Nansen** | $150/mo | 10+ | ❌ | ❌ | ❌ |
| **Arkham** | $50/mo | 5 | ❌ | ❌ | ❌ |
| **Breadcrumbs** | $99/mo | 3 | ❌ | ❌ | ❌ |
| **DeBank** | Free* | 20+ | ❌ | ❌ | ❌ |
| **Alpha Wallet Scout** | **$0-20** | **4** | **✅** | **✅** | **✅** |

*DeBank is free for viewing, but alerts/API require $49/mo

## Our Advantages

### 1. Cost Structure
- **Competitors**: Paid APIs, cloud AI, managed infrastructure → $50-150/mo
- **Us**: Free APIs, local AI, self-hosted → $0-20/mo
- **Advantage**: 75-100% cost reduction → accessible to retail

### 2. AI Integration
- **Competitors**: Static scoring, no AI validation
- **Us**: On-demand Phi-3 LLM with optimized prompts
- **Advantage**: Higher signal quality, automated reasoning

### 3. Transparency
- **Competitors**: Black box algorithms, proprietary scoring
- **Us**: Open source, documented metrics, outcome tracking
- **Advantage**: Trust, community contributions, auditability

### 4. Extensibility
- **Competitors**: Locked ecosystems, limited customization
- **Us**: Add your own data sources, filters, LLMs
- **Advantage**: Power users can customize, developers can contribute

## Barriers to Entry

### Technical Moats

1. **Multi-source aggregation logic**: 9 APIs working together requires complex deduplication and normalization
2. **FIFO PnL calculation**: Handling cross-chain, multi-wallet, multi-token accounting is non-trivial
3. **On-demand AI**: Smart activation logic + prompt engineering took significant R&D
4. **Caching architecture**: 90% API reduction requires sophisticated Redis patterns

### Network Effects

1. **Wallet labels database**: Grows with community contributions (more users = more labeled wallets)
2. **Outcome data**: More alerts = more performance data = better scoring
3. **GitHub stars/forks**: Open source → viral growth → community → contributors

### Operational Moats

1. **Free tier partnerships**: Established relationships with Alchemy, Helius, etc.
2. **API expertise**: Deep knowledge of 9+ different APIs and their quirks
3. **Community trust**: First-mover advantage in open-source crypto intelligence

\newpage

# Technology Stack

## Infrastructure

| Component | Technology | Cost | Scalability |
|-----------|-----------|------|-------------|
| **Database** | PostgreSQL 15 | $0 (Docker) | Millions of trades |
| **Cache** | Redis 7 | $0 (Docker) | Millions of keys |
| **API** | FastAPI (Python) | $0 (self-hosted) | 10k req/sec |
| **Worker** | APScheduler | $0 (self-hosted) | Parallel jobs |
| **AI** | Ollama + Phi-3 | $0 (local CPU/GPU) | Unlimited |
| **Hosting** | VPS/Cloud | $5-20/mo | Horizontal scaling |

## External Dependencies

### Blockchain Data (Free Tiers)
- **Alchemy**: 300M compute units/mo = ~10M requests
- **Helius**: 100k requests/mo for Solana
- Both provide webhooks for real-time monitoring

### Token Data (All Free)
- DEX Screener: Unlimited with rate limiting
- Pump.fun: Public API, no auth required
- GMGN: Free tier with caching
- Defined.fi: GraphQL, free tier
- GeckoTerminal: Free tier, generous limits
- Dextools: Free tier
- CoinGecko: Free tier
- Jupiter: Free tier (Solana)
- Birdeye: Optional, free tier available

### Alerts
- **Telegram**: Unlimited messages, free forever

## Production Deployment

**Current**: Docker Compose (5 containers)
- PostgreSQL, Redis, Ollama, API, Worker

**Future Scale**: Kubernetes
- Horizontal scaling for API/Worker
- Managed PostgreSQL (RDS/DigitalOcean)
- Managed Redis (ElastiCache/DigitalOcean)
- GPU nodes for faster LLM inference

**Monitoring**:
- Health check endpoints
- Structured logging (JSON)
- Metrics collection ready (Prometheus)

\newpage

# Go-to-Market Strategy

## Phase 1: Community Building (Months 1-3)

**Objective**: 1,000 GitHub stars, 100 active users

**Tactics**:
1. **Launch on Product Hunt** - tech-savvy early adopters
2. **Reddit marketing** - r/CryptoTechnology, r/algotrading, r/CryptoCurrency
3. **Twitter strategy** - thread on "How I built a free Nansen alternative"
4. **YouTube tutorials** - "Setup Alpha Wallet Scout in 10 minutes"
5. **Blog content** - "Following smart money: A systematic approach"

**Budget**: $0 (organic only)

## Phase 2: Growth (Months 4-6)

**Objective**: 5,000 stars, 500 active users, first paid customers

**Tactics**:
1. **Launch premium hosted service** - $49/mo, 1-click deploy
2. **Content marketing** - SEO-optimized guides, case studies
3. **Partnerships** - Integrate with existing crypto tools (Discord bots, Telegram groups)
4. **Influencer outreach** - Sponsor crypto YouTubers/podcasters
5. **Paid ads** - Twitter ads targeting crypto traders

**Budget**: $5k/mo (influencers $3k, ads $2k)

## Phase 3: Scale (Months 7-12)

**Objective**: 20,000 stars, 2,000 active users, $50k MRR

**Tactics**:
1. **Enterprise sales** - Reach out to trading firms, hedge funds
2. **White-label licensing** - Partner with crypto media companies
3. **Advanced features** - Copy trading, web dashboard
4. **Conference presence** - ETHDenver, Consensus, Token2049
5. **Paid growth channels** - Google ads, crypto newsletter sponsorships

**Budget**: $20k/mo (ads $10k, conferences $5k, sales $5k)

## Distribution Channels

### Organic (Free)
- GitHub (primary)
- Twitter/X (crypto trading community)
- Reddit (r/CryptoCurrency, r/algotrading)
- YouTube (tutorial content)
- Medium/Substack (long-form content)

### Paid
- Twitter ads (targeting crypto traders)
- Google ads (keywords: "crypto trading bot", "wallet tracker")
- Crypto newsletter sponsorships (The Defiant, Bankless)
- YouTube sponsorships (crypto trading channels)
- Conference sponsorships (ETHDenver, etc.)

### Partnerships
- Integration with Discord bots (trading communities)
- Telegram group partnerships (alpha channels)
- API partnerships (other crypto analytics platforms)
- Exchange partnerships (Binance, Coinbase developer programs)

\newpage

# Financial Projections

## Year 1: Launch & Validation

**Assumptions**:
- Launch: Month 1
- Premium service: Month 4
- Enterprise: Month 7

| Metric | Q1 | Q2 | Q3 | Q4 |
|--------|-----|-----|-----|-----|
| **Users (Free)** | 100 | 500 | 1,500 | 3,000 |
| **Users (Paid)** | 0 | 10 | 50 | 200 |
| **MRR** | $0 | $490 | $2,450 | $9,800 |
| **ARR** | $0 | $5,880 | $29,400 | $117,600 |
| **Costs** | $0 | $5k | $10k | $20k |
| **Burn** | $0 | -$4.5k | -$7.5k | -$10k |

**Cumulative Burn**: -$22k (bootstrappable)

## Year 2: Growth

**Assumptions**:
- Paid conversion rate: 5% (conservative)
- Enterprise deals: 2 @ $999/mo

| Metric | Q1 | Q2 | Q3 | Q4 |
|--------|-----|-----|-----|-----|
| **Users (Free)** | 5,000 | 8,000 | 12,000 | 20,000 |
| **Users (Paid)** | 350 | 550 | 800 | 1,200 |
| **Enterprise** | 2 | 3 | 4 | 5 |
| **MRR** | $19k | $31k | $43k | $64k |
| **ARR** | $228k | $372k | $516k | $768k |
| **Costs** | $25k | $30k | $40k | $50k |
| **Profit/Loss** | -$6k | +$1k | +$3k | +$14k |

**Cumulative**: Profitable by Q2 Y2

## Year 3: Scale

**Assumptions**:
- Paid conversion: 7% (improving)
- Enterprise: 10 @ $1,499/mo avg
- White-label: 3 @ $20k one-time

| Metric | Q1 | Q2 | Q3 | Q4 |
|--------|-----|-----|-----|-----|
| **Users (Free)** | 30k | 45k | 60k | 80k |
| **Users (Paid)** | 1,800 | 2,700 | 3,600 | 4,800 |
| **Enterprise** | 8 | 10 | 12 | 15 |
| **MRR** | $100k | $147k | $194k | $252k |
| **ARR** | $1.2M | $1.76M | $2.33M | $3.02M |
| **Costs** | $60k | $75k | $90k | $110k |
| **Profit/Loss** | +$40k | +$72k | +$104k | +$142k |

**Cumulative Year 3 Profit**: $358k

## Revenue Breakdown (Year 3)

- **Premium subscriptions**: 4,800 × $49 × 12 = **$2.82M** (93%)
- **Enterprise API**: 15 × $1,499 × 12 = **$270k** (9%)
- **White-label**: 3 × $20k = **$60k** (2%)
- **Total ARR**: **$3.15M**

\newpage

# Funding & Use of Funds

## Current Status: Bootstrapped

- **Investment to date**: $0 (built by founders)
- **MRR**: $0 (pre-revenue)
- **Runway**: Infinite (no burn)

## Funding Ask: $100k Seed (Optional)

**Use of Funds**:

| Category | Amount | Purpose |
|----------|--------|---------|
| **Marketing** | $40k | Influencer partnerships, paid ads, conference presence |
| **Product** | $30k | Web dashboard, mobile app, advanced features |
| **Infrastructure** | $10k | Managed hosting, GPU nodes for faster AI |
| **Legal** | $10k | Entity formation, terms of service, privacy policy |
| **Operations** | $10k | Tools, subscriptions, misc expenses |

**Timeline**: 12 months to $50k MRR (500 paid users)

**Valuation**: $1M pre-money (10x annual revenue at end of period)

## Alternative: Revenue-Based Financing

If we achieve $10k MRR (Month 6), raise $50k RBF:
- **Terms**: 1.5x cap, 10% of monthly revenue
- **Use**: Accelerate paid growth channels
- **Payback**: 15 months at $10k MRR

## No-Funding Path (Default)

Continue bootstrapping:
- Organic growth only (no paid marketing)
- Slower but sustainable
- Maintain full equity and control
- Reach profitability by Month 9-12

\newpage

# Team & Advisors

## Current Team

**Founders**: (To be filled in with your team details)

### Roles Needed (Year 1)

**Full-Time**:
1. **CTO/Lead Engineer** - Maintain infrastructure, add features
2. **Growth Marketer** - Content, SEO, paid acquisition
3. **Community Manager** - Discord, Telegram, GitHub support

**Part-Time/Contract**:
1. **Designer** - Web dashboard, marketing materials
2. **Content Creator** - YouTube tutorials, blog posts
3. **DevRel** - GitHub community, open-source contributions

## Advisory Board (Target)

**Ideal Advisors**:
1. **Crypto Trading Expert** - Validate product, network into trading communities
2. **Open Source Veteran** - Growth strategies for developer tools
3. **Enterprise Sales** - B2B sales to trading firms, hedge funds
4. **AI/ML Engineer** - Optimize LLM performance, explore new models

**Compensation**: 0.25-0.5% equity, 2-year vest

\newpage

# Risks & Mitigation

## Technical Risks

### 1. API Rate Limits / Changes

**Risk**: Free API tiers get reduced or removed

**Mitigation**:
- 9 different sources (no single point of failure)
- Aggressive caching (90% reduction)
- Build relationships with providers
- Fallback to paid tiers if necessary (still <$50/mo)

**Likelihood**: Low | **Impact**: Medium

### 2. LLM Performance Degradation

**Risk**: Phi-3 doesn't perform well on crypto signals

**Mitigation**:
- Swappable LLM backend (can use GPT-4, Claude, Llama, etc.)
- Prompt engineering testing framework
- Preliminary scoring works without LLM
- Users can disable AI if desired

**Likelihood**: Low | **Impact**: Low

### 3. Blockchain Data Availability

**Risk**: Alchemy/Helius change terms, lose access

**Mitigation**:
- Multiple providers (Alchemy, Helius, QuickNode, Infura)
- Self-host nodes as last resort (more expensive but viable)
- Community can run their own infrastructure

**Likelihood**: Low | **Impact**: Medium

## Market Risks

### 1. Crypto Bear Market

**Risk**: User interest drops during prolonged bear market

**Mitigation**:
- Low operating cost ($0-20/mo) means can survive indefinitely
- Bear markets = fewer tokens, easier to identify quality
- Shift marketing to "preservation" vs "gains"
- Diversify to stocks/forex (technical debt, but possible)

**Likelihood**: Medium | **Impact**: Medium

### 2. Regulatory Crackdown

**Risk**: Governments restrict crypto trading tools

**Mitigation**:
- Open source = can't be shut down
- No custodial function (just information)
- Operate in friendly jurisdictions
- Pivot to "research tool" if needed

**Likelihood**: Low | **Impact**: High

### 3. Competitor Catches Up

**Risk**: Nansen/Arkham add similar features

**Mitigation**:
- Open source = faster iteration via community
- Cost advantage (free vs $150/mo)
- Network effects (labeled wallets, outcome data)
- First-mover advantage in open-source space

**Likelihood**: Medium | **Impact**: Medium

## Operational Risks

### 1. Key Person Dependency

**Risk**: Founder(s) leave, project stalls

**Mitigation**:
- Comprehensive documentation
- Open source = community can fork
- Hire redundant engineers early
- Build strong community of contributors

**Likelihood**: Low | **Impact**: High

### 2. Scaling Infrastructure

**Risk**: Can't handle 10k+ users on current setup

**Mitigation**:
- Architecture designed for horizontal scaling
- Kubernetes migration path documented
- Managed service providers (RDS, ElastiCache) ready
- Revenue from paid users funds infrastructure

**Likelihood**: Low | **Impact**: Medium

\newpage

# Traction & Milestones

## Current Status

**Product**:
- ✅ MVP complete (all core features)
- ✅ Docker deployment working
- ✅ 9 data sources integrated
- ✅ AI integration (Ollama/Phi-3)
- ✅ Telegram alerts functional
- ✅ Open source (MIT license)

**Metrics**:
- GitHub: Not yet public
- Users: 1 (founder)
- MRR: $0 (pre-launch)

## 30-Day Milestones

- [ ] Public GitHub launch
- [ ] Product Hunt launch
- [ ] 100 GitHub stars
- [ ] 10 active users (free)
- [ ] First community contribution (PR)

## 90-Day Milestones

- [ ] 500 GitHub stars
- [ ] 50 active users
- [ ] Premium service launch
- [ ] First paid customer
- [ ] $500 MRR

## 180-Day Milestones

- [ ] 2,000 GitHub stars
- [ ] 200 active users
- [ ] 20 paid customers
- [ ] $1,000 MRR
- [ ] First enterprise lead

## 1-Year Milestones

- [ ] 5,000 GitHub stars
- [ ] 1,000 active users
- [ ] 100 paid customers
- [ ] $5,000 MRR
- [ ] Profitable month-to-month

\newpage

# Appendix

## Sample Alert (Telegram)

```
🚨 CONFLUENCE (2 wallets) 🚨

Token: PEPE ($0.00000123)
MCap: $450k | Liq: $250k

Wallets:
- Ansem ✓ (0x8f94...)
  30D PnL: $127k | Best: 8.2x | Early: 85

- Unknown Whale #42 (0x3d2c...)
  30D PnL: $89k | Best: 5.1x | Early: 72

Confluence Window: 8 minutes
Avg 30D PnL: $108k

🤖 AI Analysis
Confidence: 89/100
Recommendation: BUY
Reasoning: Known trader Ansem + strong confluence
with high early scores suggests institutional interest

📊 Links
TX: solscan.io/tx/4xK9p...
Chart: birdeye.so/token/PEPE...
DEX: dexscreener.com/solana/PEPE
```

## Technical Specs

**Database Schema**: 8 tables
- tokens, seed_tokens, wallets, trades, positions, wallet_stats_30d, alerts, alert_outcomes

**API Endpoints**: 12 routes
- Health, watchlist, stats, alerts, trades, performance

**Background Jobs**: 6 scheduled tasks
- Token discovery (15min)
- Wallet discovery (15min)
- PnL calculation (hourly)
- Stats aggregation (hourly)
- Watchlist maintenance (nightly)
- Performance tracking (hourly)

**Codebase Stats**:
- Python files: 45+
- Lines of code: ~8,000
- Test coverage: (To be added)
- Dependencies: 25 packages

## Links

- **GitHub**: (To be added upon public launch)
- **Demo Video**: (To be added)
- **Documentation**: README.md, TOOLS_GUIDE.md, USAGE.md
- **Contact**: (Your email/Telegram)

---

**This document is confidential and intended for investor review only.**

Last updated: October 3, 2025
