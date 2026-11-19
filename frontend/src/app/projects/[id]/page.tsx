'use client';
import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import Link from 'next/link';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import styles from './page.module.css';

interface BrandDetail {
  name: string;
  website_url: string | null;
  category: string;
  region: string | null;
  brand_context: string | null;
  logo_url: string | null;
  colors: { primary?: string; secondary?: string; accent?: string } | null;
}

interface CompetitorItem {
  name: string;
  website_url: string;
}

interface ChatItem {
  id: string;
  title: string;
  created_at: string | null;
  last_message_at: string | null;
  message_count: number;
}

interface ProjectDetails {
  brand_config_id: string;
  brand: BrandDetail;
  competitors_selected: CompetitorItem[];
  competitors_used: CompetitorItem[];
  chats: ChatItem[];
  status: string;
  created_at: string | null;
  last_updated: string | null;
}

function statusClass(status: string) {
  if (status === 'complete') return styles.statusComplete;
  if (status === 'running') return styles.statusRunning;
  if (status === 'failed') return styles.statusFailed;
  return styles.statusPending;
}

function statusLabel(status: string) {
  if (status === 'complete') return 'Complete';
  if (status === 'running') return 'Running';
  if (status === 'failed') return 'Failed';
  return 'Pending';
}

function formatDate(iso: string | null) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
  } catch {
    return iso;
  }
}

function normalize(name: string) {
  return name.toLowerCase().replace(/[^a-z0-9]/g, '');
}

export default function ProjectDetailsPage() {
  const params = useParams();
  const router = useRouter();
  const projectId = params?.id as string;
  const [data, setData] = useState<ProjectDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    fetch(`${apiBase}/api/projects/${projectId}/details`, { headers })
      .then(res => {
        if (!res.ok) throw new Error(res.status === 404 ? 'Project not found.' : `Error ${res.status}`);
        return res.json();
      })
      .then(setData)
      .catch(e => setError(e.message))
      .finally(() => setLoading(false));
  }, [projectId]);

  const handleOpenChat = (chatId: string, brandConfigId: string) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('brand_config_id', brandConfigId);
    }
    router.push(`/build?project=${chatId}`);
  };

  if (loading) {
    return <div className={styles.loadingWrap}>Loading project details…</div>;
  }

  if (error || !data) {
    return (
      <div className={styles.errorWrap}>
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#D4A843" strokeWidth="1.5">
          <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><circle cx="12" cy="16" r="1" fill="#D4A843"/>
        </svg>
        <p>{error ?? 'Project not found.'}</p>
        <Link href="/build" className={styles.backLink}>← Back to projects</Link>
      </div>
    );
  }

  const { brand_config_id, brand, competitors_selected, competitors_used, chats, status, created_at, last_updated } = data;
  const apiBase = process.env.NEXT_PUBLIC_API_URL;

  // Diff: which used competitors were NOT in the selected set?
  const selectedNorm = new Set(competitors_selected.map(c => normalize(c.name)));
  const extraUsed = competitors_used.filter(c => !selectedNorm.has(normalize(c.name)));
  const missingFromUsed = competitors_selected.filter(c => !competitors_used.some(u => normalize(u.name) === normalize(c.name)));
  const hasDiff = extraUsed.length > 0 || missingFromUsed.length > 0;

  // Single merged competitor list keyed by selected list; augment with used status
  const compList = competitors_selected.map(sel => ({
    ...sel,
    inKB: competitors_used.some(u => normalize(u.name) === normalize(sel.name)),
  }));

  return (
    <main className={styles.container}>
      <div className={styles.inner}>
        {/* Back */}
        <Link href="/build" className={styles.backLink}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
          </svg>
          Back to projects
        </Link>

        {/* Header */}
        <div>
          <h1 className={styles.pageTitle}>{brand.name}</h1>
          <div className={styles.statusRow}>
            <span className={`${styles.statusBadge} ${statusClass(status)}`}>
              {statusLabel(status)}
            </span>
            {created_at && <span className={styles.metaDate}>Created {formatDate(created_at)}</span>}
            {last_updated && last_updated !== created_at && (
              <span className={styles.metaDate}>· Updated {formatDate(last_updated)}</span>
            )}
          </div>
        </div>

        {/* Brand */}
        <div className={styles.card}>
          <div className={styles.sectionTitle}>Brand</div>
          <div className={styles.divider} />

          {(brand.logo_url || brand.colors) && (
            <div className={styles.logoRow} style={{ marginBottom: 20 }}>
              {brand.logo_url && (
                <img
                  src={brand.logo_url.startsWith('/') ? `${apiBase}${brand.logo_url}` : brand.logo_url}
                  alt="Brand logo"
                  className={styles.logoImg}
                />
              )}
              {brand.colors && (
                <div>
                  <div className={styles.fieldLabel} style={{ marginBottom: 8 }}>Colors</div>
                  <div className={styles.swatchRow}>
                    {brand.colors.primary && (
                      <div className={styles.swatch}>
                        <div className={styles.swatchDot} style={{ background: brand.colors.primary }} />
                        <span className={styles.swatchLabel}>Primary</span>
                      </div>
                    )}
                    {brand.colors.secondary && (
                      <div className={styles.swatch}>
                        <div className={styles.swatchDot} style={{ background: brand.colors.secondary }} />
                        <span className={styles.swatchLabel}>Secondary</span>
                      </div>
                    )}
                    {brand.colors.accent && (
                      <div className={styles.swatch}>
                        <div className={styles.swatchDot} style={{ background: brand.colors.accent }} />
                        <span className={styles.swatchLabel}>Accent</span>
                      </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}

          <div className={styles.brandGrid}>
            <div className={styles.field}>
              <span className={styles.fieldLabel}>Website</span>
              {brand.website_url
                ? <a href={brand.website_url} target="_blank" rel="noopener noreferrer" className={styles.fieldLink}>{brand.website_url}</a>
                : <span className={styles.fieldEmpty}>—</span>}
            </div>
            <div className={styles.field}>
              <span className={styles.fieldLabel}>Category</span>
              <span className={styles.fieldValue}>{brand.category || '—'}</span>
            </div>
            {brand.region && (
              <div className={styles.field}>
                <span className={styles.fieldLabel}>Target Market</span>
                <span className={styles.fieldValue}>{brand.region}</span>
              </div>
            )}
          </div>
        </div>

        {/* Brand Context */}
        {brand.brand_context && (
          <div className={styles.card}>
            <div className={styles.sectionTitle}>Brand Context</div>
            <div className={styles.divider} />
            <div className={styles.contextMarkdown}>
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {brand.brand_context}
              </ReactMarkdown>
            </div>
          </div>
        )}

        {/* Competitors */}
        <div className={styles.card}>
          <div className={styles.sectionTitle}>
            Competitors ({competitors_selected.length})
          </div>
          <div className={styles.divider} />

          {hasDiff && (
            <div className={styles.amberNotice}>
              <svg className={styles.amberIcon} width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"/>
                <line x1="12" y1="9" x2="12" y2="13"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
              <div>
                <span className={styles.amberText}>Report used competitors that differ from your selection.</span>
                {extraUsed.length > 0 && (
                  <span className={styles.amberText}> Extra in KB: {extraUsed.map(c => c.name).join(', ')}.</span>
                )}
                {missingFromUsed.length > 0 && (
                  <span className={styles.amberText}> Missing from KB: {missingFromUsed.map(c => c.name).join(', ')}.</span>
                )}
              </div>
            </div>
          )}

          {compList.length === 0 ? (
            <p className={styles.emptyList}>No competitors recorded.</p>
          ) : (
            <div className={styles.compList}>
              {compList.map((c, i) => (
                <div key={i} className={`${styles.compRow} ${!c.inKB && status === 'complete' ? styles.compRowMissing : ''}`}>
                  <div className={styles.compDot} />
                  <span className={styles.compName}>{c.name}</span>
                  {c.website_url && <span className={styles.compUrl}>{c.website_url}</span>}
                  {!c.inKB && status === 'complete' && (
                    <span className={styles.compBadgeMissing}>Not in KB</span>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Chats */}
        <div className={styles.card}>
          <div className={styles.sectionTitle}>
            Chats in this project ({chats.length})
          </div>
          <div className={styles.divider} />

          {chats.length === 0 ? (
            <p className={styles.emptyList}>No chats yet for this project.</p>
          ) : (
            <div className={styles.chatList}>
              {chats.map(chat => (
                <button
                  key={chat.id}
                  type="button"
                  className={styles.chatRow}
                  onClick={() => handleOpenChat(chat.id, brand_config_id)}
                >
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.chatIcon}>
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
                  </svg>
                  <span className={styles.chatTitle}>{chat.title}</span>
                  <span className={styles.chatMeta}>
                    {chat.message_count > 0 ? `${chat.message_count} message${chat.message_count === 1 ? '' : 's'}` : 'No messages'}
                  </span>
                  <span className={styles.chatDate}>{formatDate(chat.last_message_at || chat.created_at)}</span>
                  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.chatArrow}>
                    <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                  </svg>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
