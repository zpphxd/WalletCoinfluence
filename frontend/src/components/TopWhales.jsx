import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function TopWhales() {
  const [whales, setWhales] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadWhales()
    const interval = setInterval(loadWhales, 30000)
    return () => clearInterval(interval)
  }, [])

  const loadWhales = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/whales/top?limit=20`)
      setWhales(response.data.whales)
    } catch (err) {
      console.error('Failed to load whales:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading performance data</div>

  return (
    <div className="card">
      <h2>Top Performing Wallets</h2>
      <p style={{ color: 'var(--text-secondary)', marginBottom: '24px', fontSize: '0.95rem' }}>
        Highest profit wallets tracked in the last 30 days
      </p>
      <div className="whale-list">
        {whales.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '60px 20px' }}>
            <div style={{ fontSize: '3rem', marginBottom: '16px' }}>🐋</div>
            <p style={{ color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
              No profitable whales discovered yet
            </p>
          </div>
        ) : (
          whales.map((whale, idx) => {
            const medal = idx === 0 ? '🥇' : idx === 1 ? '🥈' : idx === 2 ? '🥉' : null

            return (
              <div key={whale.address} className="whale-item">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '16px' }}>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '8px' }}>
                      <span style={{
                        fontSize: '1.5rem',
                        fontWeight: '800',
                        color: 'var(--text-muted)',
                        minWidth: '32px'
                      }}>
                        {medal || `#${idx + 1}`}
                      </span>
                      <span className="address">{whale.address.slice(0, 16)}...{whale.address.slice(-12)}</span>
                    </div>
                  </div>
                  <div style={{ textAlign: 'right' }}>
                    <div style={{ fontSize: '1.5rem', fontWeight: '800', color: 'var(--success)' }}>
                      ${whale.unrealized_pnl_usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}
                    </div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                      Unrealized P/L
                    </div>
                  </div>
                </div>

                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '16px', paddingTop: '16px', borderTop: '1px solid var(--border-subtle)' }}>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                      Network
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: '600' }}>
                      {whale.chain_id === 'ethereum' ? 'ETH' : whale.chain_id.toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                      Trades
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: '600' }}>{whale.trades_count}</div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                      Best Return
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: '600' }}>
                      {whale.best_trade_multiple ? `${whale.best_trade_multiple.toFixed(1)}x` : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.05em', marginBottom: '4px' }}>
                      Early Score
                    </div>
                    <div style={{ fontSize: '0.95rem', fontWeight: '600' }}>
                      {whale.earlyscore_median ? whale.earlyscore_median.toFixed(0) : 'N/A'}
                    </div>
                  </div>
                </div>
              </div>
            )
          })
        )}
      </div>
    </div>
  )
}

export default TopWhales
