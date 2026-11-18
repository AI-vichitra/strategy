'use client';
import { useState, useEffect } from 'react';
import { connectors, getLogoUrl, type Connector, type ConnectorStatus } from '../../data/connectors';
import ConnectorModal from './ConnectorModal';
import styles from './ConnectorsPanel.module.css';

interface ConnectorsPanelProps {
  open: boolean;
  onClose: () => void;
  agentConnectors?: string[];  // when set, only show these connector names
  agentName?: string;          // agent display name for the header
}

function ConnectorCard({
  connector,
  status,
  onConnect,
}: {
  connector: Connector;
  status: ConnectorStatus;
  onConnect: () => void;
}) {
  const [imgError, setImgError] = useState(false);

  return (
    <div className={styles.card}>
      <div className={styles.cardLeft}>
        <div className={styles.iconWrapper}>
          {!imgError ? (
            <img 
              src={getLogoUrl(connector.domain)} 
              alt={`${connector.name} logo`} 
              className={styles.iconImage}
              onError={() => setImgError(true)}
            />
          ) : (
            <span className={styles.fallbackIcon}>{connector.name.charAt(0)}</span>
          )}
        </div>
        <div className={styles.textStack}>
          <span className={styles.cardTitle}>{connector.name}</span>
          <span className={styles.cardDesc}>{connector.description}</span>
        </div>
      </div>
      <div className={styles.cardRight}>
        {status === 'connected' && (
          <span className={styles.badgeGreen}>Connected</span>
        )}
        {status === 'error' && (
          <span className={styles.badgeRed}>Error</span>
        )}
        <button
          className={status === 'connected' ? styles.manageBtn : styles.connectBtn}
          onClick={onConnect}
        >
          {status === 'connected' ? 'Manage' : 'Connect'}
        </button>
      </div>
    </div>
  );
}

function authHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export default function ConnectorsPanel({ open, onClose, agentConnectors, agentName }: ConnectorsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [modalConnector, setModalConnector] = useState<Connector | null>(null);
  const [statuses, setStatuses] = useState<Record<string, ConnectorStatus>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // When agent is selected, filter to only its required connectors (preserving order from agent definition)
  const isFiltered = agentConnectors && agentConnectors.length > 0;

  const getStatus = (id: string): ConnectorStatus => statuses[id] || 'not_connected';

  useEffect(() => {
    if (!open) return;
    let cancelled = false;
    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';

    setLoading(true);
    setError(null);
    fetch(`${apiBase}/api/connectors`, { headers: authHeaders() })
      .then((res) => {
        if (!res.ok) throw new Error(`Failed to load connectors (${res.status})`);
        return res.json();
      })
      .then((rows: Array<{ connector_id: string }>) => {
        if (cancelled) return;
        const connected = new Set(rows.map((r) => r.connector_id.toLowerCase()));
        const next: Record<string, ConnectorStatus> = {};
        connectors.forEach((c) => {
          next[c.id] = connected.has(c.id.toLowerCase()) ? 'connected' : 'not_connected';
        });
        setStatuses(next);
      })
      .catch((e) => {
        if (!cancelled) setError(e instanceof Error ? e.message : 'Failed to load connectors');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [open]);

  const handleConnect = (connectorId: string) => {
    setStatuses((prev) => ({ ...prev, [connectorId]: 'connected' }));
    setModalConnector(null);
  };

  const handleDisconnect = async (connectorId: string) => {
    setError(null);
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const res = await fetch(`${apiBase}/api/connectors/${connectorId}`, {
        method: 'DELETE',
        headers: authHeaders(),
      });
      if (!res.ok && res.status !== 404) {
        throw new Error(`Failed to disconnect (${res.status})`);
      }
      setStatuses((prev) => ({ ...prev, [connectorId]: 'not_connected' }));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to disconnect');
    } finally {
      setModalConnector(null);
    }
  };

  // Reset expanded when panel closes or if it becomes filtered
  useEffect(() => {
    if (!open || isFiltered) setExpanded(false);
  }, [open, isFiltered]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'auto';
    }
    return () => { document.body.style.overflow = 'auto'; };
  }, [open]);

  const displayedConnectors = isFiltered
    ? agentConnectors
        .map(name => connectors.find(c => c.name === name))
        .filter((c): c is Connector => !!c)
    : connectors;

  // Split into two columns (only if not filtered)
  const col1 = isFiltered ? displayedConnectors : displayedConnectors.slice(0, Math.ceil(displayedConnectors.length / 2));
  const col2 = isFiltered ? [] : displayedConnectors.slice(Math.ceil(displayedConnectors.length / 2));

  return (
    <>
      <div 
        className={`${styles.overlay} ${open ? styles.overlayOpen : ''}`} 
        onClick={onClose}
      />
      <div className={`${styles.panel} ${open ? styles.panelOpen : ''} ${(expanded && !isFiltered) ? styles.panelExpanded : ''}`}>
        <div className={styles.header}>
          <div>
            <h2 className={styles.headerTitle}>Connectors</h2>
            {isFiltered && agentName && (
              <p style={{ fontSize: '11px', color: 'var(--text-tertiary, #888)', margin: '2px 0 0', fontWeight: 500 }}>
                Required for {agentName}
              </p>
            )}
          </div>
          <div className={styles.headerActions}>
            {!isFiltered && (
              <button 
                className={`${styles.expandBtn} ${expanded ? styles.expandBtnActive : ''}`}
                onClick={() => setExpanded(prev => !prev)}
                aria-label={expanded ? 'Collapse' : 'Expand'}
                title={expanded ? 'Show less' : 'Show more'}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  {expanded ? (
                    <><polyline points="11 17 6 12 11 7"/><polyline points="18 17 13 12 18 7"/></>
                  ) : (
                    <><polyline points="13 17 18 12 13 7"/><polyline points="6 17 11 12 6 7"/></>
                  )}
                </svg>
              </button>
            )}
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
        <div className={styles.scrollArea}>
          {loading && (
            <p style={{ fontSize: '12px', color: 'var(--text-tertiary, #888)', margin: '0 0 16px' }}>
              Loading connectors...
            </p>
          )}
          {error && (
            <p style={{ fontSize: '12px', color: '#dc2626', margin: '0 0 16px' }}>
              {error}
            </p>
          )}
          <div className={styles.columns}>
            <div className={styles.column}>
              {col1.map(conn => (
                <ConnectorCard
                  key={conn.id}
                  connector={conn}
                  status={getStatus(conn.id)}
                  onConnect={() => setModalConnector(conn)}
                />
              ))}
            </div>
            {expanded && (
              <div className={`${styles.column} ${styles.columnTwo}`}>
                {col2.map(conn => (
                  <ConnectorCard
                    key={conn.id}
                    connector={conn}
                    status={getStatus(conn.id)}
                    onConnect={() => setModalConnector(conn)}
                  />
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Connector Modal */}
      {modalConnector && (
        <ConnectorModal
          connector={modalConnector}
          status={getStatus(modalConnector.id)}
          onClose={() => setModalConnector(null)}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      )}
    </>
  );
}
