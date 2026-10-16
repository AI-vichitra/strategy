'use client';
import { useState, useRef, useEffect } from 'react';
import { connectors as allConnectorsData, getLogoUrl } from '../../data/connectors';
import styles from './TemplateGrid.module.css';

const getDomain = (connectorName: string) => {
  const c = allConnectorsData.find(c => c.name === connectorName);
  return c ? c.domain : 'google.com';
};

const categories = [
  'All',
  'Research & Intelligence',
  'Branding & Marketing',
];

const brandingSubTabs = [
  'All',
  'Digital Strategy',
  'Brand Strategy',
  'Performance Marketing',
  'Strategy & Planning',
];

// Helper to render specific icons
export const allTemplates = [
  // -- Branding & Marketing --
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Competition Analysis',
    desc: 'Identify your true market position and uncover competitor blind spots. Get a feature-by-feature breakdown of where you win, lose, and how to differentiate.',
    connectors: ['Firecrawl', 'Ahrefs', 'Semrush API Key', 'Exa'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'GTM Strategy',
    desc: 'Launch with confidence using a complete Go-To-Market roadmap. Define your target audience, pricing, and distribution channels to maximize market impact.',
    connectors: ['HubSpot', 'Salesforce', 'Google Analytics', 'Exa'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'Product Launch Strategy',
    desc: 'Turn your new product idea into a structured, high-impact rollout plan. Map out your pre-launch buzz, launch day execution, and post-launch retention tactics.',
    connectors: ['Google Analytics', 'LinkedIn', 'X', 'Reddit', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Social Media Strategy',
    desc: 'Build an engaging social presence that converts followers into customers. Get tailored content pillars, posting cadences, and platform-specific growth tactics.',
    connectors: ['LinkedIn', 'X', 'Reddit', 'YouTube'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Content Calendar',
    desc: 'A content planner. It researches what\'s trending, proposes a monthly calendar of topics, and drafts a brief for each piece...',
    connectors: ['Semrush API Key', 'Reddit', 'YouTube', 'Notion', 'Google Docs'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Festival/Topical Campaign Strategy',
    desc: 'Plans festival-season and topical marketing campaigns with timing, messaging, and channel recommendations. Maps out topical authority clusters, pillar topics, and internal linking structures...',
    connectors: ['Google Calendar', 'Semrush API Key', 'Exa', 'Reddit', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'GEO/AEO',
    desc: 'Optimize your brand to rank higher in AI search engines like ChatGPT and Perplexity. Ensure AI tools accurately understand and recommend your brand to users.',
    connectors: ['Google Search Console', 'Ahrefs', 'Semrush API Key', 'Bing Webmaster', 'Firecrawl', 'SerpAPI'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'SEO Strategy',
    desc: 'A comprehensive SEO agent. Give it a website URL and it crawls pages, identifies issues, researches keywords, audits on-page factors, analyzes backlinks, and builds an actionable optimization roadmap...',
    connectors: ['Google Search Console', 'Ahrefs', 'Semrush API Key', 'Bing Webmaster', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Seasonal Campaign',
    desc: 'Builds seasonal marketing plans covering Q1–Q4 peaks, promotional windows, and content cadences for maximum impact...',
    connectors: ['Google Analytics', 'Google Search Console', 'Semrush API Key'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Brand Strategy',
    title: 'Brand Audit',
    desc: 'Evaluate your brand\'s current health, consistency, and messaging across all channels. Discover actionable ways to strengthen your identity.',
    connectors: ['Google Analytics', 'Google Search Console', 'Reddit', 'X', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Brand Strategy',
    title: 'Brand Positioning',
    desc: 'Defines your unique market position. Analyzes competitors, identifies white space, and crafts a compelling positioning statement...',
    connectors: ['Exa', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'ICP & Personas',
    desc: 'Defines your Ideal Customer Profile and builds detailed buyer personas with firmographics, pain points, and buying triggers...',
    connectors: ['HubSpot', 'Salesforce', 'Apollo'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Performance Marketing',
    title: 'Campaign Structure Architect',
    desc: 'Designs the optimal campaign structure for your paid media. Covers account hierarchy, ad group logic, naming conventions...',
    connectors: ['Google Ads', 'Google Analytics'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Performance Marketing',
    title: 'Bidding & Budget Optimizer',
    desc: 'Analyzes your current bidding strategies and budget allocation across campaigns and recommends optimizations for better ROI...',
    connectors: ['Google Ads', 'Google Analytics'],
    plusText: ''
  },

  // -- Research & Intelligence --
  {
    category: 'Research & Intelligence',
    title: 'Company Research Agent',
    desc: 'A company research agent. Give it a company name and it puts together a one-pager covering their product, team...',
    connectors: ['LinkedIn', 'Exa', 'Firecrawl'],
    plusText: '+1'
  },
  {
    category: 'Research & Intelligence',
    title: 'Competitive Intelligence Agent',
    desc: 'A competitive intel agent. It watches competitor websites for changes, tracks their announcements and press...',
    connectors: ['Firecrawl', 'Ahrefs', 'Reddit', 'X'],
    plusText: '+2'
  }
];


interface TemplateGridProps {
  onSelectAgent: (title: string) => void;
}

export default function TemplateGrid({ onSelectAgent }: TemplateGridProps) {
  const [activeTab, setActiveTab] = useState('All');
  const [activeBrandingSubTab, setActiveBrandingSubTab] = useState('All');
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

  const filteredSearchAgents = allTemplates.filter(agent =>
    agent.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const isBranding = activeTab === 'Branding & Marketing';

  // Filter templates based on active tab (and sub-tab if branding)
  const displayedTemplates = (() => {
    if (activeTab === 'All') return allTemplates;
    if (isBranding) {
      const brandingCards = allTemplates.filter(t => t.category === 'Branding & Marketing');
      if (activeBrandingSubTab === 'All') return brandingCards;
      return brandingCards.filter(t => t.subCategory === activeBrandingSubTab);
    }
    return allTemplates.filter(t => t.category === activeTab);
  })();

  // Count agents per category (for hover badge)
  const categoryCounts: Record<string, number> = {};
  categoryCounts['All'] = allTemplates.length;
  categories.slice(1).forEach(cat => {
    categoryCounts[cat] = allTemplates.filter(t => t.category === cat).length;
  });

  // Count agents per Branding & Marketing sub-tab (for hover badge)
  const brandingCards = allTemplates.filter(t => t.category === 'Branding & Marketing');
  const subCategoryCounts: Record<string, number> = {};
  subCategoryCounts['All'] = brandingCards.length;
  brandingSubTabs.slice(1).forEach(sub => {
    subCategoryCounts[sub] = brandingCards.filter(t => t.subCategory === sub).length;
  });

  return (
    <div className={styles.wrapper}>
      <div className={styles.headerRow}>
        <h2 className={styles.title}>Templates</h2>
        
        {/* Search input with live dropdown */}
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
              {filteredSearchAgents.map((agent, i) => (
                <button
                  key={i}
                  type="button"
                  className={styles.dropdownItem}
                  onClick={() => {
                    onSelectAgent(agent.title);
                    setSearchQuery('');
                  }}
                >
                  <div className={styles.dropdownItemContent}>
                    <span className={styles.dropdownItemTitle}>{agent.title}</span>
                    <span className={styles.dropdownItemCategory}>{agent.category}</span>
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Primary tabs */}
      <div className={styles.tabsContainer}>
        <div className={styles.tabsScroll}>
          {categories.map((cat, i) => (
            <button
              key={i}
              onClick={() => {
                setActiveTab(cat);
                if (cat === 'Branding & Marketing') setActiveBrandingSubTab('All');
              }}
              className={`${styles.tab} ${activeTab === cat ? styles.activeTab : ''}`}
            >
              <span className={styles.tabLabel}>{cat}</span>
              <span className={styles.tabCount}>{categoryCounts[cat]}</span>
            </button>
          ))}
        </div>
      </div>

      {/* Sub-tabs — only shown for Branding & Marketing */}
      {isBranding && (
        <div className={styles.subTabsContainer}>
          <div className={styles.subTabsScroll}>
            {brandingSubTabs.map((sub, i) => (
              <button
                key={i}
                onClick={() => setActiveBrandingSubTab(sub)}
                className={`${styles.subTab} ${activeBrandingSubTab === sub ? styles.activeSubTab : ''}`}
              >
                <span>{sub}</span>
                <span className={styles.subTabCount}>{subCategoryCounts[sub]}</span>
              </button>
            ))}
          </div>
        </div>
      )}

      <div className={styles.grid}>
        {displayedTemplates.map((tpl, i) => (
          <div key={i} className={styles.card} onClick={() => onSelectAgent(tpl.title)}>
            <div className={styles.cardTop}>
              <h3 className={styles.cardTitle}>{tpl.title}</h3>
              <p className={styles.cardDesc}>{tpl.desc}</p>
            </div>
            <div className={styles.cardBottom}>
              <div className={styles.iconGroup}>
                {tpl.connectors.slice(0, 4).map((cName, j) => (
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
              {tpl.connectors.length > 4 && (
                <div className={styles.plusOne}>+{tpl.connectors.length - 4}</div>
              )}
            </div>
          </div>
        ))}
        {displayedTemplates.length === 0 && (
          <div className={styles.emptyState}>
            No templates available for {isBranding ? activeBrandingSubTab : activeTab} yet.
          </div>
        )}
      </div>
    </div>
  );
}

