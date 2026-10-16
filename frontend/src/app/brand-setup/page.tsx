'use client';

import { useState, useRef, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from './page.module.css';

function StrategySetupInner() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const isNewProject = searchParams.get('new') === 'true';
  const [checkingFirstTime, setCheckingFirstTime] = useState(true);

  useEffect(() => {
    const checkFirstTimeUser = async () => {
      if (isNewProject) {
        setCheckingFirstTime(false);
        return;
      }
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = localStorage.getItem('access_token');
      if (!token) {
        router.push('/auth');
        return;
      }
      try {
        const res = await fetch(`${apiBase}/api/brands/`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        });
        if (res.status === 401) {
          localStorage.removeItem('access_token');
          router.push('/auth');
          return;
        }
        if (res.ok) {
          // Allow user to stay on brand-setup even if they have brands (linear backwards step support)
          const brands = await res.json();
        }
      } catch (err) {
        console.error('Failed to check first-time status:', err);
      } finally {
        setCheckingFirstTime(false);
      }
    };
    checkFirstTimeUser();
  }, [router]);

  // ── Step 1 state ──────────────────────────────────────────────────────────
  const [step, setStep] = useState<'form' | 'loading' | 'confirm_competitors'>('form');
  const [brandName, setBrandName] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [category, setCategory] = useState('');
  const [brandContext, setBrandContext] = useState('');
  const [competitorName, setCompetitorName] = useState('');
  const [competitorUrl, setCompetitorUrl] = useState('');
  const [competitors, setCompetitors] = useState<{ name: string; url?: string }[]>([]);

  // ── Candidates state ──────────────────────────────────────────────────────
  const [discoveredBrandHandle, setDiscoveredBrandHandle] = useState('');
  const [candidates, setCandidates] = useState<{ name: string; website_url: string; handle: string; source: string; selected: boolean }[]>([]);
  const [newCompName, setNewCompName] = useState('');
  const [newCompWebsite, setNewCompWebsite] = useState('');
  const [tavilyError, setTavilyError] = useState('');

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

  const handleAddConfirmedCompetitor = () => {
    if (!newCompName.trim()) return;
    setCandidates(prev => [
      ...prev,
      {
        name: newCompName.trim(),
        website_url: newCompWebsite.trim(),
        handle: newCompName.trim().replace(' ', '').toLowerCase(),
        source: 'user',
        selected: true
      }
    ]);
    setNewCompName('');
    setNewCompWebsite('');
  };

  const handleToggleCandidate = (idx: number) => {
    setCandidates(prev =>
      prev.map((c, i) => (i === idx ? { ...c, selected: !c.selected } : c))
    );
  };

  const handleEditWebsite = (idx: number, newUrl: string) => {
    setCandidates(prev =>
      prev.map((c, i) => (i === idx ? { ...c, website_url: newUrl } : c))
    );
  };

  const handleRemoveCandidate = (idx: number) => {
    setCandidates(prev => prev.filter((_, i) => i !== idx));
  };

  const handleSubmit = async () => {
    const newErrors: Record<string, string> = {};
    if (!brandName.trim()) { newErrors.brandName = 'This field is mandatory'; brandNameRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    if (!websiteUrl.trim()) { newErrors.websiteUrl = 'This field is mandatory'; if (!newErrors.brandName) websiteUrlRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    if (!category) { newErrors.category = 'This field is mandatory'; if (!newErrors.brandName && !newErrors.websiteUrl) categoryRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
    setErrors(newErrors);
    if (Object.keys(newErrors).length > 0) return;

    let finalCompetitors = [...competitors];
    if (competitorName.trim()) {
      finalCompetitors.push({ name: competitorName.trim(), url: competitorUrl.trim() || undefined });
    }

    setStep('loading');

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      const res = await fetch(`${apiBase}/api/brands/search-competitors`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          brand_name: brandName,
          website_url: websiteUrl,
          category,
          user_competitors: finalCompetitors.map(c => ({ name: c.name, url: c.url || '' }))
        })
      });

      if (res.status === 401) {
        localStorage.removeItem('access_token');
        router.push('/auth');
        return;
      }
      if (!res.ok) throw new Error('Failed to search competitors');
      const data = await res.json();
      setDiscoveredBrandHandle(data.brand_handle || brandName.replace(/\s/g, '').toLowerCase());
      setTavilyError(data.tavily_error || '');

      const mapped = (data.candidates || []).map((c: any) => ({
        name: c.name || '',
        website_url: c.website_url || '',
        handle: c.handle || c.name?.replace(/\s/g, '').toLowerCase() || '',
        source: c.source || 'tavily',
        selected: true
      }));
      setCandidates(mapped);
      setStep('confirm_competitors');
    } catch (e: any) {
      console.error('Search competitors error:', e);
      alert(`Error searching competitors: ${e.message}`);
      setStep('form');
    }
  };

  const handleFinalConfirm = async () => {
    const selectedComps = candidates.filter(c => c.selected);
    if (selectedComps.length === 0) {
      alert("Please select or add at least one competitor to analyze.");
      return;
    }

    const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;

    try {
      // Single confirm call — creates brand + project + launches research pipeline in background
      const confirmRes = await fetch(`${apiBase}/api/brands/confirm`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          brand_name: brandName,
          website_url: websiteUrl,
          category,
          brand_context: brandContext,
          brand_handle: discoveredBrandHandle,
          selected_competitors: selectedComps.map(c => ({
            name: c.name,
            website_url: c.website_url || '',
            handle: c.handle || ''
          }))
        })
      });

      if (confirmRes.status === 401) {
        localStorage.removeItem('access_token');
        router.push('/auth');
        return;
      }
      if (!confirmRes.ok) throw new Error('Failed to confirm brand setup');
      const brandData = await confirmRes.json();
      localStorage.setItem('brand_config_id', brandData.id);

      // Redirect immediately — pipeline runs in the background
      router.push('/build');
    } catch (e: any) {
      console.error('Final confirmation error:', e);
      alert(`Error confirming configuration: ${e.message}`);
    }
  };

  if (checkingFirstTime) {
    return (
      <main className={styles.container} style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', color: '#fff' }}>
        <p>Checking authentication and profile status...</p>
      </main>
    );
  }

  return (
    <main className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>New Brand Research</h1>
        <p className={styles.subtitle}>
          {step === 'form' && "Fill in brand details to generate strategic intelligence"}
          {step === 'loading' && "Analysing brand and fetching competitor profiles"}
          {step === 'confirm_competitors' && "Confirm the competitor list for deep scraping"}
        </p>
      </div>

      <div className={styles.card}>
        {step === 'form' && (
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
                <option value="Technology & Software">Technology & Software</option>
                <option value="Consumer Electronics">Consumer Electronics</option>
                <option value="SaaS (Software as a Service)">SaaS (Software as a Service)</option>
                <option value="Healthcare & Life Sciences">Healthcare & Life Sciences</option>
                <option value="E-commerce">E-commerce</option>
                <option value="D2C (Direct-to-Consumer)">D2C (Direct-to-Consumer)</option>
                <option value="Financial Services & Fintech">Financial Services & Fintech</option>
                <option value="Education & EdTech">Education & EdTech</option>
                <option value="Retail">Retail</option>
                <option value="Manufacturing & Industrial">Manufacturing & Industrial</option>
                <option value="FMCG & Consumer Goods">FMCG & Consumer Goods</option>
                <option value="Hospitality & Events">Hospitality & Events</option>
                <option value="Travel & Tourism">Travel & Tourism</option>
                <option value="Media & Entertainment">Media & Entertainment</option>
                <option value="Automotive & Mobility">Automotive & Mobility</option>
                <option value="Professional Services (B2B)">Professional Services (B2B)</option>
                <option value="Marketing & Advertising">Marketing & Advertising</option>
                <option value="Wellness, Health & Fitness">Wellness, Health & Fitness</option>
                <option value="Food & Beverage">Food & Beverage</option>
                <option value="Fashion & Beauty">Fashion & Beauty</option>
                <option value="Non-Profit / NGO">Non-Profit / NGO</option>
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
              <button className={styles.backBtn} onClick={() => router.push('/strategy-setup')}>
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
        )}

        {step === 'loading' && (
          <div className={styles.loadingScreen}>
            <div className={styles.spinner} />
            <h3 className={styles.loadingText}>FETCHING YOUR COMPETITORS AND ANALYSING THE BRAND DETAILS</h3>
            <p className={styles.helpText} style={{ marginTop: '16px' }}>Tavily is looking up your market space and identifying official social media handles. Please wait...</p>
          </div>
        )}

        {step === 'confirm_competitors' && (
          <div>
            <div className={styles.cardHeader}>
              <div className={styles.iconWrapper}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div>
                <h2 className={styles.cardTitle}>Review Competitors</h2>
                <p className={styles.confirmSectionSubtitle}>Select the competitors you want to include in your strategy analysis. You can also customize their Instagram handles.</p>
              </div>
            </div>

            {/* Tavily error / quota warning banner */}
            {tavilyError && (
              <div className={styles.tavilyErrorBanner}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0 }}>
                  <circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span>
                  <strong>Tavily search unavailable</strong> — your API plan limit may have been reached.
                  Competitors could not be auto-discovered. You can manually add competitors below.
                </span>
              </div>
            )}

            <div className={styles.candidateGrid}>
              {candidates.length === 0 && (
                <div className={styles.noCandidatesMsg}>
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="1.5">
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                  <p>No competitors found automatically. Add them manually below.</p>
                </div>
              )}

              {candidates.map((cand, idx) => (
                <div 
                  key={idx} 
                  className={`${styles.candidateCard} ${cand.selected ? styles.candidateCardSelected : ''}`}
                  onClick={() => handleToggleCandidate(idx)}
                >
                  <input 
                    type="checkbox"
                    checked={cand.selected}
                    onChange={() => {}} // Handled by card click
                    className={styles.checkboxInput}
                    onClick={(e) => e.stopPropagation()}
                  />
                  <div className={styles.candidateDetails}>
                    <div className={styles.candidateHeader}>
                      <span className={styles.candidateName}>{cand.name}</span>
                      <span className={`${styles.candidateSourceBadge} ${cand.source === 'user' ? styles.badgeUser : styles.badgeTavily}`}>
                        {cand.source === 'user' ? 'Added by you' : 'Suggested'}
                      </span>
                    </div>
                    <div onClick={(e) => e.stopPropagation()} style={{ width: '100%' }}>
                      {cand.website_url ? (
                        <a
                          href={cand.website_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className={styles.candidateWebsiteLink}
                          onClick={(e) => e.stopPropagation()}
                        >
                          <svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" style={{ marginRight: 4, flexShrink: 0 }}>
                            <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/>
                            <polyline points="15 3 21 3 21 9"/>
                            <line x1="10" y1="14" x2="21" y2="3"/>
                          </svg>
                          {cand.website_url.replace(/^https?:\/\/(www\.)?/, '').split('/')[0]}
                        </a>
                      ) : (
                        <input
                          type="text"
                          value={cand.website_url}
                          onChange={(e) => handleEditWebsite(idx, e.target.value)}
                          placeholder="https://competitor.com"
                          className={styles.candidateHandleInput}
                        />
                      )}
                    </div>
                  </div>
                  <button 
                    type="button"
                    className={styles.removeCandidateBtn}
                    onClick={(e) => {
                      e.stopPropagation();
                      handleRemoveCandidate(idx);
                    }}
                    title="Delete suggestion"
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>
                    </svg>
                  </button>
                </div>
              ))}
            </div>

            {/* Add Competitor inline */}
            <div className={styles.addCandidateForm}>
              <h4 className={styles.addCandidateTitle}>Add Another Competitor</h4>
              <div className={styles.addCandidateFields}>
                <input 
                  type="text"
                  placeholder="Competitor Name (e.g. Adidas)"
                  value={newCompName}
                  onChange={(e) => setNewCompName(e.target.value)}
                  className={styles.input}
                />
                <input 
                  type="text"
                  placeholder="Website URL (e.g. https://adidas.com)"
                  value={newCompWebsite}
                  onChange={(e) => setNewCompWebsite(e.target.value)}
                  className={styles.input}
                />
                <button 
                  type="button" 
                  onClick={handleAddConfirmedCompetitor}
                  className={styles.addBtn}
                >
                  Add
                </button>
              </div>
            </div>

            <div className={styles.footer}>
              <button className={styles.backBtn} onClick={() => setStep('form')}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
                </svg>
                Back
              </button>
              <button className={styles.continueBtn} onClick={handleFinalConfirm}>
                CONFIRM AND START RESEARCH
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </button>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}

export default function StrategySetup() {
  return (
    <Suspense fallback={
      <main className={styles.container} style={{ display: 'flex', justifyContent: 'center', alignItems: 'center', minHeight: '100vh', color: '#fff' }}>
        <p>Loading setup...</p>
      </main>
    }>
      <StrategySetupInner />
    </Suspense>
  );
}
