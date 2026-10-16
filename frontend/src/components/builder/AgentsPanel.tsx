'use client';
import { useState, useEffect } from 'react';
import { allTemplates } from './TemplateGrid';
import { connectors as allConnectorsData, getLogoUrl } from '../../data/connectors';
import styles from './AgentsPanel.module.css';

interface AgentsPanelProps {
  open: boolean;
  onClose: () => void;
  onSelectAgent: (title: string) => void;
  defaultCategory?: string;
}

const getDomain = (connectorName: string) => {
  const c = allConnectorsData.find(c => c.name === connectorName);
  return c ? c.domain : 'google.com';
};

function MiniIconImg({ connectorName }: { connectorName: string }) {
  const [imgError, setImgError] = useState(false);
  if (imgError) {
    return (
      <span style={{
        fontSize: '10px', fontWeight: 700,
        color: '#B8912E', lineHeight: 1
      }}>
        {connectorName.charAt(0)}
      </span>
    );
  }
  return (
    <img
      src={getLogoUrl(getDomain(connectorName))}
      alt={connectorName}
      className={styles.miniIconImg}
      onError={() => setImgError(true)}
    />
  );
}

export default function AgentsPanel({ open, onClose, onSelectAgent, defaultCategory }: AgentsPanelProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState(defaultCategory || 'All');

  // Reset state when panel closes; apply defaultCategory when panel opens
  useEffect(() => {
    if (!open) {
      setSearchQuery('');
      setSelectedCategory('All');
    } else {
      setSelectedCategory(defaultCategory || 'All');
    }
  }, [open, defaultCategory]);

  // Removed body scroll lock to allow interaction with chatbox

  // Filter templates
  const filteredTemplates = allTemplates.filter(agent => {
    const matchesSearch = agent.title.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          agent.desc.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesCategory = selectedCategory === 'All' || agent.category === selectedCategory;
    return matchesSearch && matchesCategory;
  });

  // Extract unique categories dynamically
  const categories = ['All', ...Array.from(new Set(allTemplates.map(t => t.category)))];

  return (
    <>
      {/* Removed overlay to allow interaction behind the panel */}
      <div className={`${styles.panel} ${open ? styles.panelOpen : ''}`}>
        <div className={styles.header}>
          <h2 className={styles.headerTitle}>Available Agents</h2>
          <button className={styles.closeBtn} onClick={onClose} aria-label="Close">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18"></line>
              <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
          </button>
        </div>

        {/* Search & Categories Bar */}
        <div className={styles.searchBarContainer}>
          <div className={styles.searchWrapper}>
            <svg className={styles.searchIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input 
              type="text" 
              placeholder="Search agents..." 
              className={styles.searchInput}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          
          <div className={styles.categoriesRow}>
            {categories.map(cat => (
              <button 
                key={cat}
                type="button"
                className={`${styles.categoryTab} ${selectedCategory === cat ? styles.categoryTabActive : ''}`}
                onClick={() => setSelectedCategory(cat)}
              >
                {cat}
              </button>
            ))}
          </div>
        </div>

        <div className={styles.scrollArea}>
          {filteredTemplates.length === 0 ? (
            <div className={styles.emptyState}>No agents found matching your criteria.</div>
          ) : (
            <div className={styles.grid}>
              {filteredTemplates.map((agent, i) => (
                <div 
                  key={i} 
                  className={styles.agentCard}
                  onClick={() => {
                    onSelectAgent(agent.title);
                    onClose();
                  }}
                >
                  <div className={styles.cardHeader}>
                    <span className={styles.agentTitle}>{agent.title}</span>
                    <span className={styles.categoryBadge}>{agent.category}</span>
                  </div>
                  <p className={styles.agentDesc}>{agent.desc}</p>
                  <div className={styles.cardFooter}>
                    <div className={styles.miniIconsGroup}>
                      {agent.connectors.slice(0, 4).map((conn, idx) => (
                        <div key={idx} className={styles.miniIcon} title={conn}>
                          <MiniIconImg connectorName={conn} />
                        </div>
                      ))}
                      {agent.connectors.length > 4 && (
                        <span className={styles.plusMore}>+{agent.connectors.length - 4}</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </>
  );
}
