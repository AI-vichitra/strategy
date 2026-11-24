'use client';
import { useState, useRef } from 'react';
import styles from './AgentTemplateView.module.css';
import { type CompetitorDetail } from '../CompetitorForm';

export interface TargetAudienceData {
  region?: string;
  segments?: string[];
  locations?: string;
  notes?: string;
}

interface QuestionItem {
  question: string;
  options: string[];
  multiSelect?: boolean;
}

interface AgentTemplateViewProps {
  selectedAgent: string;
  agentDescription?: string;
  brand?: {
    id?: string;
    brand_name?: string;
    website_url?: string;
    category?: string;
    logo_url?: string;
    target_market?: any;
    additional_notes?: string;
  } | null;
  competitors: CompetitorDetail[];
  onUpdateCompetitors: (comps: CompetitorDetail[]) => void;
  userContext: string;
  onChangeUserContext: (val: string) => void;
  qaAnswers: Array<{ question: string; answer: string }>;
  onUpdateQaAnswers: (answers: Array<{ question: string; answer: string }>) => void;
  questions?: QuestionItem[];
  targetAudience: TargetAudienceData;
  onChangeTargetAudience: (ta: TargetAudienceData) => void;
  additionalNotes: string;
  onChangeAdditionalNotes: (notes: string) => void;
  brandKit?: any;
  onChangeBrandKit?: (bk: any) => void;
  attachedFiles: File[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
}

const TABS = [
  { id: 'brand_details', label: 'Brand Details' },
  { id: 'strategy_preferences', label: 'Strategy Preferences' },
  { id: 'target_audience', label: 'Target Audience' },
  { id: 'additional_info', label: 'Additional Info' },
] as const;

type TabId = typeof TABS[number]['id'];

const DEFAULT_REGIONS = [
  'Global', 'North America', 'Europe', 'Asia-Pacific', 'India', 'United Kingdom', 'Middle East', 'Latin America'
];

const DEFAULT_SEGMENTS = [
  'B2B Enterprise Leaders', 'High Net Worth Individuals', 'Tech & Product Innovators', 'Gen Z & Millennials',
  'Small Business Owners', 'Industry Specialists', 'Mass Market Shoppers', 'Early Adopters'
];

const DEFAULT_GOALS = [
  'Brand Awareness', 'Lead Generation', 'Market Expansion', 'Sales & Revenue Growth',
  'Competitive Positioning', 'Customer Retention', 'Thought Leadership'
];

const DEFAULT_FORMATS = [
  'Executive Summary', 'Detailed Strategic Plan', 'Step-by-Step Playbook', 'Comprehensive Competitive Audit'
];

const DEFAULT_TIMELINES = [
  'Immediate (30 Days)', 'Quarterly (90 Days)', '6-Month Implementation', '1-Year Strategic Horizon'
];

export default function AgentTemplateView({
  selectedAgent,
  agentDescription,
  brand,
  competitors,
  onUpdateCompetitors,
  userContext,
  onChangeUserContext,
  qaAnswers,
  onUpdateQaAnswers,
  questions,
  targetAudience,
  onChangeTargetAudience,
  additionalNotes,
  onChangeAdditionalNotes,
  brandKit,
  onChangeBrandKit,
  attachedFiles,
  onAddFiles,
  onRemoveFile,
}: AgentTemplateViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('brand_details');
  const [userContextOpen, setUserContextOpen] = useState(false);
  const [brandNameDraft, setBrandNameDraft] = useState(brand?.brand_name || '');
  const [websiteDraft, setWebsiteDraft] = useState(brand?.website_url || '');

  // Inline add competitor state
  const [showAddCompetitor, setShowAddCompetitor] = useState(false);
  const [newCompName, setNewCompName] = useState('');
  const [newCompUrl, setNewCompUrl] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  const displayBrandName = brandNameDraft || brand?.brand_name || 'Your Brand';
  const displayWebsite = websiteDraft || brand?.website_url || 'https://www.example.com';

  const subtitle = agentDescription ||
    `Add the details below to generate a detailed ${selectedAgent.toLowerCase()} report based on your brand research data.`;

  // Competitor removal
  const handleRemoveCompetitor = (index: number) => {
    onUpdateCompetitors(competitors.filter((_, i) => i !== index));
  };

  // Add competitor
  const handleSaveNewCompetitor = () => {
    const trimmedName = newCompName.trim();
    if (!trimmedName || competitors.length >= 5) return;
    onUpdateCompetitors([
      ...competitors,
      {
        brand_name: trimmedName,
        website_url: newCompUrl.trim(),
        social_media: {}
      }
    ]);
    setNewCompName('');
    setNewCompUrl('');
    setShowAddCompetitor(false);
  };

  // Toggle answer in qaAnswers
  const handleToggleQuestionOption = (questionText: string, option: string, multiSelect?: boolean) => {
    const existing = qaAnswers.find(a => a.question === questionText);
    let nextAnswer = option;

    if (multiSelect !== false && existing) {
      const selected = existing.answer ? existing.answer.split(', ').map(s => s.trim()).filter(Boolean) : [];
      if (selected.includes(option)) {
        const filtered = selected.filter(s => s !== option);
        nextAnswer = filtered.join(', ');
      } else {
        nextAnswer = [...selected, option].join(', ');
      }
    }

    const updated = qaAnswers.filter(a => a.question !== questionText);
    if (nextAnswer) {
      updated.push({ question: questionText, answer: nextAnswer });
    }
    onUpdateQaAnswers(updated);
  };

  const isOptionSelected = (questionText: string, option: string): boolean => {
    const existing = qaAnswers.find(a => a.question === questionText);
    if (!existing || !existing.answer) return false;
    const items = existing.answer.split(', ').map(s => s.trim());
    return items.includes(option);
  };

  const handleToggleAudienceSegment = (seg: string) => {
    const current = targetAudience.segments || [];
    const next = current.includes(seg) ? current.filter(s => s !== seg) : [...current, seg];
    onChangeTargetAudience({ ...targetAudience, segments: next });
  };

  return (
    <div className={styles.container}>
      {/* ── Agent Header ── */}
      <div className={styles.headerRow}>
        <div className={styles.agentIconWrap}>
          <svg width="34" height="34" viewBox="0 0 24 24" fill="#7C3AED">
            <path d="M12 2C6.48 2 2 6.48 2 12v8c0 1.1.9 2 2 2h4v-6h4v6h4v-6h4v6h2c1.1 0 2-.9 2-2v-8c0-5.52-4.48-10-10-10zm-4 10c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm8 0c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z" />
          </svg>
        </div>
        <div>
          <h1 className={styles.agentTitle}>{selectedAgent}</h1>
          <p className={styles.agentSubtitle}>{subtitle}</p>
        </div>
      </div>

      {/* ── Multi Tabs Bar ── */}
      <div className={styles.tabsBarWrap}>
        <div className={styles.tabsBar}>
          {TABS.map((tab, idx) => {
            const isActive = activeTab === tab.id;
            return (
              <span key={tab.id} style={{ display: 'inline-flex', alignItems: 'center' }}>
                <button
                  type="button"
                  className={`${styles.tabItem} ${isActive ? styles.tabItemActive : ''}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  <span className={`${styles.tabDot} ${isActive ? styles.tabDotActive : ''}`} />
                  {tab.label}
                </button>
                {idx < TABS.length - 1 && <span className={styles.tabDivider} />}
              </span>
            );
          })}
        </div>
      </div>

      {/* ── TAB 1: Brand Details ── */}
      {activeTab === 'brand_details' && (
        <>
          {/* Competitor Details Card */}
          <div className={styles.card}>
            <div className={styles.cardHeaderRow}>
              <div className={styles.cardHeaderLeft}>
                <div className={styles.cardIconBox}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="2" y="7" width="20" height="14" rx="2" ry="2" />
                    <path d="M16 21V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v16" />
                  </svg>
                </div>
                <div>
                  <h3 className={styles.cardTitle}>Competitor Details (Optional)</h3>
                  <p className={styles.cardSubtitle}>
                    Add competitors you want analyzed, or skip to let AI identify them automatically
                  </p>
                </div>
              </div>

              <div className={styles.counterBadge}>
                {competitors.length}/5 competitors added ✓
              </div>
            </div>

            {/* 2-Column Fields: Brand Name & Website */}
            <div className={styles.twoColGrid}>
              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  <span>Brand Name <span className={styles.requiredAsterisk}>*</span></span>
                </label>
                <div className={styles.inputWrapper}>
                  <input
                    type="text"
                    className={styles.textInput}
                    value={displayBrandName}
                    maxLength={50}
                    onChange={(e) => setBrandNameDraft(e.target.value)}
                    placeholder="e.g. Ferrari"
                  />
                  <span className={styles.charCount}>{displayBrandName.length}/50</span>
                </div>
              </div>

              <div className={styles.fieldGroup}>
                <label className={styles.fieldLabel}>
                  <span>Website URL</span>
                </label>
                <div className={styles.inputWrapper}>
                  <input
                    type="text"
                    className={`${styles.textInput} ${styles.textInputWithIcon}`}
                    value={displayWebsite}
                    onChange={(e) => setWebsiteDraft(e.target.value)}
                    placeholder="https://www.example.com"
                  />
                  {displayWebsite && (
                    <button
                      type="button"
                      className={styles.externalLinkBtn}
                      title="Open website"
                      onClick={() => {
                        const url = displayWebsite.startsWith('http') ? displayWebsite : `https://${displayWebsite}`;
                        window.open(url, '_blank', 'noopener,noreferrer');
                      }}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6" />
                        <polyline points="15 3 21 3 21 9" />
                        <line x1="10" y1="14" x2="21" y2="3" />
                      </svg>
                    </button>
                  )}
                </div>
              </div>
            </div>

            {/* About Your Competitors */}
            <div className={styles.competitorsSection}>
              <div className={styles.competitorsHeader}>
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10" />
                  <line x1="12" y1="20" x2="12" y2="4" />
                  <line x1="6" y1="20" x2="6" y2="14" />
                </svg>
                <span>About Your Competitors</span>
              </div>

              <div className={styles.competitorsChipsRow}>
                {competitors.map((c, i) => (
                  <div key={i} className={styles.competitorChip}>
                    <div className={styles.competitorChipLogo}>
                      {c.logo_url ? (
                        <img
                          src={c.logo_url.startsWith('/') ? `${process.env.NEXT_PUBLIC_API_URL || ''}${c.logo_url}` : c.logo_url}
                          alt={c.brand_name}
                          style={{ width: '100%', height: '100%', objectFit: 'contain' }}
                          onError={(e) => { (e.currentTarget as HTMLElement).style.display = 'none'; }}
                        />
                      ) : (
                        c.brand_name.slice(0, 1).toUpperCase()
                      )}
                    </div>
                    <span>{c.brand_name}</span>
                    <button
                      type="button"
                      className={styles.competitorChipRemove}
                      title={`Remove ${c.brand_name}`}
                      onClick={() => handleRemoveCompetitor(i)}
                    >
                      &times;
                    </button>
                  </div>
                ))}

                {competitors.length < 5 && (
                  <button
                    type="button"
                    className={styles.addCompetitorBtn}
                    title="Add competitor"
                    onClick={() => setShowAddCompetitor(true)}
                  >
                    +
                  </button>
                )}
              </div>

              {/* Inline Add Competitor Form */}
              {showAddCompetitor && (
                <div className={styles.inlineAddCard}>
                  <div className={styles.twoColGrid} style={{ margin: 0 }}>
                    <div className={styles.fieldGroup}>
                      <label className={styles.fieldLabel}>Competitor Brand Name</label>
                      <input
                        type="text"
                        className={styles.textInput}
                        placeholder="e.g. Porsche"
                        value={newCompName}
                        onChange={(e) => setNewCompName(e.target.value)}
                        autoFocus
                      />
                    </div>
                    <div className={styles.fieldGroup}>
                      <label className={styles.fieldLabel}>Competitor Website URL</label>
                      <input
                        type="text"
                        className={styles.textInput}
                        placeholder="https://www.porsche.com"
                        value={newCompUrl}
                        onChange={(e) => setNewCompUrl(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className={styles.inlineAddActions}>
                    <button
                      type="button"
                      className={styles.inlineCancelBtn}
                      onClick={() => { setShowAddCompetitor(false); setNewCompName(''); setNewCompUrl(''); }}
                    >
                      Cancel
                    </button>
                    <button
                      type="button"
                      className={styles.inlineSaveBtn}
                      onClick={handleSaveNewCompetitor}
                      disabled={!newCompName.trim()}
                    >
                      Add Competitor
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* User Context Card (Collapsible) */}
          <div className={styles.card}>
            <div
              className={`${styles.cardHeaderRow} ${styles.accordionHeader}`}
              onClick={() => setUserContextOpen(!userContextOpen)}
            >
              <div className={styles.cardHeaderLeft}>
                <div className={styles.cardIconBox}>
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
                </div>
                <div>
                  <h3 className={styles.cardTitle}>User Context</h3>
                  <p className={styles.cardSubtitle}>
                    Give additional context to enhance the prompt...
                  </p>
                </div>
              </div>

              <div className={`${styles.accordionChevron} ${userContextOpen ? styles.accordionChevronOpen : ''}`}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </div>
            </div>

            {userContextOpen && (
              <div className={styles.accordionBody}>
                <textarea
                  className={styles.textarea}
                  placeholder="Give additional context or specific instructions to enhance the strategy output..."
                  value={userContext}
                  onChange={(e) => onChangeUserContext(e.target.value)}
                />
              </div>
            )}
          </div>
        </>
      )}

      {/* ── TAB 2: Strategy Preferences ── */}
      {activeTab === 'strategy_preferences' && (
        <div className={styles.card}>
          <div className={styles.cardHeaderRow} style={{ marginBottom: '20px' }}>
            <div className={styles.cardHeaderLeft}>
              <div className={styles.cardIconBox}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="4" y1="21" x2="4" y2="14" />
                  <line x1="4" y1="10" x2="4" y2="3" />
                  <line x1="12" y1="21" x2="12" y2="12" />
                  <line x1="12" y1="8" x2="12" y2="3" />
                  <line x1="20" y1="21" x2="20" y2="16" />
                  <line x1="20" y1="12" x2="20" y2="3" />
                  <line x1="1" y1="14" x2="7" y2="14" />
                  <line x1="9" y1="8" x2="15" y2="8" />
                  <line x1="17" y1="16" x2="23" y2="16" />
                </svg>
              </div>
              <div>
                <h3 className={styles.cardTitle}>Strategy Preferences</h3>
                <p className={styles.cardSubtitle}>
                  Customize the strategic targets, channels, and delivery format for {selectedAgent}
                </p>
              </div>
            </div>
          </div>

          {/* Dynamic Questions or Defaults */}
          {questions && questions.length > 0 ? (
            questions.map((q, qIdx) => (
              <div key={qIdx} className={styles.questionBlock}>
                <h4 className={styles.questionTitle}>
                  <span>{q.question}</span>
                  {q.multiSelect && <span style={{ fontSize: '11px', color: '#9CA3AF', fontWeight: 400 }}>(Select all that apply)</span>}
                </h4>
                <div className={styles.optionsPills}>
                  {q.options.map((opt, optIdx) => {
                    const selected = isOptionSelected(q.question, opt);
                    return (
                      <button
                        key={optIdx}
                        type="button"
                        className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                        onClick={() => handleToggleQuestionOption(q.question, opt, q.multiSelect)}
                      >
                        {selected && <span className={styles.pillCheck}>✓</span>}
                        <span>{opt}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))
          ) : (
            <>
              {/* Default Strategy Questions */}
              <div className={styles.questionBlock}>
                <h4 className={styles.questionTitle}>Primary Strategic Goal</h4>
                <div className={styles.optionsPills}>
                  {DEFAULT_GOALS.map((goal, idx) => {
                    const selected = isOptionSelected('Primary Strategic Goal', goal);
                    return (
                      <button
                        key={idx}
                        type="button"
                        className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                        onClick={() => handleToggleQuestionOption('Primary Strategic Goal', goal, false)}
                      >
                        {selected && <span className={styles.pillCheck}>✓</span>}
                        <span>{goal}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className={styles.questionBlock}>
                <h4 className={styles.questionTitle}>Desired Deliverable Format</h4>
                <div className={styles.optionsPills}>
                  {DEFAULT_FORMATS.map((fmt, idx) => {
                    const selected = isOptionSelected('Desired Deliverable Format', fmt);
                    return (
                      <button
                        key={idx}
                        type="button"
                        className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                        onClick={() => handleToggleQuestionOption('Desired Deliverable Format', fmt, false)}
                      >
                        {selected && <span className={styles.pillCheck}>✓</span>}
                        <span>{fmt}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div className={styles.questionBlock}>
                <h4 className={styles.questionTitle}>Execution Horizon</h4>
                <div className={styles.optionsPills}>
                  {DEFAULT_TIMELINES.map((time, idx) => {
                    const selected = isOptionSelected('Execution Horizon', time);
                    return (
                      <button
                        key={idx}
                        type="button"
                        className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                        onClick={() => handleToggleQuestionOption('Execution Horizon', time, false)}
                      >
                        {selected && <span className={styles.pillCheck}>✓</span>}
                        <span>{time}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </>
          )}
        </div>
      )}

      {/* ── TAB 3: Target Audience ── */}
      {activeTab === 'target_audience' && (
        <div className={styles.card}>
          <div className={styles.cardHeaderRow} style={{ marginBottom: '20px' }}>
            <div className={styles.cardHeaderLeft}>
              <div className={styles.cardIconBox}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div>
                <h3 className={styles.cardTitle}>Target Audience</h3>
                <p className={styles.cardSubtitle}>
                  Define target market regions, core buyer personas, and audience demographics
                </p>
              </div>
            </div>
          </div>

          {/* Target Region */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>Target Market Region</h4>
            <div className={styles.optionsPills}>
              {DEFAULT_REGIONS.map((reg, idx) => {
                const selected = targetAudience.region === reg;
                return (
                  <button
                    key={idx}
                    type="button"
                    className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                    onClick={() => onChangeTargetAudience({ ...targetAudience, region: reg })}
                  >
                    {selected && <span className={styles.pillCheck}>✓</span>}
                    <span>{reg}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Buyer Personas / Segments */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>
              <span>Core Audience Segments</span>
              <span style={{ fontSize: '11px', color: '#9CA3AF', fontWeight: 400 }}>(Select all that apply)</span>
            </h4>
            <div className={styles.optionsPills}>
              {DEFAULT_SEGMENTS.map((seg, idx) => {
                const selected = (targetAudience.segments || []).includes(seg);
                return (
                  <button
                    key={idx}
                    type="button"
                    className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                    onClick={() => handleToggleAudienceSegment(seg)}
                  >
                    {selected && <span className={styles.pillCheck}>✓</span>}
                    <span>{seg}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Key Locations / Cities */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>Key Focus Cities / Geographies</h4>
            <input
              type="text"
              className={styles.textInput}
              placeholder="e.g. New York, London, Tokyo, Milan, Dubai, Mumbai"
              value={targetAudience.locations || ''}
              onChange={(e) => onChangeTargetAudience({ ...targetAudience, locations: e.target.value })}
            />
          </div>

          {/* Audience Notes */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>Customer Motivations & Pain Points</h4>
            <textarea
              className={styles.textarea}
              placeholder="Describe what drives your audience, key objections, and why they choose your brand over competitors..."
              value={targetAudience.notes || ''}
              onChange={(e) => onChangeTargetAudience({ ...targetAudience, notes: e.target.value })}
            />
          </div>
        </div>
      )}

      {/* ── TAB 4: Additional Info ── */}
      {activeTab === 'additional_info' && (
        <div className={styles.card}>
          <div className={styles.cardHeaderRow} style={{ marginBottom: '20px' }}>
            <div className={styles.cardHeaderLeft}>
              <div className={styles.cardIconBox}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" />
                  <line x1="16" y1="17" x2="8" y2="17" />
                  <polyline points="10 9 9 9 8 9" />
                </svg>
              </div>
              <div>
                <h3 className={styles.cardTitle}>Additional Info & Guidelines</h3>
                <p className={styles.cardSubtitle}>
                  Add extra strategic guidelines, reference documents, and brand assets
                </p>
              </div>
            </div>
          </div>

          {/* Strategic Guardrails */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>Strategic Guardrails & Specific Instructions</h4>
            <textarea
              className={styles.textarea}
              placeholder="e.g. Moving to premium positioning; BFSI compliance rules; Avoid competitor direct attacks; Prioritize luxury lifestyle branding..."
              value={additionalNotes}
              onChange={(e) => onChangeAdditionalNotes(e.target.value)}
            />
          </div>

          {/* Reference Files */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>Supporting Reference Documents</h4>
            <input
              ref={fileInputRef}
              type="file"
              multiple
              style={{ display: 'none' }}
              onChange={(e) => {
                if (e.target.files) {
                  onAddFiles(Array.from(e.target.files));
                }
              }}
            />
            <button
              type="button"
              className={styles.fileUploadBtn}
              onClick={() => fileInputRef.current?.click()}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Upload Reference File (PDF, DOCX, TXT)
            </button>

            {attachedFiles.length > 0 && (
              <div className={styles.filesList}>
                {attachedFiles.map((file, idx) => (
                  <div key={idx} className={styles.fileItem}>
                    <div className={styles.fileItemLeft}>
                      <span>📄</span>
                      <span>{file.name}</span>
                      <span style={{ color: '#9CA3AF', fontSize: '11px' }}>
                        ({(file.size / 1024).toFixed(1)} KB)
                      </span>
                    </div>
                    <button
                      type="button"
                      className={styles.fileItemRemove}
                      onClick={() => onRemoveFile(idx)}
                      title="Remove file"
                    >
                      &times;
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
