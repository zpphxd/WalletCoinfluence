import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function TrendingTokens() {
  const [tokens, setTokens] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    loadTokens()
    const interval = setInterval(loadTokens, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const loadTokens = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/tokens/trending?limit=20`)
      setTokens(response.data.trending_tokens)
    } catch (err) {
      console.error('Failed to load trending tokens:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <div className="loading">Loading trending tokens...</div>

  return (
    <div className="card">
      <h2>Trending Tokens (Most Whale Buys in 24h)</h2>
      <div className="token-list">
        {tokens.length === 0 ? (
          <p style={{ color: '#9ca3af', textAlign: 'center', padding: '40px' }}>
            No trending tokens yet
          </p>
        ) : (
          tokens.map((token, idx) => (
            <div key={token.token_address} className="token-item">
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                <div>
                  <span style={{ fontSize: '1.2rem', fontWeight: '700', marginRight: '12px' }}>
                    #{idx + 1}
                  </span>
                  <span style={{ fontSize: '1.1rem', fontWeight: '600' }}>
                    {token.symbol || 'Unknown'}
                  </span>
                </div>
                <div style={{ fontSize: '1.1rem', fontWeight: '700', color: '#3b82f6' }}>
                  {token.whale_count} whales
                </div>
              </div>

              <div className="address" style={{ marginBottom: '10px' }}>
                {token.token_address}
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>Price</div>
                  <div style={{ fontSize: '0.9rem' }}>
                    ${token.price_usd ? token.price_usd.toFixed(8) : 'N/A'}
                  </div>
                </div>
                <div>
                  <div style={{ fontSize: '0.75rem', color: '#9ca3af' }}>24h Volume</div>
                  <div style={{ fontSize: '0.9rem' }}>
                    ${token.total_volume_24h ? token.total_volume_24h.toLocaleString(undefined, { maximumFractionDigits: 0 }) : 'N/A'}
                  </div>
                </div>
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  )
}

export default TrendingTokens
