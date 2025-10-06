import React, { useState, useEffect } from 'react'
import axios from 'axios'
import Dashboard from './components/Dashboard'
import PaperTrading from './components/PaperTrading'
import CustomWatchlist from './components/CustomWatchlist'
import TopWhales from './components/TopWhales'
import TrendingTokens from './components/TrendingTokens'

const API_BASE = 'http://localhost:8000'

function App() {
  const [stats, setStats] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [activeTab, setActiveTab] = useState('dashboard')

  useEffect(() => {
    loadStats()
    const interval = setInterval(loadStats, 30000) // Refresh every 30s
    return () => clearInterval(interval)
  }, [])

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/stats/overview`)
      setStats(response.data)
      setError(null)
    } catch (err) {
      setError('Failed to load stats: ' + err.message)
    } finally {
      setLoading(false)
    }
  }

  if (loading) {
    return <div className="loading">Loading Whale Pods...</div>
  }

  return (
    <div className="container">
      <header className="header">
        <h1>🐋 Whale Pods</h1>
        <p>Professional Whale Tracking & Trading Intelligence</p>
      </header>

      {error && <div className="error">{error}</div>}

      <div className="nav-tabs">
        <button
          className={`nav-tab ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => setActiveTab('dashboard')}
        >
          Overview
        </button>
        <button
          className={`nav-tab ${activeTab === 'paper-trading' ? 'active' : ''}`}
          onClick={() => setActiveTab('paper-trading')}
        >
          Portfolio
        </button>
        <button
          className={`nav-tab ${activeTab === 'whales' ? 'active' : ''}`}
          onClick={() => setActiveTab('whales')}
        >
          Top Performers
        </button>
        <button
          className={`nav-tab ${activeTab === 'trending' ? 'active' : ''}`}
          onClick={() => setActiveTab('trending')}
        >
          Market Trends
        </button>
        <button
          className={`nav-tab ${activeTab === 'watchlist' ? 'active' : ''}`}
          onClick={() => setActiveTab('watchlist')}
        >
          My Watchlist
        </button>
      </div>

      {activeTab === 'dashboard' && <Dashboard stats={stats} />}
      {activeTab === 'paper-trading' && <PaperTrading />}
      {activeTab === 'watchlist' && <CustomWatchlist />}
      {activeTab === 'whales' && <TopWhales />}
      {activeTab === 'trending' && <TrendingTokens />}
    </div>
  )
}

export default App
