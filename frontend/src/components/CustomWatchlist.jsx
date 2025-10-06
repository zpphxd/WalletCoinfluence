import React, { useState, useEffect } from 'react'
import axios from 'axios'

const API_BASE = 'http://localhost:8000'

function CustomWatchlist() {
  const [wallets, setWallets] = useState([])
  const [loading, setLoading] = useState(true)
  const [showAddForm, setShowAddForm] = useState(false)
  const [formData, setFormData] = useState({
    address: '',
    chain_id: 'ethereum',
    label: '',
    notes: ''
  })

  // Classify whale by tier based on notes
  const getWhaleTier = (wallet) => {
    const notes = wallet.notes || ''
    if (notes.includes('$17.4M') || notes.includes('579%') || notes.includes('$14.8M') || notes.includes('$12M')) {
      return { tier: 1, label: 'TIER 1: MEGA', color: '#10b981', emoji: '🐋' }
    } else if (notes.includes('$7.2M') || notes.includes('$489k') || notes.includes('2345 trades')) {
      return { tier: 2, label: 'TIER 2: STRONG', color: '#3b82f6', emoji: '🐬' }
    } else if (notes.includes('$29k') || notes.includes('$21k') || notes.includes('$14k')) {
      return { tier: 3, label: 'TIER 3: LEARNING', color: '#6b7280', emoji: '🐟' }
    }
    return { tier: 0, label: 'CUSTOM', color: '#9ca3af', emoji: '📍' }
  }

  useEffect(() => {
    loadWallets()
  }, [])

  const loadWallets = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/watchlist`)
      // Sort by tier (1 first, then 2, then 3)
      const sorted = response.data.sort((a, b) => {
        const tierA = getWhaleTier(a).tier
        const tierB = getWhaleTier(b).tier
        if (tierA === 0) return 1  // Custom to end
        if (tierB === 0) return -1
        return tierA - tierB  // 1, 2, 3
      })
      setWallets(sorted)
    } catch (err) {
      console.error('Failed to load watchlist:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    try {
      await axios.post(`${API_BASE}/api/watchlist`, formData)
      setFormData({ address: '', chain_id: 'ethereum', label: '', notes: '' })
      setShowAddForm(false)
      loadWallets()
    } catch (err) {
      alert('Failed to add wallet: ' + err.message)
    }
  }

  const handleRemove = async (address, chain_id) => {
    if (!confirm(`Remove ${address} from watchlist?`)) return

    try {
      await axios.delete(`${API_BASE}/api/watchlist/${address}?chain_id=${chain_id}`)
      loadWallets()
    } catch (err) {
      alert('Failed to remove wallet: ' + err.message)
    }
  }

  if (loading) return <div className="loading">Loading custom watchlist...</div>

  return (
    <div>
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h2>Custom Watchlist ({wallets.length})</h2>
          <button className="btn" onClick={() => setShowAddForm(!showAddForm)}>
            {showAddForm ? 'Cancel' : '+ Add Wallet'}
          </button>
        </div>

        {showAddForm && (
          <form onSubmit={handleSubmit} style={{ marginBottom: '24px', padding: '20px', background: 'var(--bg-secondary)', borderRadius: '8px', border: '1px solid var(--border-light)' }}>
            <div className="form-group">
              <label>Wallet Address *</label>
              <input
                type="text"
                placeholder="0x... or Solana address"
                value={formData.address}
                onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                required
              />
            </div>

            <div className="form-group">
              <label>Chain</label>
              <select
                value={formData.chain_id}
                onChange={(e) => setFormData({ ...formData, chain_id: e.target.value })}
                style={{ width: '100%', padding: '10px', background: 'var(--bg-card)', border: '1px solid var(--border-light)', borderRadius: '6px' }}
              >
                <option value="ethereum">Ethereum</option>
                <option value="base">Base</option>
                <option value="arbitrum">Arbitrum</option>
                <option value="solana">Solana</option>
              </select>
            </div>

            <div className="form-group">
              <label>Label (optional)</label>
              <input
                type="text"
                placeholder="e.g., 'Top meme whale'"
                value={formData.label}
                onChange={(e) => setFormData({ ...formData, label: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label>Notes (optional)</label>
              <textarea
                placeholder="Any notes about this wallet..."
                value={formData.notes}
                onChange={(e) => setFormData({ ...formData, notes: e.target.value })}
                rows="3"
              />
            </div>

            <button type="submit" className="btn">Add to Watchlist</button>
          </form>
        )}

        <div className="whale-list">
          {wallets.length === 0 ? (
            <p style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '40px' }}>
              No custom wallets yet. Add your first whale to track!
            </p>
          ) : (
            wallets.map((wallet) => {
              const tierInfo = getWhaleTier(wallet)

              return (
                <div key={wallet.address} className="whale-item">
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                    <div style={{ flex: 1 }}>
                      {/* Tier Badge */}
                      <div style={{
                        display: 'inline-block',
                        padding: '4px 10px',
                        background: tierInfo.color,
                        color: '#ffffff',
                        borderRadius: '4px',
                        fontSize: '0.7rem',
                        fontWeight: '700',
                        letterSpacing: '0.5px',
                        marginBottom: '8px'
                      }}>
                        {tierInfo.emoji} {tierInfo.label}
                      </div>

                      <div style={{ fontSize: '1.1rem', fontWeight: '600', marginBottom: '6px' }}>
                        {wallet.label || 'Unlabeled Wallet'}
                      </div>
                      <div className="address" style={{ marginBottom: '8px' }}>
                        {wallet.address}
                      </div>
                      <div style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        Chain: {wallet.chain_id} • Added: {new Date(wallet.added_at).toLocaleDateString()}
                      </div>
                      {wallet.notes && (
                        <div style={{
                          marginTop: '12px',
                          padding: '12px',
                          background: 'var(--bg-secondary)',
                          borderRadius: '6px',
                          fontSize: '0.85rem',
                          color: 'var(--text-secondary)',
                          whiteSpace: 'pre-line',
                          lineHeight: '1.5'
                        }}>
                          {wallet.notes}
                        </div>
                      )}
                    </div>
                    <button
                      className="btn"
                      onClick={() => handleRemove(wallet.address, wallet.chain_id)}
                      style={{
                        marginLeft: '12px',
                        background: 'transparent',
                        color: 'var(--text-muted)',
                        border: '1px solid var(--border-light)',
                        fontSize: '0.85rem'
                      }}
                    >
                      Remove
                    </button>
                  </div>

                  {wallet.stats && (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '12px', marginTop: '12px', padding: '12px', background: 'var(--bg-secondary)', borderRadius: '6px' }}>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Trades</div>
                        <div style={{ fontWeight: '600', fontSize: '1.1rem' }}>{wallet.stats.trades_count}</div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>P/L</div>
                        <div className={wallet.stats.unrealized_pnl_usd >= 0 ? 'positive' : 'negative'} style={{ fontWeight: '600', fontSize: '1.1rem' }}>
                          ${wallet.stats.unrealized_pnl_usd.toFixed(0)}
                        </div>
                      </div>
                      <div>
                        <div style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>Early Score</div>
                        <div style={{ fontWeight: '600', fontSize: '1.1rem' }}>
                          {wallet.stats.earlyscore_median ? wallet.stats.earlyscore_median.toFixed(1) : 'N/A'}
                        </div>
                      </div>
                    </div>
                  )}
                </div>
              )
            })
          )}
        </div>
      </div>
    </div>
  )
}

export default CustomWatchlist
