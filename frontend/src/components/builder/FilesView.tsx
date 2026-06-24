'use client';

import { useState, useMemo } from 'react';
import styles from './FilesView.module.css';

interface GeneratedFile {
  id: string;
  name: string;
  type: 'pdf' | 'csv' | 'docx' | 'html';
  size: string;
  date: string;
  description: string;
  category: string;
  shared: boolean;
  gradient: string;
}

const MOCK_FILES: GeneratedFile[] = [
  {
    id: '1',
    name: 'Brand Strategy & Positioning Canvas',
    type: 'pdf',
    size: '2.4 MB',
    date: '2026-06-16 16:30',
    description: 'Comprehensive brand positioning canvas, target segments, and unique value propositions.',
    category: 'Brand Strategy',
    shared: false,
    gradient: 'linear-gradient(135deg, #7c3aed, #4f46e5)',
  },
  {
    id: '2',
    name: 'Go-To-Market Launch Blueprint',
    type: 'pdf',
    size: '4.1 MB',
    date: '2026-06-16 16:35',
    description: 'Step-by-step GTM roadmap, marketing channel mix, budget suggestions, and acquisition timeline.',
    category: 'GTM Strategy',
    shared: false,
    gradient: 'linear-gradient(135deg, #ec4899, #8b5cf6)',
  },
  {
    id: '3',
    name: 'Q3 Content Calendar & Campaign Deck',
    type: 'csv',
    size: '482 KB',
    date: '2026-06-16 16:42',
    description: '30-day topical content pipeline, themes, tags, copy templates, and LinkedIn/X posting schedules.',
    category: 'Content Strategy',
    shared: true,
    gradient: 'linear-gradient(135deg, #10b981, #059669)',
  },
  {
    id: '4',
    name: 'Competitor Ad Strategy & Performance Deconstruction',
    type: 'pdf',
    size: '3.8 MB',
    date: '2026-06-16 16:50',
    description: 'Deep-dive analysis of competitors\' ad copies, platforms, estimated spends, and message vectors.',
    category: 'Competitor Intelligence',
    shared: false,
    gradient: 'linear-gradient(135deg, #f59e0b, #d97706)',
  },
  {
    id: '5',
    name: 'SEO & GEO (AI Overviews) Technical Audit',
    type: 'html',
    size: '1.2 MB',
    date: '2026-06-16 17:05',
    description: 'Search and AI Overview optimization index, keyword gap analysis, and citation recommendations.',
    category: 'SEO & GEO',
    shared: true,
    gradient: 'linear-gradient(135deg, #3b82f6, #1d4ed8)',
  },
  {
    id: '6',
    name: 'Topical Launch Social Media Copy Deck',
    type: 'docx',
    size: '920 KB',
    date: '2026-06-16 17:15',
    description: 'Ready-to-use copy variations, headlines, CTAs, and visual asset outlines for digital ad campaigns.',
    category: 'Creative Assets',
    shared: false,
    gradient: 'linear-gradient(135deg, #ef4444, #b91c1c)',
  },
];

export default function FilesView() {
  const [activeTab, setActiveTab] = useState<'all' | 'mine' | 'shared'>('all');
  const [searchQuery, setSearchQuery] = useState('');
  const [sortBy, setSortBy] = useState<'recent' | 'name' | 'size'>('recent');

  // Filtered files
  const filteredFiles = useMemo(() => {
    return MOCK_FILES.filter(file => {
      // Tab filter
      if (activeTab === 'mine' && file.shared) return false;
      if (activeTab === 'shared' && !file.shared) return false;

      // Search filter
      const matchQuery =
        file.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        file.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
        file.category.toLowerCase().includes(searchQuery.toLowerCase());
      return matchQuery;
    }).sort((a, b) => {
      if (sortBy === 'name') {
        return a.name.localeCompare(b.name);
      }
      if (sortBy === 'size') {
        const sizeA = parseFloat(a.size);
        const sizeB = parseFloat(b.size);
        return sizeB - sizeA;
      }
      // default: recent first
      return new Date(b.date).getTime() - new Date(a.date).getTime();
    });
  }, [activeTab, searchQuery, sortBy]);

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
      case 'csv':
        return (
          <svg className={styles.fileIcon} viewBox="0 0 24 24" fill="none" stroke="#10b981" strokeWidth="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="8" y1="13" x2="16" y2="13" />
            <line x1="8" y1="17" x2="16" y2="17" />
            <line x1="10" y1="9" x2="10" y2="9" />
          </svg>
        );
      case 'docx':
        return (
          <svg className={styles.fileIcon} viewBox="0 0 24 24" fill="none" stroke="#3b82f6" strokeWidth="2.5">
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
            <polyline points="14 2 14 8 20 8" />
            <line x1="9" y1="13" x2="15" y2="13" />
            <line x1="9" y1="17" x2="15" y2="17" />
            <line x1="9" y1="9" x2="13" y2="9" />
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
        <p className={styles.subtitle}>Browse and manage strategic documents generated for your brand.</p>
      </div>

      {/* Toolbar */}
      <div className={styles.toolbar}>
        {/* Tabs */}
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

        {/* Search & Sort */}
        <div className={styles.actions}>
          <div className={styles.searchBox}>
            <svg className={styles.searchIcon} width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input 
              type="text" 
              className={styles.searchInput} 
              placeholder="Search files..."
              value={searchQuery}
              onChange={e => setSearchQuery(e.target.value)}
            />
            {searchQuery && (
              <button className={styles.clearSearch} onClick={() => setSearchQuery('')}>×</button>
            )}
          </div>

          <div className={styles.sortWrapper}>
            <select 
              className={styles.sortSelect}
              value={sortBy}
              onChange={e => setSortBy(e.target.value as any)}
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
          {filteredFiles.map(file => (
            <div key={file.id} className={styles.card}>
              {/* Thumbnail Area */}
              <div className={styles.thumbnail} style={{ background: file.gradient }}>
                <div className={styles.thumbnailOverlay} />
                <div className={styles.typeBadge}>{file.type.toUpperCase()}</div>
                <div className={styles.thumbnailContent}>
                  <div className={styles.previewTag}>{file.category}</div>
                  <h4 className={styles.previewName}>{file.name}</h4>
                </div>
              </div>

              {/* Detail Area */}
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
                      <span>{file.date.split(' ')[0]}</span>
                    </div>
                  </div>
                </div>

                <p className={styles.description}>{file.description}</p>

                {/* Card Actions */}
                <div className={styles.cardActions}>
                  <button className={styles.actionBtn} title="Download file">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                      <polyline points="7 10 12 15 17 10" />
                      <line x1="12" y1="15" x2="12" y2="3" />
                    </svg>
                    Download
                  </button>
                  <button className={styles.actionBtn} title="Share file">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="18" cy="5" r="3" />
                      <circle cx="6" cy="12" r="3" />
                      <circle cx="18" cy="19" r="3" />
                      <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
                      <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
                    </svg>
                    Share
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
          <h3>No files found</h3>
          <p>We couldn't find any generated files matching your criteria. Try adjusting your filters or search query.</p>
        </div>
      )}
    </div>
  );
}
