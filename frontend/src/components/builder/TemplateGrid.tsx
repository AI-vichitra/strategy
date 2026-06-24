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
  'Sales & Outreach',
  'Data & Analytics',
  'Productivity & Ops',
  'Support & Success',
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
  // -- Sales & Outreach --
  {
    category: 'Sales & Outreach',
    title: 'Competitor Research Agent',
    desc: 'A research agent that digs into any competitor. Give it a company name or website and it comes back with their...',
    connectors: ['Firecrawl', 'Exa', 'SerpAPI', 'Reddit'],
    plusText: '+1'
  },
  {
    category: 'Sales & Outreach',
    title: 'Cold Outreach Writer',
    desc: 'A cold email writer that does its homework first. Give it a prospect and it researches their company, finds releva...',
    connectors: ['LinkedIn', 'Apollo', 'Gmail', 'Exa'],
    plusText: '+1'
  },
  {
    category: 'Sales & Outreach',
    title: 'Sales Prospecting Agent',
    desc: 'A proactive sales agent that helps prospecting and outreach. It resear target accounts, finds the right...',
    connectors: ['Apollo', 'LinkedIn', 'ZoomInfo', 'Hunter.io API Key', 'Gmail', 'Google Calendar'],
    plusText: '+1'
  },
  {
    category: 'Sales & Outreach',
    title: 'Lead Enrichment Agent',
    desc: 'An agent that enriches lead lists. Give it a spreadsheet of contacts and it fills in company data, verifies emails, and...',
    connectors: ['Apollo', 'ZoomInfo', 'Hunter.io API Key', 'Findymail', 'Google Sheets'],
    plusText: ''
  },
  {
    category: 'Sales & Outreach',
    title: 'CRM Pipeline Reporter',
    desc: 'A reporting agent that summarizes your Salesforce pipeline. It pulls deal data, breaks it down by stage and owner, an...',
    connectors: ['Salesforce', 'HubSpot', 'Google Sheets', 'Google Docs'],
    plusText: '+1'
  },
  {
    category: 'Sales & Outreach',
    title: 'Meeting Prep Agent',
    desc: 'A meeting prep agent. Before any external call, it researches the attendees and their companies an...',
    connectors: ['LinkedIn', 'Apollo', 'ZoomInfo', 'Google Calendar', 'Google Docs', 'Exa', 'Firecrawl'],
    plusText: '+1'
  },
  {
    category: 'Sales & Outreach',
    title: 'Sales Pitch Generator',
    desc: 'A seasoned sales professional that crafts concise, persuasive pitches tailored to each prospect\'s needs and pain points...',
    connectors: ['HubSpot', 'Salesforce', 'OpenAI API Key'],
    plusText: ''
  },
  {
    category: 'Sales & Outreach',
    title: 'Cold Calling Script Generator',
    desc: 'A skilled copywriter that crafts persuasive cold calling scripts that grab attention, build rapport, and drive conversions...',
    connectors: ['LinkedIn', 'HubSpot', 'Salesforce', 'OpenAI API Key'],
    plusText: ''
  },

  // -- Data & Analytics --
  {
    category: 'Data & Analytics',
    title: 'BigQuery Data Analyst',
    desc: 'A data analyst for your BigQuery warehouse. Ask it any business question and it writes the SQL, runs the query,...',
    connectors: ['BigQuery'],
    plusText: '+1'
  },
  {
    category: 'Data & Analytics',
    title: 'PostgreSQL Query Agent',
    desc: 'A query agent for your PostgreSQL database. Ask questions in plain English and it writes safe read-only SQL, runs i...',
    connectors: ['PostgreSQL'],
    plusText: ''
  },
  {
    category: 'Data & Analytics',
    title: 'Data Cleanup Agent',
    desc: 'A cleanup agent for messy spreadsheets. Give it a Google She and it deduplicates rows, standardi...',
    connectors: ['Google Sheets', 'Microsoft Excel'],
    plusText: '+1'
  },
  {
    category: 'Data & Analytics',
    title: 'Spreadsheet Analyst',
    desc: 'An analyst for your Google Sheets data. Give it a spreadsheet and ask questions — it finds patterns, creates summaries,...',
    connectors: ['Google Sheets', 'Microsoft Excel'],
    plusText: ''
  },
  {
    category: 'Data & Analytics',
    title: 'Snowflake Data Analyst',
    desc: 'A data analyst for your Snowflake warehouse. It explores tables, answers questions with SQL, and documents...',
    connectors: ['Snowflake'],
    plusText: '+1'
  },
  {
    category: 'Data & Analytics',
    title: 'Report Generator',
    desc: 'A report writer connected to your warehouse. Ask a business questio it produces a polished report with...',
    connectors: ['BigQuery', 'Snowflake', 'Google Docs'],
    plusText: '+1'
  },

  // -- Support & Success --
  {
    category: 'Support & Success',
    title: 'Customer Lookup Agent',
    desc: 'A customer lookup agent. Give it a name and it pulls together everything — account info, open tickets, recent...',
    connectors: ['HubSpot', 'Salesforce', 'Zendesk'],
    plusText: '+1'
  },
  {
    category: 'Support & Success',
    title: 'Feedback Digest Agent',
    desc: 'A feedback summarizer. It reads through support tickets, groups feedback by theme, and puts together a weekly...',
    connectors: ['Zendesk', 'Freshdesk', 'Intercom'],
    plusText: ''
  },
  {
    category: 'Support & Success',
    title: 'Issue Tracker Agent',
    desc: 'A triage agent for GitHub issues. It categorizes new issues, finds relate ones, and sends you a daily digest o',
    connectors: ['GitHub', 'Jira', 'Linear'],
    plusText: ''
  },
  {
    category: 'Support & Success',
    title: 'Customer Onboarding Agent',
    desc: 'An onboarding agent for new customers. It sets up their checklist, schedules a kickoff call, and sends a welcome emai...',
    connectors: ['HubSpot', 'Salesforce', 'Gmail', 'Google Calendar'],
    plusText: '+1'
  },
  {
    category: 'Support & Success',
    title: 'Help Docs Writer',
    desc: 'A documentation writer. Give it a topic and it researches best practices, checks your existing docs for gaps, and drafts ...',
    connectors: ['Notion', 'Google Docs', 'Confluence'],
    plusText: ''
  },
  {
    category: 'Support & Success',
    title: 'Support Inbox Agent',
    desc: 'A support agent that handles incon tickets. It reads each one, finds the answer from your knowledge base.',
    connectors: ['Zendesk', 'Freshdesk', 'Intercom', 'Notion'],
    plusText: '+1'
  },

  // -- Branding & Marketing — ordered for ALL tab --
  // ① Competition Analysis
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Competition Analysis',
    desc: 'A competitive content analyst. Point it at a competitor\'s website and it breaks down their messaging, content strategy, and gaps...',
    connectors: ['Firecrawl', 'Ahrefs', 'Semrush API Key', 'Exa'],
    plusText: ''
  },
  // ② GTM Strategy
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'GTM Strategy',
    desc: 'Builds a go-to-market plan for your product launch. Covers positioning, ICP, channels, pricing, and 90-day action plan...',
    connectors: ['HubSpot', 'Salesforce', 'Google Analytics', 'Exa'],
    plusText: ''
  },
  // ③ Product Launch Strategy
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'Product Launch Strategy',
    desc: 'Plans a full product launch from pre-launch buzz to post-launch retention. Covers timelines, channels, and success metrics...',
    connectors: ['Google Analytics', 'LinkedIn', 'X', 'Reddit', 'Firecrawl'],
    plusText: ''
  },
  // ④ Social Media Strategy
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Social Media Strategy',
    desc: 'Builds a comprehensive social media strategy tailored to your brand, audience, and goals across all major platforms...',
    connectors: ['LinkedIn', 'X', 'Reddit', 'YouTube'],
    plusText: ''
  },
  // ⑤ Content Calendar
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Content Calendar',
    desc: 'A content planner. It researches what\'s trending, proposes a monthly calendar of topics, and drafts a brief for each piece...',
    connectors: ['Semrush API Key', 'Reddit', 'YouTube', 'Notion', 'Google Docs'],
    plusText: ''
  },
  // ⑥ Festival Campaign (renamed from Festival Strategy)
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Festival Campaign',
    desc: 'Plans festival-season marketing campaigns with timing, messaging, and channel recommendations aligned to key cultural moments...',
    connectors: ['Google Calendar', 'Exa', 'Firecrawl'],
    plusText: ''
  },
  // ⑦ Topical Campaign (renamed from Topical Strategy)
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Topical Campaign',
    desc: 'Maps out topical authority clusters for your niche. Identifies pillar topics, supporting content, and internal linking structures...',
    connectors: ['Semrush API Key', 'Exa', 'Reddit', 'Firecrawl'],
    plusText: ''
  },
  // --- remaining Digital Strategy agents ---
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'GEO/AEO',
    desc: 'Optimizes your content for Generative Engine Optimization and Answer Engine Optimization — ensuring visibility in AI-powered search results...',
    connectors: ['Google Search Console', 'Ahrefs', 'Semrush API Key', 'Bing Webmaster', 'Firecrawl', 'SerpAPI'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'SEO',
    desc: 'A dedicated SEO agent. Researches keywords, audits on-page factors, analyzes backlinks, and builds an actionable optimization roadmap...',
    connectors: [],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Trend Strategy',
    desc: 'Spots emerging trends in your industry before they peak and maps them to content and campaign opportunities...',
    connectors: ['X', 'Reddit', 'YouTube', 'Exa'],
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
    subCategory: 'Digital Strategy',
    title: 'SEO Audit',
    desc: 'An SEO auditor. Give it a website URL and it crawls the pages, identifies issues, and produces an actionable report...',
    connectors: ['Google Search Console', 'Ahrefs', 'Semrush API Key', 'Bing Webmaster', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Business Plan Generator',
    desc: 'Transforms business ideas into detailed, actionable plans covering product, marketing, sales, finance, and funding...',
    connectors: ['Exa', 'Firecrawl', 'Google Docs'],
    plusText: ''
  },

  // --- Brand Strategy ---
  {
    category: 'Branding & Marketing',
    subCategory: 'Brand Strategy',
    title: 'Brand Audit',
    desc: 'Reviews your existing brand across all touchpoints — visual identity, messaging, tone, and positioning — and flags inconsistencies...',
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
    subCategory: 'Brand Strategy',
    title: 'Brand Personality and Guidelines',
    desc: 'Builds your brand\'s personality framework — voice, tone, archetype, and values — and writes a guidelines doc your team can use...',
    connectors: ['LinkedIn', 'X', 'Firecrawl'],
    plusText: ''
  },

  // --- remaining Strategy & Planning ---
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'Market Sizing & Entry',
    desc: 'Calculates TAM, SAM, and SOM for your market and recommends the best entry strategy based on competitive dynamics...',
    connectors: ['Exa', 'Firecrawl', 'SerpAPI'],
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
    subCategory: 'Strategy & Planning',
    title: 'Partnership & Distribution Strategy',
    desc: 'Identifies high-value partnership opportunities and builds a distribution strategy to scale reach beyond owned channels...',
    connectors: ['LinkedIn', 'Apollo', 'HubSpot'],
    plusText: ''
  },
  {
    category: 'Branding & Marketing',
    subCategory: 'Strategy & Planning',
    title: 'Revenue Model Strategy',
    desc: 'Analyzes your business model and recommends the optimal revenue structure — pricing tiers, monetization, and upsell paths...',
    connectors: ['HubSpot', 'Salesforce', 'Google Analytics'],
    plusText: ''
  },

  // ⑧⑨⑩⑪ — last four in ALL (as requested)
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
    title: 'Attribution & Measurement Agent',
    desc: 'Audits your current attribution model, identifies gaps in measurement, and recommends the right tracking setup for your funnel...',
    connectors: ['Google Analytics', 'Google Ads', 'BigQuery'],
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
  {
    category: 'Branding & Marketing',
    subCategory: 'Digital Strategy',
    title: 'Legal Agreement Drafter',
    desc: 'An experienced contract lawyer that drafts clear, concise, and legally binding agreements tailored to your needs...',
    connectors: ['Google Docs', 'Notion'],
    plusText: ''
  },

  // -- Productivity & Ops --
  {
    category: 'Productivity & Ops',
    title: 'Meeting Notes Agent',
    desc: 'A meeting notes agent. It listens to your calls, pulls out the key decisions and action items, writes clean notes, and...',
    connectors: ['Google Meet', 'Zoom', 'Gong', 'Google Docs'],
    plusText: '+2'
  },
  {
    category: 'Productivity & Ops',
    title: 'Executive Assistant',
    desc: 'A personal assistant that manages your calendar, drafts emails, organizes files, and keeps your docs in order. Proactive...',
    connectors: ['Gmail', 'Google Calendar', 'Google Drive', 'Google Docs', 'Slack'],
    plusText: '+2'
  },
  {
    category: 'Productivity & Ops',
    title: 'Inbox Manager',
    desc: 'An email manager. It goes through yo inbox, sorts what\'s urgent from what\' not, drafts replies for the routine stuf',
    connectors: ['Gmail', 'Microsoft Outlook'],
    plusText: ''
  },
  {
    category: 'Productivity & Ops',
    title: 'Daily Standup Agent',
    desc: 'A standup prep agent. Each morning it checks your tickets and calendar and puts together a quick brief — what...',
    connectors: ['Jira', 'ClickUp', 'Linear', 'Google Calendar'],
    plusText: '+1'
  },
  {
    category: 'Productivity & Ops',
    title: 'Weekly Recap Agent',
    desc: 'A weekly recap agent. Every Friday it looks back at the week\'s tickets, meetings, and accomplishments and...',
    connectors: ['Jira', 'ClickUp', 'Asana', 'Slack', 'Google Calendar'],
    plusText: '+2'
  },
  {
    category: 'Productivity & Ops',
    title: 'Internal Knowledge Agent',
    desc: 'An internal knowledge agent. Ask it a question and it searches your compa docs and wikis to find the answer....',
    connectors: ['Notion', 'Google Drive', 'Google Docs', 'Confluence'],
    plusText: '+1'
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
  },
  {
    category: 'Research & Intelligence',
    title: 'News & Trends Monitor',
    desc: 'A news monitoring agent. It tracks industry news and emerging trends, filters for what actually matters, and',
    connectors: ['Exa', 'Reddit', 'X', 'Firecrawl'],
    plusText: ''
  },
  {
    category: 'Research & Intelligence',
    title: 'Market Research Agent',
    desc: 'A market research agent. Give it an industry or category and it maps out the market — size, key players, trends, and...',
    connectors: ['Exa', 'Firecrawl', 'SerpAPI'],
    plusText: '+1'
  },
  {
    category: 'Research & Intelligence',
    title: 'Deep Research Agent',
    desc: 'A thorough research agent. Give it any question and it searches across multiple sources in parallel, reads through the...',
    connectors: ['Exa', 'Firecrawl', 'SerpAPI', 'Perplexity API Key'],
    plusText: '+2'
  },
  {
    category: 'Research & Intelligence',
    title: 'Recruiting Sourcer',
    desc: 'A recruiting sourcer. Give it a job description and it finds matching candidates, scores them against th',
    connectors: ['LinkedIn', 'Greenhouse', 'Ashby'],
    plusText: '+1'
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

