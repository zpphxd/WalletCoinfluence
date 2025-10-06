import React from 'react'

function Dashboard({ stats }) {
  if (!stats) return <div className="loading">Loading system metrics</div>

  const paperTrading = stats.paper_trading
  const watchlist = stats.custom_watchlist || {}
  const profitableRate = stats.total_whales > 0
    ? ((stats.profitable_whales / stats.total_whales) * 100).toFixed(1)
    : 0

  return (
    <div>
      <div className="grid">
        {/* Custom Watchlist - UPGRADED */}
        <div className="card">
          <h2>⭐ Verified Whale Watchlist</h2>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-label">Total Whales</div>
              <div className="stat-value">{watchlist.total || 0}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Tier 1 Mega ($10M+)</div>
              <div className="stat-value positive">{watchlist.tier1_mega || 0}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Tier 2 Strong ($1M+)</div>
              <div className="stat-value positive">{watchlist.tier2_strong || 0}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Networks</div>
              <div className="stat-value" style={{ fontSize: '1.25rem' }}>
                {(watchlist.ethereum || 0) > 0 && `ETH ${watchlist.ethereum}`}
                {(watchlist.ethereum || 0) > 0 && (watchlist.solana || 0) > 0 && ' · '}
                {(watchlist.solana || 0) > 0 && `SOL ${watchlist.solana}`}
              </div>
            </div>
          </div>
          <div style={{ marginTop: '12px', padding: '12px', background: 'var(--bg-secondary)', borderRadius: '6px', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            Nansen-verified whales with $51.9M proven performance · Upgraded Oct 6, 2025
          </div>
        </div>

        {/* Auto-Discovery Stats */}
        <div className="card">
          <h2>Auto-Discovery</h2>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-label">Tracked Wallets</div>
              <div className="stat-value">{stats.total_whales.toLocaleString()}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Profitable</div>
              <div className="stat-value positive">{stats.profitable_whales.toLocaleString()}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Success Rate</div>
              <div className="stat-value positive">{profitableRate}%</div>
            </div>
            <div className="stat">
              <div className="stat-label">Total Trades</div>
              <div className="stat-value">{stats.total_trades.toLocaleString()}</div>
            </div>
          </div>
        </div>

        {/* Market Coverage */}
        <div className="card">
          <h2>Market Coverage</h2>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-label">Tokens Monitored</div>
              <div className="stat-value">{stats.total_tokens.toLocaleString()}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Signals (All Time)</div>
              <div className="stat-value">{stats.total_alerts.toLocaleString()}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Signals (24h)</div>
              <div className="stat-value">{stats.recent_alerts_24h.toLocaleString()}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Avg. per Hour</div>
              <div className="stat-value">
                {Math.round(stats.recent_alerts_24h / 24)}
              </div>
            </div>
          </div>
        </div>

        {/* Portfolio Performance */}
        {paperTrading && (
          <div className="card">
            <h2>Portfolio Performance</h2>
            <div className="stat-grid">
              <div className="stat">
                <div className="stat-label">Cash Balance</div>
                <div className="stat-value">${paperTrading.balance.toFixed(2)}</div>
              </div>
              <div className="stat">
                <div className="stat-label">Total P/L</div>
                <div className={`stat-value ${(paperTrading.total_profit + paperTrading.total_loss) >= 0 ? 'positive' : 'negative'}`}>
                  {(paperTrading.total_profit + paperTrading.total_loss) >= 0 ? '+' : ''}
                  ${(paperTrading.total_profit + paperTrading.total_loss).toFixed(2)}
                </div>
              </div>
              <div className="stat">
                <div className="stat-label">Win Rate</div>
                <div className="stat-value">
                  {paperTrading.win_count + paperTrading.loss_count > 0
                    ? ((paperTrading.win_count / (paperTrading.win_count + paperTrading.loss_count)) * 100).toFixed(1)
                    : 0}%
                </div>
              </div>
              <div className="stat">
                <div className="stat-label">Active Positions</div>
                <div className="stat-value">{paperTrading.open_positions}</div>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* System Status Bar */}
      <div className="card" style={{ marginTop: '24px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '24px' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <div style={{ width: '8px', height: '8px', borderRadius: '50%', background: 'var(--success)', boxShadow: '0 0 8px var(--success)' }} />
            <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>System Operational</span>
          </div>
          <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
            Data refreshes every 30 seconds
          </div>
        </div>
      </div>
    </div>
  )
}

export default Dashboard
