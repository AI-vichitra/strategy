'use client';
import { useState, useEffect } from 'react';
import { connectors, getLogoUrl, type Connector, type ConnectorStatus } from '../../data/connectors';
import ConnectorModal from './ConnectorModal';
import styles from './ConnectorsPanel.module.css';

interface ConnectorsPanelProps {
  open: boolean;
  onClose: () => void;
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

export default function ConnectorsPanel({ open, onClose }: ConnectorsPanelProps) {
  const [expanded, setExpanded] = useState(false);
  const [modalConnector, setModalConnector] = useState<Connector | null>(null);
  const [statuses, setStatuses] = useState<Record<string, ConnectorStatus>>({});

  const getStatus = (id: string): ConnectorStatus => statuses[id] || 'not_connected';

  const handleConnect = (connectorId: string) => {
    setStatuses((prev) => ({ ...prev, [connectorId]: 'connected' }));
    setModalConnector(null);
  };

  const handleDisconnect = (connectorId: string) => {
    setStatuses((prev) => ({ ...prev, [connectorId]: 'not_connected' }));
    setModalConnector(null);
  };

  // Reset expanded when panel closes
  useEffect(() => {
    if (!open) setExpanded(false);
  }, [open]);

  // Prevent body scroll when open
  useEffect(() => {
    if (open) {
      document.body.style.overflow = 'hidden';
    } else {
      document.body.style.overflow = 'auto';
    }
    return () => { document.body.style.overflow = 'auto'; };
  }, [open]);

  // Split connectors into two columns
  const half = Math.ceil(connectors.length / 2);
  const col1 = connectors.slice(0, half);
  const col2 = connectors.slice(half);

  return (
    <>
      <div 
        className={`${styles.overlay} ${open ? styles.overlayOpen : ''}`} 
        onClick={onClose}
      />
      <div className={`${styles.panel} ${open ? styles.panelOpen : ''} ${expanded ? styles.panelExpanded : ''}`}>
        <div className={styles.header}>
          <h2 className={styles.headerTitle}>Connectors</h2>
          <div className={styles.headerActions}>
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
            <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
              </svg>
            </button>
          </div>
        </div>
        <div className={styles.scrollArea}>
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
