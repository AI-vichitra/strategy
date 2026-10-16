'use client';

import { useState, useEffect, useMemo, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import rehypeRaw from 'rehype-raw';
import { exportReportToPdf } from '../../utils/pdfExport';
import styles from './FilesView.module.css';

interface GeneratedFile {
  id: string;
  projectId: string;
  name: string;
  brandName: string;
  agentName: string;
  content: string;
  type: 'pdf' | 'csv' | 'docx' | 'html';
  size: string;
  date: string;
  description: string;
  category: string;
  shared: boolean;
  gradient: string;
}

const GRADIENTS = [
  'linear-gradient(135deg, #2D2A26 0%, #D4A843 100%)',
  'linear-gradient(135deg, #1E293B 0%, #6366F1 100%)',
  'linear-gradient(135deg, #064E3B 0%, #10B981 100%)',
  'linear-gradient(135deg, #4C1D95 0%, #A855F7 100%)',
  'linear-gradient(135deg, #7C2D12 0%, #F59E0B 100%)',
];

export default function FilesView() {
  const [activeTab, setActiveTab] = useState<'all' | 'mine' | 'shared'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'recent' | 'name' | 'size'>('recent');
  const [files, setFiles] = useState<GeneratedFile[]>([]);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [activeExportFile, setActiveExportFile] = useState<GeneratedFile | null>(null);
  const hiddenRenderRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const fetchGeneratedReports = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const [projRes, brandsRes] = await Promise.all([
          fetch(`${apiBase}/api/projects/`, { headers }),
          fetch(`${apiBase}/api/brands/`, { headers }),
        ]);

        if (!projRes.ok) return;
        const projects = await projRes.json();
        const brands = brandsRes.ok ? await brandsRes.json() : [];
        const brandMap: Record<string, string> = {};
        (brands || []).forEach((b: any) => {
          brandMap[b.id] = b.brand_name;
        });

        const extracted: GeneratedFile[] = [];
        (projects || []).forEach((proj: any, pIdx: number) => {
          const assistantMsgs = (proj.messages || []).filter((m: any) => m.role === 'assistant' && m.content?.trim());
          assistantMsgs.forEach((msg: any, mIdx: number) => {
            const brandName = brandMap[proj.brand_config_id] || proj.title || 'Brand';
            const agentName = proj.agent_type || 'StratAI';
            const headerMatch = msg.content.match(/^#+\s*(.+)$/m);
            const rawTitle = headerMatch
              ? headerMatch[1].replace(/[*_`]/g, '').trim()
              : `${brandName} - ${agentName} Report`;

            const plainPreview = msg.content
              .replace(/```[\s\S]*?```/g, '')
              .replace(/[#*_>`~|-]/g, ' ')
              .replace(/\s+/g, ' ')
              .trim()
              .slice(0, 140);

            const byteSize = new Blob([msg.content]).size;
            const kbSize = Math.max(12, Math.round((byteSize * 3.2) / 1024)); // estimated PDF size

            const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
            const fileName = `${sanitize(brandName)}_${sanitize(agentName)}.pdf`;

            extracted.push({
              id: `${proj.id}-${msg.id || mIdx}`,
              projectId: proj.id,
              name: fileName,
              brandName,
              agentName,
              content: msg.content,
              type: 'pdf',
              size: `${kbSize} KB`,
              date: msg.created_at || proj.created_at || new Date().toISOString(),
              description: plainPreview ? `${plainPreview}...` : `Generated ${agentName} strategic report for ${brandName}.`,
              category: agentName,
              shared: false,
              gradient: GRADIENTS[(pIdx + mIdx) % GRADIENTS.length],
            });
          });
        });

        setFiles(extracted);
      } catch (err) {
        console.error('Failed to load generated files:', err);
      }
    };

    fetchGeneratedReports();
  }, []);

  const handleDownloadFile = async (file: GeneratedFile) => {
    try {
      setDownloadingId(file.id);
      setActiveExportFile(file);

      // Wait a tick for hidden ReactMarkdown container to render
      await new Promise((resolve) => setTimeout(resolve, 150));

      if (hiddenRenderRef.current) {
        await exportReportToPdf({
          element: hiddenRenderRef.current,
          reportTitle: file.name.replace(/\.pdf$/i, ''),
          brandName: file.brandName,
          agentName: file.agentName,
          fileName: file.name.replace(/[^a-zA-Z0-9_.-]/g, '_'),
        });
      }
    } catch (err) {
      console.error('Failed to download report PDF:', err);
    } finally {
      setDownloadingId(null);
      setActiveExportFile(null);
    }
  };

  const handleOpenInChat = (file: GeneratedFile) => {
    window.dispatchEvent(
      new CustomEvent('openProject', {
        detail: { projectId: file.projectId },
      })
    );
  };

  // Filtered files
  const filteredFiles = useMemo(() => {
    return files
      .filter((file) => {
        if (activeTab === 'mine' && file.shared) return false;
        if (activeTab === 'shared' && !file.shared) return false;

        const matchQuery =
          file.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
          file.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
          file.category.toLowerCase().includes(searchQuery.toLowerCase()) ||
          file.brandName.toLowerCase().includes(searchQuery.toLowerCase());
        return matchQuery;
      })
      .sort((a, b) => {
        if (sortBy === 'name') {
          return a.name.localeCompare(b.name);
        }
        if (sortBy === 'size') {
          const sizeA = parseFloat(a.size);
          const sizeB = parseFloat(b.size);
          return sizeB - sizeA;
        }
        return new Date(b.date).getTime() - new Date(a.date).getTime();
      });
  }, [files, activeTab, searchQuery, sortBy]);

  const getFileIcon = (type: GeneratedFile['type']) => {
    switch (type) {
      case 'pdf':
        return (
          <svg className={styles.fileIcon} viewBox="0 0 24 24" fill="none" stroke="#ef4444" strokeWidth="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="9" y1="15" x2="15" y2="15" />
          </svg>
        );
      default:
        return (
          <svg className={styles.fileIcon} viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <polyline points="8 17 12 13 16 17" />
          </svg>
        );
    }
  };

  return (
    <div className={styles.container}>
      <div className={styles.header}>
        <div className={styles.titleWrapper}>
          <h2 className={styles.title}>Files</h2>
          <span className={styles.badge}>{filteredFiles.length} items</span>
        </div>
        <p className={styles.subtitle}>Browse and download strategic PDF reports generated for your brands.</p>
      </div>

      {/* Toolbar */}
      <div className={styles.toolbar}>
        <div className={styles.tabGroup}>
          <button
            className={`${styles.tabBtn} ${activeTab === 'all' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('all')}
          >
            All
          </button>
          <button
            className={`${styles.tabBtn} ${activeTab === 'mine' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('mine')}
          >
            Mine
          </button>
          <button
            className={`${styles.tabBtn} ${activeTab === 'shared' ? styles.tabActive : ''}`}
            onClick={() => setActiveTab('shared')}
          >
            Shared with me
          </button>
        </div>

        <div className={styles.actions}>
          <div className={styles.searchBox}>
            <svg className={styles.searchIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search reports..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className={styles.clearSearch} onClick={() => setSearchQuery('')}>×</button>
            )}
          </div>

          <div className={styles.sortWrapper}>
            <select
              className={styles.sortSelect}
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value as any)}
            >
              <option value="recent">Recent First</option>
              <option value="name">Alphabetical</option>
              <option value="size">Size (Large to Small)</option>
            </select>
          </div>
        </div>
      </div>

      {/* Files Grid */}
      {filteredFiles.length > 0 ? (
        <div className={styles.grid}>
          {filteredFiles.map((file) => (
            <div key={file.id} className={styles.card}>
              <div
                className={styles.thumbnail}
                style={{ background: file.gradient, cursor: 'pointer' }}
                onClick={() => handleOpenInChat(file)}
              >
                <div className={styles.thumbnailOverlay} />
                <div className={styles.typeBadge}>{file.type.toUpperCase()}</div>
                <div className={styles.thumbnailContent}>
                  <div className={styles.previewTag}>{file.brandName} &bull; {file.category}</div>
                  <h4 className={styles.previewName}>{file.name}</h4>
                </div>
              </div>

              <div className={styles.details}>
                <div className={styles.detailsHeader}>
                  <div className={styles.fileIconWrapper}>
                    {getFileIcon(file.type)}
                  </div>
                  <div className={styles.fileInfo}>
                    <h3 className={styles.fileName} title={file.name}>{file.name}</h3>
                    <div className={styles.fileMetadata}>
                      <span>{file.size}</span>
                      <span className={styles.bullet}>•</span>
                      <span>{new Date(file.date).toLocaleDateString()}</span>
                    </div>
                  </div>
                </div>

                <p className={styles.description}>{file.description}</p>

                <div className={styles.cardActions}>
                  <button
                    className={styles.actionBtn}
                    title="Download PDF report"
                    onClick={() => handleDownloadFile(file)}
                    disabled={downloadingId === file.id}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    {downloadingId === file.id ? 'Exporting...' : 'Download PDF'}
                  </button>
                  <button
                    className={styles.actionBtn}
                    title="Open report in chat"
                    onClick={() => handleOpenInChat(file)}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                      <polyline points="15 3 21 3 21 9" />
                      <line x1="10" y1="14" x2="21" y2="3" />
                    </svg>
                    Open
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className={styles.emptyState}>
          <div className={styles.emptyIconWrapper}>
            <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#a855f7" strokeWidth="1.5">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z" />
              <line x1="7" y1="7" x2="7.01" y2="7" strokeWidth="2" />
            </svg>
          </div>
          <h3>No files generated yet</h3>
          <p>You haven&apos;t generated any files yet. Once you build strategies, blueprints, or decks, they will appear here as downloadable PDFs.</p>
        </div>
      )}

      {/* Hidden container for rendering markdown before PDF export from FilesView */}
      {activeExportFile && (
        <div style={{ position: 'fixed', left: '-9999px', top: 0, width: '780px', background: '#fff', padding: '24px' }}>
          <div ref={hiddenRenderRef}>
            <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[rehypeRaw]}>
              {activeExportFile.content}
            </ReactMarkdown>
          </div>
        </div>
      )}
    </div>
  );
}
