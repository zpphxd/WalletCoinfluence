# 🔑 Get Your API Keys (5 Minutes Each)

Your Telegram is already configured! ✅ You just need 2 more API keys.

---

## 1. Alchemy (Ethereum, Base, Arbitrum) - FREE

### Quick Steps:
1. **Go to:** https://www.alchemy.com
2. **Click:** "Get started for free" (top right)
3. **Sign up with Google/GitHub** (fastest)
4. **Create your first app:**
   - Click "Create new app"
   - Name: "Wallet Scout"
   - Chain: Ethereum
   - Network: Mainnet
5. **Copy the API Key:**
   - Click "API Keys" button
   - Copy the key (starts with `alch_`)
6. **Add to `.env`:**
   ```bash
   ALCHEMY_API_KEY=alch_YOUR_KEY_HERE
   ```

### Free Tier Limits:
- ✅ 300M compute units/month (plenty for this project)
- ✅ All chains included

---

## 2. Helius (Solana) - FREE

### Quick Steps:
1. **Go to:** https://www.helius.dev
2. **Click:** "Sign Up"
3. **Sign up with email or GitHub**
4. **Dashboard → API Keys:**
   - Your key is shown immediately
   - Copy the API key
5. **Add to `.env`:**
   ```bash
   HELIUS_API_KEY=YOUR_KEY_HERE
   ```

### Free Tier Limits:
- ✅ 100k requests/month
- ✅ RPC access included

---

## 3. Update .env and Start!

After you have both keys, your `.env` should look like:

```bash
TELEGRAM_BOT_TOKEN=8482390902:AAHFiGq9q9Gt-P7ErpZL0FDs9PyEYIwmN_c
TELEGRAM_CHAT_ID=8416972017
ALCHEMY_API_KEY=alch_xxxxxxxxxxxxxxxxxxxx
HELIUS_API_KEY=xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx
```

Then run:
```bash
cd "/Users/zachpowers/Wallet Signal"
./QUICKSTART.sh
```

---

## ⚡ FASTER Alternative: Use Only Ethereum (No Solana)

If you want to start RIGHT NOW with just Alchemy:

1. Get just the Alchemy key (2 min signup)
2. Edit `.env` and change:
   ```bash
   CHAINS=ethereum,base,arbitrum
   # Remove solana since you don't have Helius yet
   ```
3. Start: `./QUICKSTART.sh`
4. Add Helius later when you want Solana support

---

## Need Help?

**Stuck on Alchemy?** → Try signing up with Google (fastest)
**Stuck on Helius?** → Email signup is simplest
**Can't edit .env?** → Run: `nano .env` and paste the keys

---

**The signups are genuinely 2-3 minutes each with Google/GitHub login!**
