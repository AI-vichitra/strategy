'use client';
import { useState, useRef, useEffect, useMemo } from 'react';
import { connectors as allConnectorsData, getLogoUrl } from '../../data/connectors';
import { getAgentIcon } from '../../data/agentIcons';
import { useAgents, type Agent, type AgentCategory } from '../../hooks/useAgents';
import styles from './TemplateGrid.module.css';

const getDomain = (connectorName: string) => {
  const c = allConnectorsData.find(c => c.name === connectorName);
  return c ? c.domain : 'google.com';
};

// A category with no "group" field still gets its own top-level tab,
// keyed by its own name, rather than being dropped.
const groupOf = (cat: AgentCategory) => cat.group || cat.name;

// Pseudo-group shown as the first tab: every enabled agent, organized by
// the normal category-section layout.
const ALL_TAB = 'All';

interface TemplateGridProps {
  onSelectAgent: (title: string) => void;
}

function AgentCard({ agent, onSelectAgent }: { agent: Agent; onSelectAgent: (title: string) => void }) {
  return (
    <div className={styles.card} onClick={() => onSelectAgent(agent.title)}>
      <div className={styles.cardTop}>
        <div className={styles.cardTitleRow}>
          <span className={styles.cardIcon} aria-hidden="true">
            {getAgentIcon(agent.title, agent.category)}
          </span>
          <h3 className={styles.cardTitle}>{agent.title}</h3>
        </div>
        <p className={styles.cardDesc}>{agent.description}</p>
      </div>
      <div className={styles.cardBottom}>
        <div className={styles.iconGroup}>
          {agent.connectors.slice(0, 4).map((cName, j) => (
            <span key={j} className={styles.miniIcon} title={cName}>
              <img
                src={getLogoUrl(getDomain(cName))}
                alt={cName}
                className={styles.miniIconImg}
                onError={(e) => {
                  // fallback to a letter if image fails completely (rare with google favicons)
                  e.currentTarget.style.display = 'none';
                  if (e.currentTarget.nextElementSibling) {
                     (e.currentTarget.nextElementSibling as HTMLElement).style.display = 'flex';
                  }
                }}
              />
              <span className={styles.fallbackText} style={{ display: 'none' }}>
                {cName.charAt(0)}
              </span>
            </span>
          ))}
        </div>
        {agent.connectors.length > 4 && (
          <div className={styles.plusOne}>+{agent.connectors.length - 4}</div>
        )}
      </div>
    </div>
  );
}

export default function TemplateGrid({ onSelectAgent }: TemplateGridProps) {
  const { agents, categories, loading, error, refetch } = useAgents();
  const [activeGroup, setActiveGroup] = useState<string>(ALL_TAB);
  const [searchQuery, setSearchQuery] = useState('');
  const searchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (searchContainerRef.current && !searchContainerRef.current.contains(e.target as Node)) {
        setSearchQuery('');
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Top-level tab row — the distinct groups, in first-appearance order.
  const groupsInOrder = useMemo(() => {
    const seen = new Set<string>();
    const order: string[] = [];
    categories.forEach((c) => {
      const g = groupOf(c);
      if (!seen.has(g)) {
        seen.add(g);
        order.push(g);
      }
    });
    return order;
  }, [categories]);

  // Derived rather than persisted: falls back to "All" for this render if
  // the previously active group disappears (e.g. catalog reloads).
  const effectiveActiveGroup = useMemo(() => {
    if (activeGroup === ALL_TAB || groupsInOrder.includes(activeGroup)) return activeGroup;
    return ALL_TAB;
  }, [activeGroup, groupsInOrder]);

  const categoryNameById = useMemo(() => {
    const map: Record<string, string> = {};
    categories.forEach((c) => { map[c.id] = c.name; });
    return map;
  }, [categories]);

  // Categories belonging to the active group, in API order — each renders
  // as its own labeled section beneath the group tab. "All" shows every
  // category, in the order the API returns them.
  const categoriesInActiveGroup = useMemo(() => {
    if (effectiveActiveGroup === ALL_TAB) return categories;
    return categories.filter((c) => groupOf(c) === effectiveActiveGroup);
  }, [categories, effectiveActiveGroup]);

  const agentCountByGroup = useMemo(() => {
    const counts: Record<string, number> = { [ALL_TAB]: agents.length };
    groupsInOrder.forEach((g) => {
      const categoryIds = new Set(categories.filter((c) => groupOf(c) === g).map((c) => c.id));
      counts[g] = agents.filter((a) => categoryIds.has(a.category)).length;
    });
    return counts;
  }, [groupsInOrder, categories, agents]);

  // Search dropdown always searches across every agent, regardless of the
  // active group/category.
  const filteredSearchAgents = useMemo(
    () => agents.filter((agent) => agent.title.toLowerCase().includes(searchQuery.toLowerCase())),
    [agents, searchQuery]
  );

  const totalAgentsInActiveGroup = useMemo(
    () => categoriesInActiveGroup.reduce((sum, cat) => sum + agents.filter((a) => a.category === cat.id).length, 0),
    [categoriesInActiveGroup, agents]
  );

  return (
    <div className={styles.wrapper}>
      <div className={styles.headerRow}>
        <h2 className={styles.title}>Templates</h2>

        {/* Search input with live dropdown — searches the full catalog */}
        <div className={styles.searchContainer} ref={searchContainerRef}>
          <div className={styles.searchInputWrapper}>
            <svg className={styles.searchIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="11" cy="11" r="8" />
              <line x1="21" y1="21" x2="16.65" y2="16.65" />
            </svg>
            <input
              type="text"
              className={styles.searchInput}
              placeholder="Search templates..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>

          {searchQuery.trim() !== '' && filteredSearchAgents.length > 0 && (
            <div className={styles.searchDropdown}>
              {filteredSearchAgents.map((agent) => (
                <button
                  key={agent.id}
                  type="button"
                  className={styles.dropdownItem}
                  onClick={() => {
                    onSelectAgent(agent.title);
                    setSearchQuery('');
                  }}
                >
                  <div className={styles.dropdownItemContent}>
                    <span className={styles.dropdownItemTitle}>{agent.title}</span>
                    <span className={styles.dropdownItemCategory}>
                      {categoryNameById[agent.category] || agent.category}
                    </span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Top-level group tabs — "All" first, then each group from the "group" field */}
      {!loading && !error && groupsInOrder.length > 0 && (
        <div className={styles.tabsContainer}>
          <div className={styles.tabsScroll}>
            <button
              onClick={() => setActiveGroup(ALL_TAB)}
              className={`${styles.tab} ${effectiveActiveGroup === ALL_TAB ? styles.activeTab : ''}`}
            >
              <span className={styles.tabLabel}>{ALL_TAB}</span>
              <span className={styles.tabCount}>{agentCountByGroup[ALL_TAB] ?? 0}</span>
            </button>
            {groupsInOrder.map((g) => (
              <button
                key={g}
                onClick={() => setActiveGroup(g)}
                className={`${styles.tab} ${effectiveActiveGroup === g ? styles.activeTab : ''}`}
              >
                <span className={styles.tabLabel}>{g}</span>
                <span className={styles.tabCount}>{agentCountByGroup[g] ?? 0}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      {loading && (
        <div className={styles.grid}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={`${styles.card} ${styles.cardSkeleton}`} aria-hidden="true" />
          ))}
        </div>
      )}

      {!loading && error && (
        <div className={styles.errorState}>
          <p>Couldn&apos;t load the agent catalog. {error}</p>
          <button type="button" className={styles.retryBtn} onClick={refetch}>
            Retry
          </button>
        </div>
      )}

      {!loading && !error && totalAgentsInActiveGroup === 0 && (
        <div className={styles.emptyState}>
          No templates available for {effectiveActiveGroup === ALL_TAB ? 'this view' : effectiveActiveGroup} yet.
        </div>
      )}

      {!loading && !error && totalAgentsInActiveGroup > 0 && categoriesInActiveGroup.map((cat) => {
        const catAgents = agents.filter((a) => a.category === cat.id);
        if (catAgents.length === 0) return null;
        return (
          <div key={cat.id} className={styles.categorySection}>
            <div className={styles.categorySectionHeader}>
              <h3 className={styles.categorySectionTitle}>{cat.name}</h3>
              <span className={styles.categorySectionCount}>{catAgents.length}</span>
            </div>
            <div className={styles.grid}>
              {catAgents.map((agent) => (
                <AgentCard key={agent.id} agent={agent} onSelectAgent={onSelectAgent} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
