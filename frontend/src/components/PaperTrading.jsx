import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function PaperTrading() {
  const [status, setStatus] = useState(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadStatus()
    const interval = setInterval(loadStatus, 15000) // Refresh every 15s
    return () => clearInterval(interval)
  }, [])

  const loadStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/paper-trading/status`)
      setStatus(response.data)
    } catch (err) {
      console.error('Failed to load paper trading status:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading paper trading status...</div>
  if (!status || !status.active) return <div className="card">No paper trading data available</div>

  const roi = ((status.total_portfolio - status.starting_balance) / status.starting_balance) * 100

  return (
    <div>
      <div className="grid">
        <div className="card">
          <h2>Portfolio Summary</h2>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-label">Cash Balance</div>
              <div className="stat-value">${status.balance.toFixed(2)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Total Portfolio</div>
              <div className="stat-value">${status.total_portfolio.toFixed(2)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">ROI</div>
              <div className={`stat-value ${roi >= 0 ? 'positive' : 'negative'}`}>
                {roi >= 0 ? '+' : ''}{roi.toFixed(2)}%
              </div>
            </div>
            <div className="stat">
              <div className="stat-label">Win Rate</div>
              <div className="stat-value">
                {status.win_count + status.loss_count > 0
                  ? ((status.win_count / (status.win_count + status.loss_count)) * 100).toFixed(1)
                  : 0}%
              </div>
            </div>
          </div>
        </div>

        <div className="card">
          <h2>Performance</h2>
          <div className="stat-grid">
            <div className="stat">
              <div className="stat-label">Total Profit</div>
              <div className="stat-value positive">${status.total_profit.toFixed(2)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Total Loss</div>
              <div className="stat-value negative">${status.total_loss.toFixed(2)}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Wins</div>
              <div className="stat-value">{status.win_count}</div>
            </div>
            <div className="stat">
              <div className="stat-label">Losses</div>
              <div className="stat-value">{status.loss_count}</div>
            </div>
          </div>
        </div>
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Open Positions ({status.open_positions.length})</h2>
        <div className="position-list">
          {status.open_positions.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No open positions</p>
          ) : (
            status.open_positions.map((pos) => (
              <div
                key={pos.token_address}
                className={`position-item ${pos.profit_pct >= 0 ? 'profit' : 'loss'}`}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '8px' }}>
                  <span className="address">{pos.token_address.slice(0, 10)}...{pos.token_address.slice(-8)}</span>
                  <span className={pos.profit_pct >= 0 ? 'positive' : 'negative'} style={{ fontWeight: 'bold' }}>
                    {pos.profit_pct >= 0 ? '+' : ''}{pos.profit_pct.toFixed(2)}%
                  </span>
                </div>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', fontSize: '0.9rem' }}>
                  <div>
                    <div style={{ color: '#9ca3af', fontSize: '0.8rem' }}>Entry</div>
                    <div>${pos.entry_price.toFixed(8)}</div>
                  </div>
                  <div>
                    <div style={{ color: '#9ca3af', fontSize: '0.8rem' }}>Current</div>
                    <div>${pos.current_price.toFixed(8)}</div>
                  </div>
                  <div>
                    <div style={{ color: '#9ca3af', fontSize: '0.8rem' }}>P/L</div>
                    <div className={pos.profit_loss >= 0 ? 'positive' : 'negative'}>
                      ${pos.profit_loss.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card" style={{ marginTop: '20px' }}>
        <h2>Recent Closed Trades</h2>
        <div className="trade-list">
          {status.closed_trades.length === 0 ? (
            <p style={{ color: '#9ca3af' }}>No closed trades yet</p>
          ) : (
            status.closed_trades.map((trade, idx) => (
              <div key={idx} className="trade-item">
                <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                  <span className="address">{trade.token_address.slice(0, 10)}...{trade.token_address.slice(-8)}</span>
                  <span className={trade.profit_loss >= 0 ? 'positive' : 'negative'} style={{ fontWeight: 'bold' }}>
                    {trade.profit_loss >= 0 ? '✅' : '❌'} {trade.profit_pct >= 0 ? '+' : ''}{trade.profit_pct.toFixed(2)}%
                  </span>
                </div>
                <div style={{ fontSize: '0.85rem', color: '#9ca3af' }}>
                  ${trade.profit_loss.toFixed(2)} • {trade.reason}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  )
}

export default PaperTrading
