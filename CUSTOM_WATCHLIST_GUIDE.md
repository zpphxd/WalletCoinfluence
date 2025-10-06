# Custom Watchlist Guide

**Date**: October 6, 2025
**Feature**: User-submitted whale wallets for confluence detection

---

## 🎯 What is the Custom Watchlist?

The custom watchlist allows you to manually add specific whale wallets you want to monitor for confluence signals. These wallets will be tracked alongside auto-discovered whales and contribute to confluence detection when they make trades.

### Why Use This?

- **Follow Known Whales**: Track wallets you've identified as consistently profitable
- **Cross-Chain Monitoring**: Add wallets from Ethereum, Base, Arbitrum, or Solana
- **Personal Research**: Monitor wallets you've researched independently
- **Confluence Boosting**: Your custom wallets count toward the 5+ whale confluence threshold

---

## 📋 How to Add Custom Wallets

### Method 1: Web Dashboard (Recommended)

1. **Start the dashboard**:
   ```bash
   cd "/Users/zachpowers/Wallet Signal"
   ./start_frontend.sh
   ```

2. **Open browser**: http://localhost:3000

3. **Navigate to "Custom Watchlist" tab**

4. **Click "+ Add Wallet"**

5. **Fill in the form**:
   - **Wallet Address** (required): The wallet address (0x... for EVM chains)
   - **Chain**: ethereum, base, arbitrum, or solana
   - **Label** (optional): A friendly name like "Top Meme Whale"
   - **Notes** (optional): Any observations about this wallet

6. **Click "Add to Watchlist"**

### Method 2: CLI Tool

```bash
# Add a wallet
python manage_watchlist.py add 0x1234... ethereum "My favorite whale"

# List all custom wallets
python manage_watchlist.py list

# Remove a wallet
python manage_watchlist.py remove 0x1234... ethereum
```

---

## 🔍 Example: Adding a Known Profitable Whale

Let's say you've noticed wallet `0x9c22836e733d1611d41020123da7aa72f475cc7b` consistently making profitable trades on Ethereum.

**Using Dashboard**:
1. Go to Custom Watchlist tab
2. Click "+ Add Wallet"
3. Enter:
   - Address: `0x9c22836e733d1611d41020123da7aa72f475cc7b`
   - Chain: `ethereum`
   - Label: `PNKSTR whale - 4x returns`
   - Notes: `Found this wallet via whale analysis. Made $715 on PNKSTR in one trade.`
4. Save

**Using CLI**:
```bash
python manage_watchlist.py add \
  0x9c22836e733d1611d41020123da7aa72f475cc7b \
  ethereum \
  "PNKSTR whale - 4x returns"
```

---

## 🐋 How Custom Wallets Work in Confluence

Once added, your custom wallets are:

1. **Monitored every 2 minutes** for new trades (same as auto-discovered whales)
2. **Included in confluence detection** - If your custom whale + 4 auto-discovered whales buy the same token within 30 minutes, that's a **5-whale confluence signal**
3. **Tracked for stats** - Their PnL, trade count, and EarlyScore are calculated
4. **Visible in dashboard** - See their performance in real-time

### Confluence Example:

```
🚨 5-WHALE CONFLUENCE DETECTED 🚨

Token: PEPE ($0.00000123)
Time Window: 12 minutes

Wallets:
1. 0x9c2283... (YOUR CUSTOM WHALE) | $715 PnL | Early: 47.6
2. 0xe101e6... (auto-discovered)  | $892 PnL | Early: 52.1
3. 0x13e936... (auto-discovered)  | $450 PnL | Early: 38.9
4. 0x2f4a8c... (auto-discovered)  | $320 PnL | Early: 41.2
5. 0x7b9e1d... (auto-discovered)  | $210 PnL | Early: 36.5

🤖 Paper trading will execute BUY with 40% of balance!
```

---

## 📊 Viewing Custom Wallet Performance

### In the Dashboard:

The Custom Watchlist tab shows:
- All your custom wallets
- Their labels and notes
- Live stats (if available):
  - **Trades**: Number of trades made
  - **P/L**: Current unrealized profit/loss
  - **Early Score**: How early they buy (0-100)

### Finding Good Whales to Add:

1. **Check "Top Whales" tab** - See the most profitable auto-discovered whales
2. **Review recent confluence** - See which wallets are frequently buying together
3. **External research** - Use Etherscan, Debank, or other tools to find wallets
4. **Add to custom list** - Once you find a good one, add it permanently

---

## 🎯 Best Practices

### Start Small:
- Add 3-5 high-quality whales initially
- Watch how they perform
- Add more as you discover them

### Label Clearly:
- Use descriptive labels: "Meme king - 10x avg", "Early PEPE buyer", etc.
- Add notes about why you're tracking them

### Review Regularly:
- Check dashboard weekly
- Remove wallets that stop performing
- Add new whales as you discover them

### Cross-Reference:
- Compare your custom whales to auto-discovered ones
- Look for patterns in what makes a wallet profitable
- Learn from the system's discoveries

---

## 🔧 Technical Details

### Database Storage:

Custom wallets are stored in the `custom_watchlist_wallets` table with:
- `address` + `chain_id` (primary key)
- `label` (optional custom name)
- `notes` (optional notes)
- `is_active` (soft delete flag)
- `added_at` (timestamp)

### Integration:

Custom wallets are fetched in `wallet_monitor.py` via:
```python
def _get_watchlist_wallets(self):
    # Get auto-discovered whales ($500+ PnL)
    profitable_whales = ...

    # Get custom watchlist wallets
    custom_wallets = ...

    # Combine both (remove duplicates)
    return unique_wallets
```

### API Endpoints:

- `GET /api/watchlist` - List all custom wallets
- `POST /api/watchlist` - Add a wallet
- `PATCH /api/watchlist/{address}` - Update label/notes
- `DELETE /api/watchlist/{address}` - Remove wallet (soft delete)

---

## 🚀 Next Steps

1. **Start the dashboard**: `./start_frontend.sh`
2. **Add your first whale**: Use Custom Watchlist tab
3. **Monitor confluence**: Watch for alerts when your custom whales trade
4. **Refine your list**: Keep the profitable ones, remove the duds
5. **Learn patterns**: See what makes a whale consistently profitable

---

## 💡 Pro Tips

- **Don't over-add**: 10-20 quality whales > 100 mediocre ones
- **Track chains separately**: A whale good at Ethereum memes may not be good at Solana
- **Watch confluence patterns**: Which wallets frequently buy together?
- **Use notes field**: Record your observations for future reference
- **Check Top Whales tab**: The system auto-discovers new profitable wallets daily

---

**The edge**: Following proven winners, not random traders. Your custom watchlist is YOUR personal whale tracker!
