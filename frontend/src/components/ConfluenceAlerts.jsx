import { useState, useEffect } from 'react';
import './ConfluenceAlerts.css';

function ConfluenceAlerts() {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const fetchAlerts = async () => {
    try {
      const response = await fetch('http://localhost:8000/api/alerts/recent?limit=50');
      if (!response.ok) throw new Error('Failed to fetch alerts');

      const data = await response.json();
      setAlerts(data.alerts);
      setError(null);
    } catch (err) {
      console.error('Error fetching alerts:', err);
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    // Initial fetch
    fetchAlerts();

    // Auto-refresh every 30 seconds
    const interval = setInterval(fetchAlerts, 30000);

    return () => clearInterval(interval);
  }, []);

  const formatTimestamp = (isoString) => {
    const date = new Date(isoString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    return `${diffDays}d ago`;
  };

  const getChainIcon = (chainId) => {
    const icons = {
      ethereum: '⟠',
      base: '🔵',
      arbitrum: '🔷',
      solana: '◎',
    };
    return icons[chainId] || '🔗';
  };

  if (loading) {
    return (
      <div className="confluence-alerts">
        <div className="alerts-header">
          <h2>🚨 Confluence Alerts</h2>
          <div className="live-indicator">
            <span className="pulse"></span>
            LIVE
          </div>
        </div>
        <div className="loading">Loading alerts...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="confluence-alerts">
        <div className="alerts-header">
          <h2>🚨 Confluence Alerts</h2>
        </div>
        <div className="error">Error: {error}</div>
      </div>
    );
  }

  return (
    <div className="confluence-alerts">
      <div className="alerts-header">
        <h2>🚨 Confluence Alerts</h2>
        <div className="live-indicator">
          <span className="pulse"></span>
          LIVE
        </div>
        <div className="alerts-count">{alerts.length} total</div>
      </div>

      {alerts.length === 0 ? (
        <div className="no-alerts">
          <p>No confluence alerts yet</p>
          <p className="hint">Alerts appear when 2+ whales buy the same token within 30 minutes</p>
        </div>
      ) : (
        <div className="alerts-list">
          {alerts.map((alert) => (
            <div key={alert.id} className="alert-card">
              <div className="alert-header">
                <div className="alert-time">
                  {formatTimestamp(alert.timestamp)}
                </div>
                <div className="alert-chain">
                  {getChainIcon(alert.chain_id)} {alert.chain_id}
                </div>
              </div>

              <div className="alert-main">
                <div className="token-info">
                  <div className="token-symbol">{alert.token_symbol}</div>
                  <div className="token-address">{alert.token_address}</div>
                  <div className="price-info">
                    {alert.token_price > 0 && (
                      <div className="current-price">
                        <span className="price-label">Current:</span>
                        <span className="price-value">${alert.token_price.toFixed(8)}</span>
                      </div>
                    )}
                    {alert.token_price_at_alert > 0 && alert.token_price !== alert.token_price_at_alert && (
                      <div className="alert-price">
                        <span className="price-label">At Alert:</span>
                        <span className="price-value">${alert.token_price_at_alert.toFixed(8)}</span>
                      </div>
                    )}
                  </div>
                </div>

                <div className="confluence-badge">
                  <span className="whale-count">{alert.whale_count}</span>
                  <span className="whale-text">WHALES</span>
                </div>
              </div>

              {alert.whales && alert.whales.length > 0 && (
                <div className="whale-list">
                  <div className="whale-list-header">
                    <span>Wallet</span>
                    <span>Purchase Amount</span>
                    <span>30D Performance</span>
                  </div>
                  {alert.whales.map((whale, idx) => (
                    <div key={idx} className="whale-item">
                      <div className="whale-address">{whale.address}</div>
                      <div className="whale-purchase">
                        {whale.purchase_amount_usd > 0 ? (
                          <span className="purchase-amount">${whale.purchase_amount_usd.toLocaleString()}</span>
                        ) : (
                          <span className="purchase-amount-unknown">-</span>
                        )}
                      </div>
                      <div className="whale-stats">
                        {whale.pnl_30d !== undefined && (
                          <span className={whale.pnl_30d > 0 ? 'profit' : 'loss'}>
                            ${whale.pnl_30d.toFixed(0)}
                          </span>
                        )}
                        {whale.best_trade > 0 && (
                          <span className="best-trade">
                            {whale.best_trade.toFixed(1)}x
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="alert-actions">
                <a
                  href={`https://dexscreener.com/${alert.chain_id}/${alert.token_address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="action-btn"
                >
                  📊 Chart
                </a>
                <a
                  href={`https://etherscan.io/token/${alert.token_address}`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="action-btn"
                >
                  🔍 Explorer
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

export default ConfluenceAlerts;
