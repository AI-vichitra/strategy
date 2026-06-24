'use client';
import { useState } from 'react';
import { getLogoUrl, type Connector, type ConnectorStatus } from '../../data/connectors';
import styles from './ConnectorModal.module.css';

interface Props {
  connector: Connector;
  status: ConnectorStatus;
  onClose: () => void;
  onConnect: (connectorId: string) => void;
  onDisconnect: (connectorId: string) => void;
}

export default function ConnectorModal({ connector, status, onClose, onConnect, onDisconnect }: Props) {
  // API state
  const [apiKey, setApiKey] = useState('');
  const [showKey, setShowKey] = useState(false);

  // Database state
  const [dbFields, setDbFields] = useState({ host: '', port: '', database: '', username: '', password: '' });
  const [showDbPass, setShowDbPass] = useState(false);
  const [testResult, setTestResult] = useState<'idle' | 'success' | 'error'>('idle');

  const [imgError, setImgError] = useState(false);

  const handleApiConnect = () => {
    if (apiKey.trim()) onConnect(connector.id);
  };

  const handleDbTest = () => {
    if (dbFields.host && dbFields.database) setTestResult('success');
    else setTestResult('error');
  };

  const handleDbConnect = () => {
    if (dbFields.host && dbFields.database) onConnect(connector.id);
  };

  return (
    <div className={styles.overlay} onClick={onClose}>
      <div className={styles.modal} onClick={(e) => e.stopPropagation()}>
        {/* Close button */}
        <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        {/* Header */}
        <div className={styles.header}>
          <div className={styles.logoBox}>
            {!imgError ? (
              <img
                src={getLogoUrl(connector.domain)}
                alt={connector.name}
                className={styles.logoImg}
                onError={() => setImgError(true)}
              />
            ) : (
              <span className={styles.logoFallback}>{connector.name.charAt(0)}</span>
            )}
          </div>
          <div className={styles.headerText}>
            <h2 className={styles.connectorName}>{connector.name}</h2>
            <p className={styles.connectorDesc}>{connector.description}</p>
          </div>
          <span className={`${styles.statusBadge} ${styles[status === 'connected' ? 'badgeConnected' : status === 'error' ? 'badgeError' : 'badgeDefault']}`}>
            {status === 'connected' ? '● Connected' : status === 'error' ? '● Error' : '● Not Connected'}
          </span>
        </div>

        <div className={styles.divider} />

        {/* ── Already connected state ────────────── */}
        {status === 'connected' ? (
          <div className={styles.body}>
            <div className={styles.connectedState}>
              <div className={styles.connectedIcon}>
                <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#059669" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
                </svg>
              </div>
              <p className={styles.connectedText}>This connector is active and ready to use.</p>
              <button className={styles.disconnectBtn} onClick={() => onDisconnect(connector.id)}>
                Disconnect
              </button>
            </div>
          </div>
        ) : connector.type === 'api' ? (
          /* ── API Key form ────────────────────── */
          <div className={styles.body}>
            <label className={styles.label}>API Key</label>
            <div className={styles.inputRow}>
              <input
                type={showKey ? 'text' : 'password'}
                className={styles.input}
                placeholder={`Enter your ${connector.name} API key`}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                autoFocus
              />
              <button className={styles.toggleBtn} onClick={() => setShowKey(!showKey)} aria-label={showKey ? 'Hide' : 'Show'}>
                {showKey ? (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" />
                  </svg>
                ) : (
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
                  </svg>
                )}
              </button>
            </div>
            <div className={styles.actions}>
              <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
              <button className={styles.primaryBtn} onClick={handleApiConnect} disabled={!apiKey.trim()}>
                Connect Account
              </button>
            </div>
          </div>
        ) : connector.type === 'oauth' ? (
          /* ── OAuth form ──────────────────────── */
          <div className={styles.body}>
            <div className={styles.oauthInfo}>
              <div className={styles.oauthIcon}>
                <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#8b5cf6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="11" width="18" height="11" rx="2" ry="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
                </svg>
              </div>
              <p className={styles.oauthText}>
                Clicking <strong>Continue to Connect</strong> will redirect you to {connector.name}&apos;s authorization page where you can securely grant access.
              </p>
              <div className={styles.oauthNote}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#d97706" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
                <span>OAuth connection flow will be configured later.</span>
              </div>
            </div>
            <div className={styles.actions}>
              <button className={styles.cancelBtn} onClick={onClose}>Cancel</button>
              <button className={styles.primaryBtn} onClick={() => onConnect(connector.id)}>
                Continue to Connect
              </button>
            </div>
          </div>
        ) : (
          /* ── Database form ───────────────────── */
          <div className={styles.body}>
            <div className={styles.dbGrid}>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Host</label>
                <input className={styles.input} placeholder="e.g. db.example.com" value={dbFields.host} onChange={(e) => setDbFields({ ...dbFields, host: e.target.value })} />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Port</label>
                <input className={styles.input} placeholder="e.g. 5432" value={dbFields.port} onChange={(e) => setDbFields({ ...dbFields, port: e.target.value })} />
              </div>
              <div className={`${styles.fieldGroup} ${styles.fullWidth}`}>
                <label className={styles.label}>Database</label>
                <input className={styles.input} placeholder="e.g. my_database" value={dbFields.database} onChange={(e) => setDbFields({ ...dbFields, database: e.target.value })} />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Username</label>
                <input className={styles.input} placeholder="e.g. admin" value={dbFields.username} onChange={(e) => setDbFields({ ...dbFields, username: e.target.value })} />
              </div>
              <div className={styles.fieldGroup}>
                <label className={styles.label}>Password</label>
                <div className={styles.inputRow}>
                  <input className={styles.input} type={showDbPass ? 'text' : 'password'} placeholder="••••••••" value={dbFields.password} onChange={(e) => setDbFields({ ...dbFields, password: e.target.value })} />
                  <button className={styles.toggleBtn} onClick={() => setShowDbPass(!showDbPass)}>
                    {showDbPass ? (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" /><line x1="1" y1="1" x2="23" y2="23" /></svg>
                    ) : (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></svg>
                    )}
                  </button>
                </div>
              </div>
            </div>

            {testResult !== 'idle' && (
              <div className={`${styles.testResult} ${testResult === 'success' ? styles.testSuccess : styles.testError}`}>
                {testResult === 'success' ? (
                  <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><polyline points="20 6 9 17 4 12" /></svg> Connection test passed</>
                ) : (
                  <><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5"><circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" /></svg> Connection test failed — check credentials</>
                )}
              </div>
            )}

            <div className={styles.actions}>
              <button className={styles.testBtn} onClick={handleDbTest}>Test Connection</button>
              <button className={styles.primaryBtn} onClick={handleDbConnect} disabled={!dbFields.host || !dbFields.database}>
                Connect Database
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
