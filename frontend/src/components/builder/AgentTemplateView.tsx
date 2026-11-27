'use client';
import { useState, useRef, useEffect } from 'react';
import { getAgentIcon } from '../../data/agentIcons';
import FileIcon from '../FileIcon';
import styles from './AgentTemplateView.module.css';
import { type CompetitorDetail, type CompetitorSocialMedia } from '../CompetitorForm';
import BrandKitForm, { type BrandKit } from '../BrandKitForm';
import { BRAND_CATEGORIES, TARGET_MARKET_REGIONS } from '../../data/brandOptions';

export interface TargetAudienceData {
  region?: string;
  segments?: string[];
  locations?: string;
  notes?: string;
  ageDemographics?: string[];
  incomeTier?: string;
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
    target_market?: { region?: string | null; cities?: string[]; custom_region?: string | null } | null;
    additional_notes?: string;
    brand_brief?: { tone_of_voice?: string; target_audience?: string; [key: string]: string | undefined };
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
  brandKit?: BrandKit;
  onChangeBrandKit?: (bk: BrandKit) => void;
  apiBase?: string;
  authToken?: string;
  attachedFiles: File[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
}

const TABS = [
  { id: 'brand_details', label: 'Brand Details' },
  { id: 'competitor', label: 'Competitor' },
  { id: 'brand_kit', label: 'Brand Kit' },
  { id: 'strategy_preferences', label: 'Strategy Preferences' },
  { id: 'target_audience', label: 'Target Audience' },
  { id: 'additional_info', label: 'Additional Info' },
] as const;

type TabId = typeof TABS[number]['id'];

// Mirrors CompetitorForm.tsx's SOCIAL_FIELDS exactly — same field set/order,
// reused here so the Competitor tab's per-competitor social inputs match
// the gated-off form's layout.
const SOCIAL_FIELDS: { key: keyof CompetitorSocialMedia; label: string; placeholder: string }[] = [
  { key: 'linkedin', label: 'LinkedIn', placeholder: 'https://linkedin.com/company/...' },
  { key: 'instagram', label: 'Instagram', placeholder: 'https://instagram.com/...' },
  { key: 'facebook', label: 'Facebook', placeholder: 'https://facebook.com/...' },
  { key: 'twitter', label: 'Twitter/X', placeholder: 'https://x.com/...' },
  { key: 'youtube', label: 'YouTube', placeholder: 'https://youtube.com/@...' },
];

const DEFAULT_SEGMENTS = [
  'B2B Enterprise Leaders', 'High Net Worth Individuals', 'Tech & Product Innovators', 'Gen Z & Millennials',
  'Small Business Owners', 'Industry Specialists', 'Mass Market Shoppers', 'Early Adopters'
];

const DEFAULT_GOALS = [
  'Brand Awareness', 'Lead Generation', 'Market Expansion', 'Sales & Revenue Growth',
  'Competitive Positioning', 'Customer Retention', 'Thought Leadership'
];

const DEFAULT_PLATFORMS = [
  'Instagram', 'LinkedIn', 'X (Twitter)', 'TikTok', 'YouTube', 'Facebook'
];

const DEFAULT_CONTENT_FORMATS = [
  'Short-Form Video / Reels', 'Carousels & Slide Decks', 'Thought Leadership & Text', 'Infographics & Visuals', 'Stories & Community Polls'
];

const DEFAULT_FORMATS = [
  'Executive Summary', 'Detailed Strategic Plan', 'Step-by-Step Playbook', 'Comprehensive Competitive Audit'
];

const DEFAULT_TIMELINES = [
  'Immediate (30 Days)', 'Quarterly (90 Days)', '6-Month Implementation', '1-Year Strategic Horizon'
];

const DEFAULT_AGE_DEMOGRAPHICS = [
  'Gen Z (18-24)', 'Young Professionals (25-34)', 'Mid-Career & Execs (35-49)', 'Senior Decision-Makers (50+)'
];

const DEFAULT_INCOME_TIERS = [
  'Budget / Value Focused', 'Mass Market', 'Upper-Middle / Affluent', 'High-Net-Worth / Luxury'
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
  apiBase,
  authToken,
  attachedFiles,
  onAddFiles,
  onRemoveFile,
}: AgentTemplateViewProps) {
  const [activeTab, setActiveTab] = useState<TabId>('brand_details');
  const [userContextOpen, setUserContextOpen] = useState(false);
  const [brandNameDraft, setBrandNameDraft] = useState(brand?.brand_name || '');
  const [websiteDraft, setWebsiteDraft] = useState(brand?.website_url || '');

  useEffect(() => {
    setBrandNameDraft(brand?.brand_name || '');
    setWebsiteDraft(brand?.website_url || '');
  }, [brand?.id, brand?.brand_name, brand?.website_url]);

  // Dynamic add states for customization
  const [availableSegments, setAvailableSegments] = useState<string[]>(DEFAULT_SEGMENTS);
  const [showAddSegment, setShowAddSegment] = useState(false);
  const [newSegmentName, setNewSegmentName] = useState('');

  const [availableGoals, setAvailableGoals] = useState<string[]>(DEFAULT_GOALS);
  const [showAddGoal, setShowAddGoal] = useState(false);
  const [newGoalName, setNewGoalName] = useState('');

  const [availablePlatforms, setAvailablePlatforms] = useState<string[]>(DEFAULT_PLATFORMS);
  const [showAddPlatform, setShowAddPlatform] = useState(false);
  const [newPlatformName, setNewPlatformName] = useState('');

  const [availableIndustries, setAvailableIndustries] = useState<string[]>([...BRAND_CATEGORIES]);
  const [showAddIndustry, setShowAddIndustry] = useState(false);
  const [newIndustryName, setNewIndustryName] = useState('');

  // Inline add competitor state
  const [showAddCompetitor, setShowAddCompetitor] = useState(false);
  const [newCompName, setNewCompName] = useState('');
  const [newCompUrl, setNewCompUrl] = useState('');
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Which existing competitor's Social Media Links section is expanded —
  // one at a time, mirroring the gated CompetitorForm's per-card toggle.
  const [openSocialIdx, setOpenSocialIdx] = useState<number | null>(null);

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

  // Edit an existing competitor's brand_name/website_url in place.
  const handleUpdateCompetitorField = (index: number, field: 'brand_name' | 'website_url', value: string) => {
    onUpdateCompetitors(competitors.map((c, i) => (i === index ? { ...c, [field]: value } : c)));
  };

  // Edit an existing competitor's social_media handles in place.
  const handleUpdateCompetitorSocial = (index: number, key: keyof CompetitorSocialMedia, value: string) => {
    onUpdateCompetitors(
      competitors.map((c, i) => (i === index ? { ...c, social_media: { ...c.social_media, [key]: value } } : c))
    );
  };

  const handleAddCustomSegment = () => {
    const trimmed = newSegmentName.trim();
    if (!trimmed) return;
    if (!availableSegments.includes(trimmed)) {
      setAvailableSegments(prev => [...prev, trimmed]);
    }
    const current = targetAudience.segments || [];
    if (!current.includes(trimmed)) {
      onChangeTargetAudience({ ...targetAudience, segments: [...current, trimmed] });
    }
    setNewSegmentName('');
    setShowAddSegment(false);
  };

  const handleAddCustomGoal = () => {
    const trimmed = newGoalName.trim();
    if (!trimmed) return;
    if (!availableGoals.includes(trimmed)) {
      setAvailableGoals(prev => [...prev, trimmed]);
    }
    handleToggleQuestionOption('Primary Strategic Goal', trimmed, false);
    setNewGoalName('');
    setShowAddGoal(false);
  };

  const handleAddCustomPlatform = () => {
    const trimmed = newPlatformName.trim();
    if (!trimmed) return;
    if (!availablePlatforms.includes(trimmed)) {
      setAvailablePlatforms(prev => [...prev, trimmed]);
    }
    handleToggleQuestionOption('Target Platforms & Channels', trimmed, true);
    setNewPlatformName('');
    setShowAddPlatform(false);
  };

  const handleAddCustomIndustry = () => {
    const trimmed = newIndustryName.trim();
    if (!trimmed) return;
    if (!availableIndustries.includes(trimmed)) {
      setAvailableIndustries(prev => [...prev, trimmed]);
    }
    handleToggleQuestionOption('Brand Industry / Category', trimmed, false);
    setNewIndustryName('');
    setShowAddIndustry(false);
  };

  const handleToggleAgeDemographic = (age: string) => {
    const current = targetAudience.ageDemographics || [];
    const next = current.includes(age) ? current.filter(a => a !== age) : [...current, age];
    onChangeTargetAudience({ ...targetAudience, ageDemographics: next });
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

  // Raw (non-pill) qaAnswers read/write — used by Brand Voice & Tone, now a
  // free-text field rather than a pill row, while still riding the same
  // qaAnswers entry (and therefore the same R2b brand_descriptors.voice
  // plumbing in MainContent) that the pills used.
  const getQaAnswer = (questionText: string): string => {
    return qaAnswers.find(a => a.question === questionText)?.answer || '';
  };
  const setQaAnswer = (questionText: string, value: string) => {
    const updated = qaAnswers.filter(a => a.question !== questionText);
    if (value) updated.push({ question: questionText, answer: value });
    onUpdateQaAnswers(updated);
  };

  const handleToggleAudienceSegment = (seg: string) => {
    const current = targetAudience.segments || [];
    const next = current.includes(seg) ? current.filter(s => s !== seg) : [...current, seg];
    onChangeTargetAudience({ ...targetAudience, segments: next });
  };

  // One-time prefill from the brand's onboarding data, run when `brand.id`
  // becomes available/changes. Every individual write below is guarded by
  // "the field is still empty" — never an unconditional overwrite — so a
  // user's own edit (or a prior seed already sitting in qaAnswers/
  // targetAudience, which are lifted state owned by MainContent and so
  // survive switching tabs or even switching to a different template for
  // the same brand) is never clobbered on re-render. brand.additional_notes
  // is deliberately never read here — it's brand-level and already injected
  // into every prompt on its own; seeding it into the per-task guardrails
  // field would double it.
  useEffect(() => {
    if (!brand?.id) return;

    // Both qaAnswers seeds are collected into ONE onUpdateQaAnswers call —
    // onUpdateQaAnswers is MainContent's plain setQaAnswers, not a
    // functional updater, so two separate calls in the same tick would each
    // read the same pre-update qaAnswers closure and the second call would
    // silently clobber the first's addition.
    const qaSeeds: Array<{ question: string; answer: string }> = [];
    if (brand.category && !getQaAnswer('Brand Industry / Category')) {
      qaSeeds.push({ question: 'Brand Industry / Category', answer: brand.category });
    }
    if (brand.brand_brief?.tone_of_voice && !getQaAnswer('Brand Voice & Tone')) {
      qaSeeds.push({ question: 'Brand Voice & Tone', answer: brand.brand_brief.tone_of_voice });
    }
    if (qaSeeds.length > 0) {
      const seededQuestions = new Set(qaSeeds.map(s => s.question));
      onUpdateQaAnswers([...qaAnswers.filter(a => !seededQuestions.has(a.question)), ...qaSeeds]);
    }

    const tm = brand.target_market;
    const taUpdates: Partial<TargetAudienceData> = {};
    // targetAudience.region defaults to 'Global' (MainContent's useState
    // initializer) even on a tab the user never opened, so that silent
    // default — not just an empty string — counts as "still unset" here.
    if (tm?.region && (!targetAudience.region || targetAudience.region === 'Global')) {
      const matchedRegion = TARGET_MARKET_REGIONS.find(r => r.value === tm.region);
      if (matchedRegion) taUpdates.region = matchedRegion.label;
    }
    if (tm?.cities?.length && !targetAudience.locations) {
      taUpdates.locations = tm.cities.join(', ');
    }
    if (brand.brand_brief?.target_audience && !targetAudience.notes) {
      taUpdates.notes = brand.brand_brief.target_audience;
    }
    if (Object.keys(taUpdates).length > 0) {
      onChangeTargetAudience({ ...targetAudience, ...taUpdates });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brand?.id]);

  return (
    <div className={styles.container}>
      {/* ── Agent Header ── */}
      <div className={styles.headerRow}>
        <div className={styles.agentIconWrap}>
          {getAgentIcon(selectedAgent, '', 28)}
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

      {/* ── TAB: Competitor ── */}
      {activeTab === 'competitor' && (
        <div className={styles.card}>
          <div className={styles.cardHeaderRow}>
            <div className={styles.cardHeaderLeft}>
              <div className={styles.cardIconBox}>
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="20" x2="18" y2="10" />
                  <line x1="12" y1="20" x2="12" y2="4" />
                  <line x1="6" y1="20" x2="6" y2="14" />
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

          {/* About Your Competitors */}
          <div className={styles.competitorsSection}>
            {competitors.map((c, i) => (
              <div key={i} className={styles.inlineAddCard} style={{ marginTop: i === 0 ? 0 : 12 }}>
                <div className={styles.twoColGrid} style={{ margin: 0 }}>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>Competitor Brand Name</label>
                    <input
                      type="text"
                      className={styles.textInput}
                      placeholder="e.g. Porsche"
                      value={c.brand_name}
                      onChange={(e) => handleUpdateCompetitorField(i, 'brand_name', e.target.value)}
                    />
                  </div>
                  <div className={styles.fieldGroup}>
                    <label className={styles.fieldLabel}>Competitor Website URL</label>
                    <input
                      type="text"
                      className={styles.textInput}
                      placeholder="https://www.porsche.com"
                      value={c.website_url || ''}
                      onChange={(e) => handleUpdateCompetitorField(i, 'website_url', e.target.value)}
                    />
                  </div>
                </div>

                <button
                  type="button"
                  className={styles.addCustomPillBtn}
                  onClick={() => setOpenSocialIdx(openSocialIdx === i ? null : i)}
                >
                  <span>{openSocialIdx === i ? '▾' : '▸'}</span>
                  Social Media Links
                </button>

                {openSocialIdx === i && (
                  <div className={styles.twoColGrid} style={{ margin: 0 }}>
                    {SOCIAL_FIELDS.map(({ key, label, placeholder }) => (
                      <div className={styles.fieldGroup} key={key}>
                        <label className={styles.fieldLabel}>{label}</label>
                        <input
                          type="text"
                          className={styles.textInput}
                          placeholder={placeholder}
                          value={c.social_media?.[key] || ''}
                          onChange={(e) => handleUpdateCompetitorSocial(i, key, e.target.value)}
                        />
                      </div>
                    ))}
                  </div>
                )}

                <div className={styles.inlineAddActions}>
                  <button
                    type="button"
                    className={styles.inlineCancelBtn}
                    onClick={() => handleRemoveCompetitor(i)}
                  >
                    Remove Competitor
                  </button>
                </div>
              </div>
            ))}

            {showAddCompetitor ? (
              <div className={styles.inlineAddCard} style={{ marginTop: competitors.length === 0 ? 0 : 12 }}>
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
            ) : (
              competitors.length < 5 && (
                <button
                  type="button"
                  className={styles.addCustomPillBtn}
                  style={{ marginTop: competitors.length === 0 ? 0 : 12 }}
                  onClick={() => setShowAddCompetitor(true)}
                >
                  + Add Competitor
                </button>
              )
            )}
          </div>
        </div>
      )}

      {/* ── TAB 1: Brand Details ── */}
      {activeTab === 'brand_details' && (
        <>
          {/* Brand Details Card */}
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
                  <h3 className={styles.cardTitle}>Brand Details</h3>
                  <p className={styles.cardSubtitle}>
                    Your brand's identity, category, and voice
                  </p>
                </div>
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

            <div className={styles.sectionDivider} />

            {/* Brand Category & Industry */}
            <div className={styles.questionBlock}>
              <h4 className={styles.questionTitle}>
                <span>Brand Category / Industry</span>
              </h4>
              <div className={styles.optionsPills}>
                {availableIndustries.map((ind, idx) => {
                  const selected = isOptionSelected('Brand Industry / Category', ind);
                  return (
                    <button
                      key={idx}
                      type="button"
                      className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                      onClick={() => handleToggleQuestionOption('Brand Industry / Category', ind, false)}
                    >
                      {selected && <span className={styles.pillCheck}>✓</span>}
                      <span>{ind}</span>
                    </button>
                  );
                })}

                {showAddIndustry ? (
                  <div className={styles.inlineCustomInputWrap}>
                    <input
                      type="text"
                      className={styles.inlineCustomInput}
                      placeholder="e.g. EdTech"
                      value={newIndustryName}
                      onChange={(e) => setNewIndustryName(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter') handleAddCustomIndustry(); }}
                      autoFocus
                    />
                    <button type="button" className={styles.inlineCustomAddBtn} onClick={handleAddCustomIndustry}>
                      Add
                    </button>
                    <button type="button" className={styles.inlineCustomCancelBtn} onClick={() => { setShowAddIndustry(false); setNewIndustryName(''); }}>
                      &times;
                    </button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className={styles.addCustomPillBtn}
                    onClick={() => setShowAddIndustry(true)}
                  >
                    + Add Industry
                  </button>
                )}
              </div>
            </div>

            {/* Brand Voice & Tone */}
            <div className={styles.questionBlock}>
              <h4 className={styles.questionTitle}>
                <span>Brand Voice & Tone</span>
              </h4>
              <textarea
                className={styles.textarea}
                placeholder="e.g. Warm, reassuring and family-first; benefit-led rather than playful..."
                value={getQaAnswer('Brand Voice & Tone')}
                onChange={(e) => setQaAnswer('Brand Voice & Tone', e.target.value)}
              />
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

      {/* ── TAB: Brand Kit ── */}
      {activeTab === 'brand_kit' && (
        <BrandKitForm
          brandKit={brandKit ?? {}}
          onChange={(bk) => onChangeBrandKit?.(bk)}
          apiBase={apiBase}
          authToken={authToken}
        />
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
                  {availableGoals.map((goal, idx) => {
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

                  {showAddGoal ? (
                    <div className={styles.inlineCustomInputWrap}>
                      <input
                        type="text"
                        className={styles.inlineCustomInput}
                        placeholder="e.g. Virality & Reach"
                        value={newGoalName}
                        onChange={(e) => setNewGoalName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAddCustomGoal(); }}
                        autoFocus
                      />
                      <button type="button" className={styles.inlineCustomAddBtn} onClick={handleAddCustomGoal}>
                        Add
                      </button>
                      <button type="button" className={styles.inlineCustomCancelBtn} onClick={() => { setShowAddGoal(false); setNewGoalName(''); }}>
                        &times;
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className={styles.addCustomPillBtn}
                      onClick={() => setShowAddGoal(true)}
                    >
                      + Add Goal
                    </button>
                  )}
                </div>
              </div>

              {/* Target Platforms / Channels */}
              <div className={styles.questionBlock}>
                <h4 className={styles.questionTitle}>
                  <span>Target Platforms & Channels</span>
                  <span style={{ fontSize: '11px', color: '#9CA3AF', fontWeight: 400 }}>(Select all that apply)</span>
                </h4>
                <div className={styles.optionsPills}>
                  {availablePlatforms.map((platform, idx) => {
                    const selected = isOptionSelected('Target Platforms & Channels', platform);
                    return (
                      <button
                        key={idx}
                        type="button"
                        className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                        onClick={() => handleToggleQuestionOption('Target Platforms & Channels', platform, true)}
                      >
                        {selected && <span className={styles.pillCheck}>✓</span>}
                        <span>{platform}</span>
                      </button>
                    );
                  })}

                  {showAddPlatform ? (
                    <div className={styles.inlineCustomInputWrap}>
                      <input
                        type="text"
                        className={styles.inlineCustomInput}
                        placeholder="e.g. Pinterest"
                        value={newPlatformName}
                        onChange={(e) => setNewPlatformName(e.target.value)}
                        onKeyDown={(e) => { if (e.key === 'Enter') handleAddCustomPlatform(); }}
                        autoFocus
                      />
                      <button type="button" className={styles.inlineCustomAddBtn} onClick={handleAddCustomPlatform}>
                        Add
                      </button>
                      <button type="button" className={styles.inlineCustomCancelBtn} onClick={() => { setShowAddPlatform(false); setNewPlatformName(''); }}>
                        &times;
                      </button>
                    </div>
                  ) : (
                    <button
                      type="button"
                      className={styles.addCustomPillBtn}
                      onClick={() => setShowAddPlatform(true)}
                    >
                      + Add Platform
                    </button>
                  )}
                </div>
              </div>

              {/* Content Formats & Pillars Focus */}
              <div className={styles.questionBlock}>
                <h4 className={styles.questionTitle}>
                  <span>Content Format & Pillars Focus</span>
                  <span style={{ fontSize: '11px', color: '#9CA3AF', fontWeight: 400 }}>(Select all that apply)</span>
                </h4>
                <div className={styles.optionsPills}>
                  {DEFAULT_CONTENT_FORMATS.map((format, idx) => {
                    const selected = isOptionSelected('Content Format & Pillars Focus', format);
                    return (
                      <button
                        key={idx}
                        type="button"
                        className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                        onClick={() => handleToggleQuestionOption('Content Format & Pillars Focus', format, true)}
                      >
                        {selected && <span className={styles.pillCheck}>✓</span>}
                        <span>{format}</span>
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
              {TARGET_MARKET_REGIONS.map(({ value, label }) => {
                const selected = targetAudience.region === label;
                return (
                  <button
                    key={value}
                    type="button"
                    className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                    onClick={() => onChangeTargetAudience({ ...targetAudience, region: label })}
                  >
                    {selected && <span className={styles.pillCheck}>✓</span>}
                    <span>{label}</span>
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
              {availableSegments.map((seg, idx) => {
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

              {showAddSegment ? (
                <div className={styles.inlineCustomInputWrap}>
                  <input
                    type="text"
                    className={styles.inlineCustomInput}
                    placeholder="e.g. CMOs"
                    value={newSegmentName}
                    onChange={(e) => setNewSegmentName(e.target.value)}
                    onKeyDown={(e) => { if (e.key === 'Enter') handleAddCustomSegment(); }}
                    autoFocus
                  />
                  <button type="button" className={styles.inlineCustomAddBtn} onClick={handleAddCustomSegment}>
                    Add
                  </button>
                  <button type="button" className={styles.inlineCustomCancelBtn} onClick={() => { setShowAddSegment(false); setNewSegmentName(''); }}>
                    &times;
                  </button>
                </div>
              ) : (
                <button
                  type="button"
                  className={styles.addCustomPillBtn}
                  onClick={() => setShowAddSegment(true)}
                >
                  + Add Custom Segment
                </button>
              )}
            </div>
          </div>

          {/* Age Demographics */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>
              <span>Target Age Demographics</span>
              <span style={{ fontSize: '11px', color: '#9CA3AF', fontWeight: 400 }}>(Select all that apply)</span>
            </h4>
            <div className={styles.optionsPills}>
              {DEFAULT_AGE_DEMOGRAPHICS.map((age, idx) => {
                const selected = (targetAudience.ageDemographics || []).includes(age);
                return (
                  <button
                    key={idx}
                    type="button"
                    className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                    onClick={() => handleToggleAgeDemographic(age)}
                  >
                    {selected && <span className={styles.pillCheck}>✓</span>}
                    <span>{age}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Purchasing Power / Income Tier */}
          <div className={styles.questionBlock}>
            <h4 className={styles.questionTitle}>
              <span>Target Purchasing Power / Tier</span>
            </h4>
            <div className={styles.optionsPills}>
              {DEFAULT_INCOME_TIERS.map((tier, idx) => {
                const selected = targetAudience.incomeTier === tier;
                return (
                  <button
                    key={idx}
                    type="button"
                    className={`${styles.optionPill} ${selected ? styles.optionPillActive : ''}`}
                    onClick={() => onChangeTargetAudience({ ...targetAudience, incomeTier: tier })}
                  >
                    {selected && <span className={styles.pillCheck}>✓</span>}
                    <span>{tier}</span>
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
                      <FileIcon filename={file.name} mimeType={file.type} size={16} />
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
