'use client';

import { useState, useRef } from 'react';
import { useRouter } from 'next/navigation';
import styles from './page.module.css';

export default function StrategySetup() {
  const router = useRouter();

  // ── Step 1 state ──────────────────────────────────────────────────────────
  const [brandName, setBrandName] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [category, setCategory] = useState('');
  const [brandContext, setBrandContext] = useState('');
  const [competitorName, setCompetitorName] = useState('');
  const [competitorUrl, setCompetitorUrl] = useState('');
  const [competitors, setCompetitors] = useState<{ name: string; url?: string }[]>([]);

  // ── Validation errors ─────────────────────────────────────────────────────
  const [errors, setErrors] = useState<Record<string, string>>({});

  // ── Refs for scrolling to error fields ───────────────────────────────────
  const brandNameRef = useRef<HTMLInputElement>(null);
  const websiteUrlRef = useRef<HTMLInputElement>(null);
  const categoryRef = useRef<HTMLSelectElement>(null);
  const brandContextRef = useRef<HTMLTextAreaElement>(null);

  const handleAddCompetitor = () => {
    if (!competitorName.trim()) return;
    setCompetitors(prev => [...prev, { name: competitorName.trim(), url: competitorUrl.trim() || undefined }]);
    setCompetitorName('');
    setCompetitorUrl('');
  };

  const handleRemoveCompetitor = (index: number) => {
    setCompetitors(prev => prev.filter((_, i) => i !== index));
  };

  const handleSubmit = () => {
    const newErrors: Record<string, string> = {};
    if (!brandName.trim()) { newErrors.brandName = 'This field is mandatory'; brandNameRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    if (!websiteUrl.trim()) { newErrors.websiteUrl = 'This field is mandatory'; if (!newErrors.brandName) websiteUrlRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    if (!category) { newErrors.category = 'This field is mandatory'; if (!newErrors.brandName && !newErrors.websiteUrl) categoryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) return;

    // Auto-add any pending competitor input if name was typed
    let finalCompetitors = [...competitors];
    if (competitorName.trim()) {
      finalCompetitors.push({ name: competitorName.trim(), url: competitorUrl.trim() || undefined });
    }

    // Save data to localStorage
    const onboardingConfig = {
      brandName,
      websiteUrl,
      category,
      brandContext,
      competitors: finalCompetitors,
      submittedAt: new Date().toISOString()
    };
    try {
      localStorage.setItem('stratai_onboarding_config', JSON.stringify(onboardingConfig));
    } catch (e) {
      console.error('Failed to save onboarding config:', e);
    }

    router.push('/build');
  };

  return (
    <main className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>New Brand Research</h1>
        <p className={styles.subtitle}>Fill in brand details to generate strategic intelligence</p>
      </div>

      <div className={styles.card}>
        <div>
          <div className={styles.cardHeader}>
            <div className={styles.iconWrapper}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/>
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
              </svg>
            </div>
            <div>
              <h2 className={styles.cardTitle}>Brand Basics</h2>
              <p className={styles.cardSubtitle}>Tell us about your brand</p>
            </div>
          </div>

          {/* Brand Name */}
          <div className={styles.formGroup}>
            <label className={styles.label}>Brand Name <span className={styles.required}>*</span></label>
            <input
              ref={brandNameRef}
              className={`${styles.input} ${errors.brandName ? styles.inputError : ''}`}
              value={brandName}
              onChange={e => { setBrandName(e.target.value); setErrors(p => ({ ...p, brandName: '' })); }}
              placeholder="e.g. StratAI"
            />
            {errors.brandName && <span className={styles.errorMsg}>{errors.brandName}</span>}
          </div>

          {/* Website URL */}
          <div className={styles.formGroup}>
            <label className={styles.label}>Website URL <span className={styles.required}>*</span></label>
            <input
              ref={websiteUrlRef}
              className={`${styles.input} ${errors.websiteUrl ? styles.inputError : ''}`}
              value={websiteUrl}
              onChange={e => { setWebsiteUrl(e.target.value); setErrors(p => ({ ...p, websiteUrl: '' })); }}
              placeholder="https://www.yourbrand.com/"
            />
            {errors.websiteUrl && <span className={styles.errorMsg}>{errors.websiteUrl}</span>}
          </div>

          {/* Category */}
          <div className={styles.formGroup}>
            <label className={styles.label}>Category <span className={styles.required}>*</span></label>
            <select
              ref={categoryRef}
              className={`${styles.select} ${errors.category ? styles.inputError : ''}`}
              value={category}
              onChange={e => { setCategory(e.target.value); setErrors(p => ({ ...p, category: '' })); }}
            >
              <option value="">Select category...</option>
              <option value="Real Estate">Real Estate</option>
              <option value="Technology">Technology</option>
              <option value="Healthcare">Healthcare</option>
              <option value="E-commerce">E-commerce</option>
              <option value="Finance">Finance</option>
              <option value="Education">Education</option>
              <option value="Retail">Retail</option>
              <option value="Manufacturing">Manufacturing</option>
              <option value="FMCG">FMCG</option>
              <option value="Hospitality">Hospitality</option>
              <option value="Media & Entertainment">Media & Entertainment</option>
              <option value="Other">Other</option>
            </select>
            {errors.category && <span className={styles.errorMsg}>{errors.category}</span>}
          </div>

          {/* Brand Context / Details */}
          <div className={styles.formGroup}>
            <label className={styles.label}>Brand Context (Tone, Mission, Vision, or Direction) (Optional)</label>
            <textarea
              ref={brandContextRef}
              className={styles.textarea}
              value={brandContext}
              onChange={e => setBrandContext(e.target.value)}
              placeholder="Describe your brand's tone, mission, vision, or the direction in which you want to move forward..."
              rows={4}
            />
          </div>

          {/* Competitors */}
          <div className={styles.formGroup}>
            <label className={styles.label}>Competitors (Optional)</label>
            <div className={styles.competitorRow}>
              <input 
                className={styles.input} 
                placeholder="Competitor Name" 
                value={competitorName} 
                onChange={e => setCompetitorName(e.target.value)} 
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddCompetitor(); } }}
              />
              <input 
                className={styles.input} 
                placeholder="Website Link (Optional)" 
                value={competitorUrl} 
                onChange={e => setCompetitorUrl(e.target.value)} 
                onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddCompetitor(); } }}
              />
              <button type="button" className={styles.addBtn} onClick={handleAddCompetitor}>Add</button>
            </div>
            
            {competitors.length > 0 && (
              <div className={styles.competitorsList}>
                {competitors.map((comp, idx) => (
                  <div key={idx} className={styles.competitorChip}>
                    <span className={styles.competitorChipText}>
                      {comp.name} {comp.url ? `(${comp.url})` : ''}
                    </span>
                    <button 
                      type="button" 
                      className={styles.deleteChipBtn} 
                      onClick={() => handleRemoveCompetitor(idx)}
                      title="Remove competitor"
                    >
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="18" y1="6" x2="6" y2="18" />
                        <line x1="6" y1="6" x2="18" y2="18" />
                      </svg>
                    </button>
                  </div>
                ))}
              </div>
            )}
            <p className={styles.helpText}>Press Enter in either field or click Add to save a competitor.</p>
          </div>

          <div className={styles.footer}>
            <button className={styles.backBtn} onClick={() => router.push('/')}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
              </svg>
              Back
            </button>
            <button className={styles.continueBtn} onClick={handleSubmit}>
              CONTINUE
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
              </svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
