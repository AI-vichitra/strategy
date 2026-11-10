'use client';
import { useEffect, useState } from 'react';
import { connectors, getLogoUrl, type Connector, type ConnectorStatus } from '../../data/connectors';
import ConnectorModal from './ConnectorModal';
import styles from './ConnectorsView.module.css';

// ── Category definitions with connector names ───────────
const categories = [
  {
    key: 'api',
    label: 'API Integrations',
    names: [
      'OpenAI API Key', 'Anthropic API Key', 'Google Gemini API Key',
      'Perplexity API Key', 'Firecrawl', 'Exa', 'SerpAPI', 'Ahrefs',
      'Semrush API Key', 'Hunter.io API Key', 'Findymail', 'ZoomInfo API Key',
      'Reddit', 'X', 'YouTube', 'Browserbase', 'Apify API Key', 'PhantomBuster API Key',
    ],
  },
  {
    key: 'regular',
    label: 'Regular Integrations',
    names: [
      'Google Search Console', 'Google Analytics', 'Google Ads', 'Bing Webmaster',
      'LinkedIn', 'Apollo', 'HubSpot', 'Salesforce', 'Attio', 'Pipedrive',
      'Freshsales', 'Salesloft', 'Zendesk', 'Freshdesk', 'Intercom',
      'Gmail', 'Microsoft', 'Outlook Calendar', 'Google Calendar', 'Google Meet',
      'Zoom', 'Slack', 'Microsoft Teams', 'Discord', 'Notion', 'Confluence',
      'Google Drive', 'Google Docs', 'Google Sheets', 'Microsoft Excel',
      'Microsoft Word', 'Airtable', 'ClickUp', 'Monday.com', 'Trello',
      'Asana', 'Jira', 'Linear', 'GitHub', 'GitLab', 'Tableau',
      'Google Looker', 'Sigma Computing', 'WordPress', 'Webflow', 'Canva',
      'Shopify', 'Greenhouse', 'Ashby', 'Gong', 'Google Forms',
      'Dropbox', 'Box', 'Calendly', 'Cal.com',
    ],
  },
  {
    key: 'mcp',
    label: 'MCP / Data / Infrastructure',
    names: [
      'PostgreSQL', 'BigQuery', 'Snowflake', 'Databricks', 'ClickHouse',
      'Google Cloud Storage', 'Supabase', 'Firebase', 'NetSuite',
      'Snowflake PAT', 'Google Apps Script', 'AWS Credentials',
    ],
  },
];

const tabLabels = [{ key: 'all', label: 'All' }, ...categories.map((c) => ({ key: c.key, label: c.label }))];

// Build a map: connector name → Connector object
const connectorMap = new Map(connectors.map((c) => [c.name, c]));

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
        {status !== 'not_connected' && (
          <span className={`${styles.badge} ${status === 'connected' ? styles.badgeGreen : styles.badgeRed}`}>
            {status === 'connected' ? 'Connected' : 'Error'}
          </span>
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

export default function ConnectorsView() {
  const [search, setSearch] = useState('');
  const [activeTab, setActiveTab] = useState('all');
  const [modalConnector, setModalConnector] = useState<Connector | null>(null);
  const [statuses, setStatuses] = useState<Record<string, ConnectorStatus>>({});
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const getStatus = (id: string): ConnectorStatus => statuses[id] || 'not_connected';

  useEffect(() => {
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
  }, []);

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

  const catConnectors = activeTab === 'all'
    ? connectors
    : (categories.find((c) => c.key === activeTab)!.names
        .map((name) => connectorMap.get(name))
        .filter(Boolean) as Connector[]);

  const filtered = search
    ? catConnectors.filter(
        (c) =>
          c.name.toLowerCase().includes(search.toLowerCase()) ||
          c.description.toLowerCase().includes(search.toLowerCase())
      )
    : catConnectors;

  return (
    <div className={styles.wrapper}>
      {/* Header */}
      <div className={styles.header}>
        <h1 className={styles.title}>Connectors Available</h1>
        <p className={styles.subtitle}>Select the connector you would like to authenticate with.</p>
        {loading && (
          <p style={{ fontSize: '12px', color: 'var(--text-tertiary, #888)', margin: '8px 0 0' }}>
            Loading connectors...
          </p>
        )}
        {error && (
          <p style={{ fontSize: '12px', color: '#dc2626', margin: '8px 0 0' }}>
            {error}
          </p>
        )}
      </div>

      {/* Search + Tabs row */}
      <div className={styles.controlsRow}>
        <div className={styles.searchBox}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <input
            type="text"
            placeholder="Search for a connector"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
        <div className={styles.tabs}>
          {tabLabels.map((tab) => (
            <button
              key={tab.key}
              className={`${styles.tab} ${activeTab === tab.key ? styles.tabActive : ''}`}
              onClick={() => { setActiveTab(tab.key); setSearch(''); }}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* List */}
      <div className={styles.list}>
        {filtered.map((conn) => (
          <ConnectorCard
            key={conn.id}
            connector={conn}
            status={getStatus(conn.id)}
            onConnect={() => setModalConnector(conn)}
          />
        ))}
        {filtered.length === 0 && (
          <div className={styles.emptyState}>
            No connectors match &ldquo;{search}&rdquo;
          </div>
        )}
      </div>

      {/* Modal */}
      {modalConnector && (
        <ConnectorModal
          connector={modalConnector}
          status={getStatus(modalConnector.id)}
          onClose={() => setModalConnector(null)}
          onConnect={handleConnect}
          onDisconnect={handleDisconnect}
        />
      )}
    </div>
  );
}
