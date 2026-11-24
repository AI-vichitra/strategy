'use client';

import { useState, useRef, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import styles from './page.module.css';
import BrandKitForm, { type BrandKit } from '../../components/BrandKitForm';
import ReferenceUpload, { type ReferenceDoc } from '../../components/ReferenceUpload';

// ── Target Market: structured region + city selection ───────────────────────
// Mirrors backend.schemas.brand.TargetMarket exactly. Region options and city
// lists are NEVER hardcoded here — they come from GET /target-market-config.
type TargetMarketRegion = 'local' | 'india' | 'us' | 'europe' | 'global' | 'other';

interface TargetMarket {
  region: TargetMarketRegion;
  cities: string[];
  custom_region?: string;
}

interface TargetMarketConfig {
  regions: { value: TargetMarketRegion; label: string }[];
  cities: Record<string, string[]>;
}

// Degraded fallback ONLY used when the config fetch fails — region options
// only (no curated city lists, since those must never be hardcoded here).
const TARGET_MARKET_FALLBACK_REGIONS: { value: TargetMarketRegion; label: string }[] = [
  { value: 'local', label: 'Local / City-specific' },
  { value: 'india', label: 'India' },
  { value: 'us', label: 'United States' },
  { value: 'europe', label: 'Europe' },
  { value: 'global', label: 'Global' },
  { value: 'other', label: 'Other' },
];

// ── Social Handles: multi-platform profile URLs ─────────────────────────────
// Mirrors backend.schemas.brand.SOCIAL_PLATFORMS exactly — never hardcoded
// independently of that closed set.
const SOCIAL_PLATFORMS = ['instagram', 'linkedin', 'x', 'youtube', 'facebook', 'tiktok'] as const;
type SocialPlatform = typeof SOCIAL_PLATFORMS[number];

const SOCIAL_PLATFORM_LABELS: Record<SocialPlatform, string> = {
  instagram: 'Instagram',
  linkedin: 'LinkedIn',
  x: 'X (Twitter)',
  youtube: 'YouTube',
  facebook: 'Facebook',
  tiktok: 'TikTok',
};

const SOCIAL_PLATFORM_ICONS: Record<SocialPlatform, React.ReactNode> = {
  instagram: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <defs>
        <radialGradient id="igIconGrad" cx="20%" cy="105%" r="130%">
          <stop offset="0%" stopColor="#fdf497" />
          <stop offset="10%" stopColor="#fdf497" />
          <stop offset="50%" stopColor="#fd5949" />
          <stop offset="70%" stopColor="#d6249f" />
          <stop offset="100%" stopColor="#285AEB" />
        </radialGradient>
      </defs>
      <rect width="24" height="24" rx="6" fill="url(#igIconGrad)" />
      <rect x="5.5" y="5.5" width="13" height="13" rx="3.5" stroke="#ffffff" strokeWidth="1.6" fill="none" />
      <circle cx="12" cy="12" r="3.2" stroke="#ffffff" strokeWidth="1.6" fill="none" />
      <circle cx="15.8" cy="8.2" r="0.9" fill="#ffffff" />
    </svg>
  ),
  linkedin: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect width="24" height="24" rx="5" fill="#0A66C2" />
      <circle cx="7.5" cy="7.5" r="1.5" fill="#ffffff" />
      <rect x="6" y="10" width="3" height="8" rx="0.5" fill="#ffffff" />
      <path d="M11 10h2.8v1.2c.4-.7 1.4-1.4 2.7-1.4 2.6 0 3.5 1.5 3.5 4v4.2h-3V14.3c0-1-.4-1.8-1.5-1.8s-1.5.8-1.5 1.8V18H11V10z" fill="#ffffff" />
    </svg>
  ),
  x: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect width="24" height="24" rx="5" fill="#000000" />
      <path d="M15.5 5.5h2l-4.4 5 5.2 6.9h-4l-3.2-4.2-3.6 4.2h-2l4.7-5.4L5.2 5.5h4.1l2.9 3.8 3.3-3.8zm-.7 10.7h1.1L8.5 6.6H7.3l7.5 9.6z" fill="#ffffff" />
    </svg>
  ),
  youtube: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect width="24" height="24" rx="5" fill="#FF0000" />
      <path d="M10 8.5l5.5 3.5-5.5 3.5V8.5z" fill="#ffffff" />
    </svg>
  ),
  facebook: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect width="24" height="24" rx="5" fill="#1877F2" />
      <path d="M15.5 12.5h-2.3V20h-3.1v-7.5H8.5V9.9h1.6V8.1c0-2.2 1.3-3.6 3.5-3.6 1 0 2 .1 2.2.1v2.5h-1.3c-1.1 0-1.4.5-1.4 1.3v1.5h2.7l-.3 2.6z" fill="#ffffff" />
    </svg>
  ),
  tiktok: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none">
      <rect width="24" height="24" rx="5" fill="#000000" />
      <path d="M15.2 6.2c.7.9 1.7 1.5 2.8 1.6v2.2c-1.1 0-2.1-.4-2.8-1.1v4.8c0 2.4-1.9 4.3-4.3 4.3S6.6 16.1 6.6 13.7s1.9-4.3 4.3-4.3c.3 0 .7 0 1 .1v2.3c-.3-.1-.6-.2-1-.2-1.2 0-2.1.9-2.1 2.1s.9 2.1 2.1 2.1 2.2-.9 2.2-2.1V5h2.1z" fill="#ffffff" />
    </svg>
  ),
};

// Domains that identify a profile URL for each platform (first = canonical
// domain used when the user types a bare handle, e.g. "@brand").
const SOCIAL_PLATFORM_DOMAINS: Record<SocialPlatform, string[]> = {
  instagram: ['instagram.com'],
  linkedin: ['linkedin.com'],
  x: ['x.com', 'twitter.com'],
  youtube: ['youtube.com', 'youtu.be'],
  facebook: ['facebook.com', 'fb.com'],
  tiktok: ['tiktok.com'],
};

// Accepts a bare handle ("@brand" / "brand"), or a full URL, for the given
// platform's row. Returns a canonical https URL (query/fragment stripped, no
// trailing slash) or an error when the input's domain doesn't match the
// platform (e.g. a LinkedIn URL typed into the Instagram row).
function normalizeSocialHandleInput(platform: SocialPlatform, raw: string): { url: string; error: string } {
  const trimmed = raw.trim();
  if (!trimmed) return { url: '', error: '' };

  const stripped = trimmed.replace(/^@/, '');
  const hasScheme = /^https?:\/\//i.test(stripped);
  const mentionsKnownDomain = SOCIAL_PLATFORM_DOMAINS[platform].some(d => stripped.toLowerCase().includes(d));
  const looksLikeUrl = hasScheme || /^[a-z0-9.-]+\.[a-z]{2,}\//i.test(stripped) || mentionsKnownDomain;

  let urlObj: URL;
  try {
    if (looksLikeUrl) {
      urlObj = new URL(hasScheme ? stripped : `https://${stripped}`);
    } else {
      // Bare handle -> build a canonical URL on the platform's own domain.
      urlObj = new URL(`https://${SOCIAL_PLATFORM_DOMAINS[platform][0]}/${stripped.replace(/^\/+/, '')}`);
    }
  } catch {
    return { url: '', error: 'Enter a valid handle or URL.' };
  }

  const host = urlObj.hostname.toLowerCase().replace(/^www\./, '');
  const domainMatches = SOCIAL_PLATFORM_DOMAINS[platform].some(d => host === d || host.endsWith(`.${d}`));
  if (!domainMatches) {
    return { url: '', error: `This link isn't for ${SOCIAL_PLATFORM_LABELS[platform]}.` };
  }

  const path = urlObj.pathname.replace(/\/+$/, '');
  return { url: `https://${host}${path}`, error: '' };
}

// ── Brand Brief: structured 9-field brand summary ────────────────────────────
// Mirrors backend.schemas.brand.BRAND_BRIEF_KEYS exactly, including order.
const BRAND_BRIEF_KEYS = [
  'what_we_do',
  'positioning',
  'target_audience',
  'differentiators',
  'products_services',
  'tone_of_voice',
  'business_model',
  'proof_points',
  'market_context',
] as const;
type BrandBriefKey = typeof BRAND_BRIEF_KEYS[number];

const BRAND_BRIEF_LABELS: Record<BrandBriefKey, string> = {
  what_we_do: 'What We Do',
  positioning: 'Positioning',
  target_audience: 'Target Audience',
  differentiators: 'Differentiators',
  products_services: 'Products & Services',
  tone_of_voice: 'Tone of Voice',
  business_model: 'Business Model',
  proof_points: 'Proof Points',
  market_context: 'Market Context',
};

const BRAND_BRIEF_PLACEHOLDERS: Record<BrandBriefKey, string> = {
  what_we_do: 'e.g. We build premium residential and commercial real estate across India.',
  positioning: 'e.g. Positioned as the most design-led developer in the premium segment.',
  target_audience: 'e.g. High-net-worth buyers seeking move-in-ready luxury homes.',
  differentiators: 'e.g. In-house design studio; IGBC Platinum-certified green buildings.',
  products_services: 'e.g. Residential towers, villas, plotted developments, commercial complexes.',
  tone_of_voice: 'e.g. Confident, design-forward, data-backed.',
  business_model: 'e.g. B2C — sells directly to homebuyers through company-owned sales galleries.',
  proof_points: 'e.g. Delivered 50+ projects; winner of CNBC-Awaaz Real Estate Award 2023.',
  market_context: 'e.g. Rising demand for gated communities in Tier-1 Indian cities post-2023.',
};

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
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
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
  const [step, setStep] = useState<'form' | 'loading' | 'confirm_competitors' | 'brief_review'>('form');
  const [brandName, setBrandName] = useState('');
  const [websiteUrl, setWebsiteUrl] = useState('');
  const [category, setCategory] = useState('');
  const [additionalNotes, setAdditionalNotes] = useState('');
  const [referenceDocs, setReferenceDocs] = useState<ReferenceDoc[]>([]);

  // ── Target Market (structured): region + cities[] + custom_region ───────
  const [tmRegion, setTmRegion] = useState<TargetMarketRegion | ''>('');
  const [tmCities, setTmCities] = useState<string[]>([]);
  const [tmCustomRegion, setTmCustomRegion] = useState('');
  const [tmCityInput, setTmCityInput] = useState('');
  const [tmError, setTmError] = useState('');
  const [tmConfig, setTmConfig] = useState<TargetMarketConfig | null>(null);
  const [tmConfigFailed, setTmConfigFailed] = useState(false);
  // Captured at search-competitors time, re-sent unchanged on confirm — the
  // user doesn't revisit this field between the two steps.
  const [confirmedTargetMarket, setConfirmedTargetMarket] = useState<TargetMarket | null>(null);

  const [competitorName, setCompetitorName] = useState('');
  const [competitorUrl, setCompetitorUrl] = useState('');
  const [competitors, setCompetitors] = useState<{ name: string; url?: string }[]>([]);
  const [brandKit, setBrandKit] = useState<BrandKit>({});

  const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL;
  const authToken = typeof window !== 'undefined' ? (localStorage.getItem('access_token') ?? undefined) : undefined;

  // ── Social Handles: prefilled from the website extractor (and, for
  // Instagram, from Tavily's handle discovery as a fallback), always shown
  // to the user to verify/correct/add before confirm — never forwarded
  // silently. ──────────────────────────────────────────────────────────────
  const [socialHandles, setSocialHandles] = useState<Record<string, string>>({});
  // Which rows were auto-filled, and from which source — purely cosmetic
  // (the subtle "found" badge); cleared for a row once the user edits it.
  const [socialHandlesFoundSource, setSocialHandlesFoundSource] = useState<Record<string, 'website' | 'discovery'>>({});
  const [socialHandlesFieldErrors, setSocialHandlesFieldErrors] = useState<Record<string, string>>({});
  const [socialHandlesError, setSocialHandlesError] = useState('');
  const [socialHandlesExtractedEmpty, setSocialHandlesExtractedEmpty] = useState(false);
  const socialHandlesRef = useRef<HTMLDivElement>(null);

  const handleSocialHandleChange = (platform: SocialPlatform, value: string) => {
    setSocialHandles(prev => ({ ...prev, [platform]: value }));
    setSocialHandlesFieldErrors(prev => ({ ...prev, [platform]: '' }));
    setSocialHandlesError('');
    // Once the user touches a row, it's no longer a pristine auto-find --
    // they're actively verifying/editing it, so drop the "found" badge.
    setSocialHandlesFoundSource(prev => {
      if (!(platform in prev)) return prev;
      const next = { ...prev };
      delete next[platform];
      return next;
    });
  };

  const handleSocialHandleBlur = (platform: SocialPlatform) => {
    const raw = socialHandles[platform] || '';
    if (!raw.trim()) {
      setSocialHandlesFieldErrors(prev => ({ ...prev, [platform]: '' }));
      return;
    }
    const { url, error } = normalizeSocialHandleInput(platform, raw);
    if (error) {
      setSocialHandlesFieldErrors(prev => ({ ...prev, [platform]: error }));
      return;
    }
    setSocialHandles(prev => ({ ...prev, [platform]: url }));
    setSocialHandlesFieldErrors(prev => ({ ...prev, [platform]: '' }));
  };

  // social_handles is re-validated and frozen once, on the confirm_competitors
  // -> brief_review transition, and resent unchanged on the actual /confirm
  // call -- same "captured once, resent later" pattern as confirmedTargetMarket,
  // since the user doesn't revisit this screen on brief_review.
  const [confirmedSocialHandles, setConfirmedSocialHandles] = useState<Record<string, string> | null>(null);

  // ── Brand Brief: generated from the website/docs, always user-verified
  // before confirm. Fired at handleSubmit time but NOT awaited there (see
  // fetchBrandBrief/briefPromiseRef) -- generation overlaps with the time the
  // user spends on the competitor-confirm screen instead of adding its own
  // serial wait. ────────────────────────────────────────────────────────────
  const [brandBrief, setBrandBrief] = useState<Record<string, string>>({});
  const [briefLoading, setBriefLoading] = useState(false);
  const [briefError, setBriefError] = useState('');
  const [briefEmptyNote, setBriefEmptyNote] = useState(false);
  const briefRef = useRef<HTMLDivElement>(null);
  const briefPromiseRef = useRef<Promise<Record<string, string>> | null>(null);

  const fetchBrandBrief = async (targetMarketOverride?: TargetMarket | null): Promise<Record<string, string>> => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const tm = targetMarketOverride !== undefined ? targetMarketOverride : confirmedTargetMarket;

    try {
      const res = await fetch(`${apiBase}/api/brands/generate-brief`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          brand_name: brandName,
          website_url: websiteUrl,
          category,
          target_market: tm || undefined,
          additional_notes: additionalNotes.trim() || undefined,
          reference_docs: referenceDocs.length > 0 ? referenceDocs : undefined,
        })
      });
      if (!res.ok) return {};
      return await res.json();
    } catch (e) {
      console.warn('Brand brief generation failed:', e);
      return {};
    }
  };

  const isBriefAllEmpty = (brief: Record<string, string>) =>
    BRAND_BRIEF_KEYS.every(key => !(brief[key] || '').trim());

  const handleRegenerateBrief = async () => {
    setBriefLoading(true);
    setBriefError('');
    try {
      const brief = await fetchBrandBrief();
      setBrandBrief(brief || {});
      setBriefEmptyNote(isBriefAllEmpty(brief || {}));
    } finally {
      setBriefLoading(false);
    }
  };

  // ── Candidates state ──────────────────────────────────────────────────────
  const [candidates, setCandidates] = useState<{ name: string; website_url: string; handle: string; source: string; selected: boolean; verified?: boolean; source_url?: string; logo_url?: string }[]>([]);
  const [newCompName, setNewCompName] = useState('');
  const [newCompWebsite, setNewCompWebsite] = useState('');
  const [tavilyError, setTavilyError] = useState('');
  const [discoveryStatus, setDiscoveryStatus] = useState<'ok' | 'empty' | 'failed' | null>(null);
  const [maxSelectionFlash, setMaxSelectionFlash] = useState(false);
  const flashTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    return () => { if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current); };
  }, []);

  // ── Fetch Target Market region/city config — single source of truth,
  // never hardcoded here. Degrades gracefully (region-only, free-text
  // cities) if the fetch fails, so the wizard still works. ─────────────────
  useEffect(() => {
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;

    (async () => {
      try {
        const res = await fetch(`${apiBase}/api/brands/target-market-config`, { headers });
        if (!res.ok) throw new Error('target-market-config fetch failed');
        const data: TargetMarketConfig = await res.json();
        setTmConfig(data);
      } catch (e) {
        console.error('Failed to load target market config, degrading to free-text:', e);
        setTmConfigFailed(true);
      }
    })();
  }, []);

  // Mirrors backend MIN_COMPETITORS / MAX_COMPETITORS (competitor_service.py).
  // Note: the backend's suggestion pool (MAX_SUGGESTIONS=8) is intentionally
  // larger than this — the frontend is what enforces the 5-selection cap.
  const MIN_COMPETITORS = 3;
  const MAX_COMPETITORS = 5;
  const manualCompetitorsAtMax = competitors.length >= MAX_COMPETITORS;
  const selectedCandidateCount = candidates.filter(c => c.selected).length;
  const belowMinCompetitors = selectedCandidateCount < MIN_COMPETITORS;
  const selectionAtMax = selectedCandidateCount >= MAX_COMPETITORS;

  // ── Validation errors ─────────────────────────────────────────────────────
  const [errors, setErrors] = useState<Record<string, string>>({});

  // ── Refs for scrolling to error fields ───────────────────────────────────
  const brandNameRef = useRef<HTMLInputElement>(null);
  const websiteUrlRef = useRef<HTMLInputElement>(null);
  const categoryRef = useRef<HTMLSelectElement>(null);
  const targetMarketRef = useRef<HTMLDivElement>(null);

  const handleAddCompetitor = () => {
    if (!competitorName.trim()) return;
    setCompetitors(prev => [...prev, { name: competitorName.trim(), url: competitorUrl.trim() || undefined }]);
    setCompetitorName('');
    setCompetitorUrl('');
  };

  const handleRemoveCompetitor = (index: number) => {
    setCompetitors(prev => prev.filter((_, i) => i !== index));
  };

  // ── Target Market handlers ───────────────────────────────────────────────
  const handleTmRegionChange = (value: TargetMarketRegion | '') => {
    setTmRegion(value);
    setTmCities([]);          // region change always resets the city selection
    setTmCustomRegion('');
    setTmCityInput('');
    setTmError('');
  };

  const handleToggleCuratedCity = (city: string) => {
    setTmCities(prev => (prev.includes(city) ? prev.filter(c => c !== city) : [...prev, city]));
    setTmError('');
  };

  const handleAddCustomCity = () => {
    const city = tmCityInput.trim();
    if (!city) return;
    if (!tmCities.some(c => c.toLowerCase() === city.toLowerCase())) {
      setTmCities(prev => [...prev, city]);
    }
    setTmCityInput('');
    setTmError('');
  };

  const handleRemoveCity = (city: string) => {
    setTmCities(prev => prev.filter(c => c !== city));
  };

  // Mirrors the backend's TargetMarket validation exactly (schemas/brand.py):
  //   local  -> cities must have >= 1 entry
  //   global -> cities forced empty (never an error)
  //   india/us/europe -> cities optional (0+)
  //   other  -> requires custom_region OR >= 1 city
  // Returns null (no target_market — omitted from the request) when the user
  // made no selection at all; returns the built object otherwise; sets
  // tmError and returns 'invalid' when the selection fails validation.
  const buildTargetMarket = (): TargetMarket | null | 'invalid' => {
    if (!tmRegion) return null; // untouched -- omit entirely, backend treats as None

    if (tmRegion === 'local') {
      if (tmCities.length < 1) {
        setTmError('Add at least one city for a local target market.');
        return 'invalid';
      }
      return { region: 'local', cities: tmCities };
    }
    if (tmRegion === 'global') {
      return { region: 'global', cities: [] }; // cities forced empty, never an error
    }
    if (tmRegion === 'other') {
      if (!tmCustomRegion.trim() && tmCities.length < 1) {
        setTmError('Enter a custom region or add at least one city.');
        return 'invalid';
      }
      return { region: 'other', cities: tmCities, custom_region: tmCustomRegion.trim() || undefined };
    }
    // india / us / europe: cities optional
    return { region: tmRegion, cities: tmCities };
  };


  const handleAddConfirmedCompetitor = () => {
    if (!newCompName.trim() || selectionAtMax) return;
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
    const target = candidates[idx];
    if (!target) return;
    // Block turning a card ON once 5 are already selected; unchecking is always
    // allowed. No card is ever visually disabled for this — instead, flash the
    // "Maximum selected" helper text in amber for ~2s so the user knows why
    // their click didn't do anything.
    if (!target.selected && selectedCandidateCount >= MAX_COMPETITORS) {
      setMaxSelectionFlash(true);
      if (flashTimeoutRef.current) clearTimeout(flashTimeoutRef.current);
      flashTimeoutRef.current = setTimeout(() => setMaxSelectionFlash(false), 2000);
      return;
    }
    setCandidates(prev => prev.map((c, i) => (i === idx ? { ...c, selected: !c.selected } : c)));
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

    // Target Market is required — block before the region-specific checks below.
    if (!tmRegion) {
      setTmError('This field is mandatory');
      targetMarketRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }

    // Client-side Target Market validation, mirroring the backend exactly —
    // block submit before the request is ever sent.
    const targetMarket = buildTargetMarket();
    if (targetMarket === 'invalid') return;
    setConfirmedTargetMarket(targetMarket);

    let finalCompetitors = [...competitors];
    if (competitorName.trim()) {
      finalCompetitors.push({ name: competitorName.trim(), url: competitorUrl.trim() || undefined });
    }

    setStep('loading');

    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const token = localStorage.getItem('access_token');
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    const getHeaders: Record<string, string> = {};
    if (token) getHeaders['Authorization'] = `Bearer ${token}`;

    // Social-links extraction runs IN PARALLEL with search-competitors, not
    // after -- it must never add a serial wait to this step. A client-side
    // timeout means a slow/unreachable site still lets the user proceed with
    // blank rows rather than blocking brand setup.
    const extractSocialLinksWithTimeout = async (timeoutMs: number): Promise<Record<string, string>> => {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), timeoutMs);
      try {
        const res = await fetch(
          `${apiBase}/api/brands/extract-social-links?website_url=${encodeURIComponent(websiteUrl)}`,
          { headers: getHeaders, signal: controller.signal }
        );
        if (!res.ok) return {};
        return await res.json();
      } catch (e) {
        console.warn('Social link extraction skipped (slow/unreachable site):', e);
        return {};
      } finally {
        clearTimeout(timer);
      }
    };

    // Brand Brief generation (LLM + Tavily) is started HERE but deliberately
    // NOT awaited in the Promise.all below -- it's likely slower than
    // competitor search, and awaiting it up front would add that wait to a
    // step users already sit through. The promise is stashed and awaited
    // only on the transition into the review step, so it overlaps with the
    // time the user spends on the competitor-confirm screen instead.
    briefPromiseRef.current = fetchBrandBrief(targetMarket);

    try {
      const [res, extracted] = await Promise.all([
        fetch(`${apiBase}/api/brands/search-competitors`, {
          method: 'POST',
          headers,
          body: JSON.stringify({
            brand_name: brandName,
            website_url: websiteUrl,
            category,
            target_market: targetMarket || undefined,
            user_competitors: finalCompetitors.map(c => ({ name: c.name, url: c.url || '' }))
          })
        }),
        extractSocialLinksWithTimeout(6000)
      ]);

      if (res.status === 401) {
        localStorage.removeItem('access_token');
        router.push('/auth');
        return;
      }
      if (!res.ok) throw new Error('Failed to search competitors');
      const data = await res.json();
      setTavilyError(data.tavily_error || '');
      setDiscoveryStatus(data.discovery_status || null);

      // Prefill Social Handles: one row per SOCIAL_PLATFORMS, from the website
      // scan first. If the scan found no Instagram link but Tavily's handle
      // discovery did, use that as a full URL -- visible and editable, never
      // forwarded silently as it was before this change.
      const prefill: Record<string, string> = {};
      const foundSource: Record<string, 'website' | 'discovery'> = {};
      for (const platform of SOCIAL_PLATFORMS) {
        const url = extracted?.[platform];
        if (url) {
          prefill[platform] = url;
          foundSource[platform] = 'website';
        }
      }
      // Same fallback the backend used to apply silently: when Tavily found no
      // real handle, guess one from the brand name so the row isn't blank --
      // but now it's a visible, editable prefill, not a value sent unseen.
      const discoveredHandle = data.brand_handle || brandName.replace(/\s/g, '').toLowerCase();
      if (!prefill.instagram && discoveredHandle) {
        prefill.instagram = `https://instagram.com/${discoveredHandle}`;
        foundSource.instagram = 'discovery';
      }
      setSocialHandles(prefill);
      setSocialHandlesFoundSource(foundSource);
      setSocialHandlesFieldErrors({});
      setSocialHandlesError('');
      setSocialHandlesExtractedEmpty(Object.keys(prefill).length === 0);

      // Backend now returns up to MAX_SUGGESTIONS (8) candidates, user-provided
      // entries first — default-select by position so the first 5 (which are
      // the user's own competitors first, then top auto-discovered ones) are
      // pre-checked, matching the 5-selection cap below.
      //
      // Every item here is tagged 'discovery' unconditionally, regardless of
      // whatever string the backend's own `source` field happens to carry —
      // the backend's "is_auto" heuristic (bool(source_url)) can legitimately
      // be false for a genuine auto-discovered competitor whose source
      // article couldn't be traced back, which would otherwise mislabel it as
      // "user". The ONLY way a candidate is tagged 'user' on the frontend is
      // via the "Add Another Competitor" input below (handleAddConfirmedCompetitor).
      const mapped = (data.candidates || []).map((c: any, idx: number) => ({
        name: c.name || '',
        website_url: c.website_url || c.url || '',
        handle: c.handle || c.name?.replace(/\s/g, '').toLowerCase() || '',
        source: 'discovery',
        selected: idx < MAX_COMPETITORS,
        verified: typeof c.verified === 'boolean' ? c.verified : undefined,
        source_url: c.source_url || undefined,
        logo_url: c.logo_url || undefined
      }));
      if (data.brand_logo_url && !brandKit.logo_url) {
        setBrandKit(prev => ({ ...prev, logo_url: data.brand_logo_url }));
      }
      setCandidates(mapped);
      setStep('confirm_competitors');
    } catch (e: any) {
      console.error('Search competitors error:', e);
      alert(`Error searching competitors: ${e.message}`);
      setStep('form');
    }
  };

  // confirm_competitors -> brief_review: validates competitors + social
  // handles (unchanged logic, just moved), freezes social_handles into state
  // for the actual /confirm call later, then awaits whatever
  // fetchBrandBrief(...) (started back in handleSubmit) has produced by now.
  const handleContinueToBrief = async () => {
    const selectedComps = candidates.filter(c => c.selected);
    if (selectedComps.length === 0) {
      alert("Please select or add at least one competitor to analyze.");
      return;
    }

    // Social Handles — required: at least one platform (not Instagram
    // specifically, since extraction legitimately returns {} for some
    // sites). Re-normalize every non-empty row on submit (not just on
    // blur) so a value pasted and never blurred still gets validated.
    const canonicalSocialHandles: Record<string, string> = {};
    let hasFieldError = false;
    const fieldErrors: Record<string, string> = {};
    for (const platform of SOCIAL_PLATFORMS) {
      const raw = (socialHandles[platform] || '').trim();
      if (!raw) continue;
      const { url, error } = normalizeSocialHandleInput(platform, raw);
      if (error) {
        fieldErrors[platform] = error;
        hasFieldError = true;
        continue;
      }
      if (url) canonicalSocialHandles[platform] = url;
    }
    if (hasFieldError) {
      setSocialHandlesFieldErrors(prev => ({ ...prev, ...fieldErrors }));
      setSocialHandlesError('Fix the highlighted social handle(s) before continuing.');
      socialHandlesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    if (Object.keys(canonicalSocialHandles).length === 0) {
      setSocialHandlesError('Add at least one social profile link.');
      socialHandlesRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    setSocialHandlesError('');
    setConfirmedSocialHandles(canonicalSocialHandles);

    setStep('brief_review');
    setBriefLoading(true);
    setBriefError('');
    try {
      const brief = await (briefPromiseRef.current ?? fetchBrandBrief());
      setBrandBrief(brief || {});
      setBriefEmptyNote(isBriefAllEmpty(brief || {}));
    } finally {
      setBriefLoading(false);
    }
  };

  const handleFinalConfirm = async () => {
    // Brand Brief — required: at least one of the nine fields (pre-filled
    // fields make this low-friction in the normal case; a thin brand can
    // still fill just one by hand).
    const trimmedBrief: Record<string, string> = {};
    for (const key of BRAND_BRIEF_KEYS) {
      const value = (brandBrief[key] || '').trim();
      if (value) trimmedBrief[key] = value;
    }
    if (Object.keys(trimmedBrief).length === 0) {
      setBriefError('Add at least one field before continuing.');
      briefRef.current?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      return;
    }
    setBriefError('');

    const selectedComps = candidates.filter(c => c.selected);
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
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
          additional_notes: additionalNotes.trim() || undefined,
          reference_docs: referenceDocs.length > 0 ? referenceDocs : undefined,
          social_handles: confirmedSocialHandles || {},
          brand_brief: trimmedBrief,
          target_market: confirmedTargetMarket || undefined,
          selected_competitors: selectedComps.map(c => ({
            name: c.name,
            website_url: c.website_url || '',
            handle: c.handle || '',
            logo_url: c.logo_url || ''
          })),
          brand_kit: (() => {
            const hasBrandKit = brandKit.logo_url || (brandKit.colors && Object.values(brandKit.colors).some(Boolean));
            return hasBrandKit ? brandKit : null;
          })()
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
          {step === 'brief_review' && "Review your Brand Brief"}
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

            {/* Target Market (scopes competitor discovery): cascading Region -> City.
                Region options + curated city lists come from GET /target-market-config
                (fetched on mount) -- never hardcoded here. */}
            <div className={styles.formRow} ref={targetMarketRef}>
              <div className={styles.formGroup}>
                <label className={styles.label}>Target Market <span className={styles.required}>*</span></label>
                <select
                  className={styles.select}
                  value={tmRegion}
                  onChange={e => handleTmRegionChange(e.target.value as TargetMarketRegion | '')}
                >
                  <option value="">Select target market...</option>
                  {(tmConfig?.regions || TARGET_MARKET_FALLBACK_REGIONS).map(r => (
                    <option key={r.value} value={r.value}>{r.label}</option>
                  ))}
                </select>

                {tmRegion === 'other' && (
                  <input
                    className={styles.input}
                    style={{ marginTop: '10px' }}
                    value={tmCustomRegion}
                    onChange={e => { setTmCustomRegion(e.target.value); setTmError(''); }}
                    placeholder="Specify target market (e.g. UAE)"
                  />
                )}

                {/* Curated multi-select, from the config endpoint, for india/us/europe */}
                {(tmRegion === 'india' || tmRegion === 'us' || tmRegion === 'europe') && tmConfig && !tmConfigFailed && (
                  <div className={styles.citySelectGrid} style={{ marginTop: '10px' }}>
                    {(tmConfig.cities[tmRegion] || []).map(city => (
                      <button
                        type="button"
                        key={city}
                        className={`${styles.cityPill} ${tmCities.includes(city) ? styles.cityPillActive : ''}`}
                        onClick={() => handleToggleCuratedCity(city)}
                      >
                        {city}
                      </button>
                    ))}
                  </div>
                )}

                {/* Free-text city add: required for local, optional custom-add for
                    india/us/europe/other, or the fallback when config fetch failed. */}
                {(tmRegion === 'local' || tmRegion === 'india' || tmRegion === 'us' || tmRegion === 'europe' || tmRegion === 'other') && (
                  <div className={styles.competitorRow} style={{ marginTop: '10px' }}>
                    <input
                      className={styles.input}
                      value={tmCityInput}
                      onChange={e => setTmCityInput(e.target.value)}
                      onKeyDown={e => { if (e.key === 'Enter') { e.preventDefault(); handleAddCustomCity(); } }}
                      placeholder={
                        tmRegion === 'local'
                          ? 'Type a city and press Enter (required, add 1 or more)'
                          : 'Add a city not in the list above (optional)'
                      }
                    />
                    <button type="button" className={styles.addBtn} onClick={handleAddCustomCity}>Add</button>
                  </div>
                )}

                {tmCities.length > 0 && tmRegion !== 'global' && (
                  <div className={styles.competitorsList}>
                    {tmCities.map(city => (
                      <div key={city} className={styles.competitorChip}>
                        <span className={styles.competitorChipText}>{city}</span>
                        <button
                          type="button"
                          className={styles.deleteChipBtn}
                          onClick={() => handleRemoveCity(city)}
                          title="Remove city"
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

                {tmRegion === 'global' && (
                  <p className={styles.helpText}>Global target market — no city narrowing needed.</p>
                )}

                {tmConfigFailed && tmRegion && tmRegion !== 'global' && tmRegion !== 'local' && (
                  <p className={styles.helpText}>Couldn&apos;t load the curated city list — type city names manually above.</p>
                )}

                {tmError && <span className={styles.errorMsg}>{tmError}</span>}
              </div>
            </div>

            {/* Additional Notes / Guardrails */}
            <div className={styles.formGroup}>
              <label className={styles.label}>Additional Notes / Guardrails (Optional)</label>
              <textarea
                className={styles.textarea}
                value={additionalNotes}
                onChange={e => setAdditionalNotes(e.target.value)}
                placeholder="Any intent, restrictions, or compliance rules the AI can't find online (e.g. 'Moving to premium positioning', 'BFSI — follow SEBI rules', 'Do not mention competitor X by name')."
                rows={3}
              />
            </div>

            {/* Brand Documents */}
            <div className={styles.formGroup}>
              <ReferenceUpload
                value={referenceDocs}
                onChange={setReferenceDocs}
                apiBase={apiBaseUrl ?? ''}
                authToken={authToken}
              />
            </div>

            {/* Brand Kit (logo + colors) */}
            <div className={styles.formGroup}>
              <BrandKitForm brandKit={brandKit} onChange={setBrandKit} apiBase={apiBaseUrl} authToken={authToken} />
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
                  disabled={manualCompetitorsAtMax}
                />
                <button type="button" className={styles.addBtn} onClick={handleAddCompetitor} disabled={manualCompetitorsAtMax}>Add</button>
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
              <p className={styles.helpText}>
                {manualCompetitorsAtMax
                  ? `Maximum of ${MAX_COMPETITORS} competitors reached.`
                  : 'Press Enter in either field or click Add to save a competitor.'}
              </p>
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

            {/* Tavily error / quota warning banner (legacy flag-OFF path) */}
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

            {/* discovery_status messaging (hybrid resolver path) */}
            {discoveryStatus === 'empty' && (
              <p className={styles.discoveryStatusNote}>
                No competitors found automatically. Please add at least 3 manually.
              </p>
            )}
            {discoveryStatus === 'failed' && (
              <div className={styles.discoveryWarningNote}>
                <span>Competitor search encountered an issue. Please add competitors manually or try again.</span>
                <button type="button" className={styles.retryDiscoveryBtn} onClick={handleSubmit}>
                  Retry
                </button>
              </div>
            )}

            <div className={styles.candidateGrid}>
              {candidates.length === 0 && (
                <div className={styles.noCandidatesMsg}>
                  <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#d1d5db" strokeWidth="1.5">
                    <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
                  </svg>
                  <p>No competitors found automatically — add them manually below.</p>
                </div>
              )}

              {candidates.map((cand, idx) => {
                return (
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
                    <div className={styles.candidateCompactBody}>
                      <div className={styles.candidateCompactTop}>
                        {cand.logo_url && (
                          <img
                            src={cand.logo_url.startsWith('/') ? `${apiBaseUrl || ''}${cand.logo_url}` : cand.logo_url}
                            alt={cand.name}
                            className={styles.candidateLogoImg}
                            onError={(e) => { (e.currentTarget as HTMLElement).style.display = 'none'; }}
                          />
                        )}
                        <span className={styles.candidateName}>{cand.name}</span>
                        {typeof cand.verified === 'boolean' && (
                          <span className={`${styles.candidateSourceBadge} ${cand.verified ? styles.badgeVerified : styles.badgeUnverified}`}>
                            {cand.verified ? 'Verified' : 'Unverified'}
                          </span>
                        )}
                        <span className={`${styles.candidateSourceBadge} ${cand.source === 'user' ? styles.badgeUser : styles.badgeTavily}`}>
                          {cand.source === 'user' ? 'Added by you' : 'Suggested'}
                        </span>
                      </div>
                      <div className={styles.candidateCompactBottom} onClick={(e) => e.stopPropagation()}>
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
                            placeholder="Paste competitor URL"
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
                );
              })}
            </div>

            {belowMinCompetitors && (
              <p className={styles.minCompetitorsHelper}>
                At least {MIN_COMPETITORS} competitors required to continue
              </p>
            )}
            {selectionAtMax && (
              <p className={`${styles.minCompetitorsHelper} ${maxSelectionFlash ? styles.minCompetitorsHelperFlash : ''}`}>
                Maximum of {MAX_COMPETITORS} competitors selected
              </p>
            )}

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
                  disabled={selectionAtMax}
                />
                <input
                  type="text"
                  placeholder="Website URL (e.g. https://adidas.com)"
                  value={newCompWebsite}
                  onChange={(e) => setNewCompWebsite(e.target.value)}
                  className={styles.input}
                  disabled={selectionAtMax}
                />
                <button
                  type="button"
                  onClick={handleAddConfirmedCompetitor}
                  className={styles.addBtn}
                  disabled={selectionAtMax}
                >
                  Add
                </button>
              </div>
            </div>

            {/* Social Handles — required: at least one platform, auto-filled
                from the website scan (and, for Instagram, from Tavily's
                discovery as a fallback), always user-verified before confirm. */}
            <div className={`${styles.formGroup} ${styles.socialHandlesSection}`} ref={socialHandlesRef}>
              <div className={styles.socialHandlesTitleRow}>
                <label className={styles.label} style={{ marginBottom: 0 }}>Social Handles</label>
                <div className={styles.infoTooltipWrapper}>
                  <button
                    type="button"
                    className={styles.infoTooltipBtn}
                    aria-label="Social handles information"
                  >
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="12" y1="16" x2="12" y2="12" />
                      <line x1="12" y1="8" x2="12.01" y2="8" />
                    </svg>
                  </button>
                  <div className={styles.infoTooltipContent} role="tooltip">
                    We scanned your website for official profile links. Verify or correct what we found, and add any platform we missed — at least one is required.
                  </div>
                </div>
              </div>

              {socialHandlesExtractedEmpty && (
                <p className={styles.helpText}>
                  We couldn&apos;t automatically find any social links on your site. Please add at least one below.
                </p>
              )}

              <div className={styles.socialHandlesGrid}>
                {SOCIAL_PLATFORMS.map(platform => (
                  <div key={platform} className={styles.socialHandleRow}>
                    <div className={styles.socialHandleLabelRow}>
                      <span className={styles.socialHandleIcon}>{SOCIAL_PLATFORM_ICONS[platform]}</span>
                      <span className={styles.socialHandlePlatform}>{SOCIAL_PLATFORM_LABELS[platform]}</span>
                      {socialHandlesFoundSource[platform] && (
                        <span className={styles.foundBadge}>
                          {socialHandlesFoundSource[platform] === 'website' ? 'Found on your site' : 'Auto-detected'}
                        </span>
                      )}
                    </div>
                    <input
                      className={`${styles.input} ${socialHandlesFieldErrors[platform] ? styles.inputError : ''}`}
                      value={socialHandles[platform] || ''}
                      onChange={e => handleSocialHandleChange(platform, e.target.value)}
                      onBlur={() => handleSocialHandleBlur(platform)}
                      placeholder={`@handle or https://${SOCIAL_PLATFORM_DOMAINS[platform][0]}/yourbrand`}
                    />
                    {socialHandlesFieldErrors[platform] && (
                      <span className={styles.errorMsg}>{socialHandlesFieldErrors[platform]}</span>
                    )}
                  </div>
                ))}
              </div>

              {socialHandlesError && <span className={styles.errorMsg}>{socialHandlesError}</span>}
            </div>

            <div className={styles.footer}>
              <button className={styles.backBtn} onClick={() => setStep('form')}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
                </svg>
                Back
              </button>
              <button
                className={styles.continueBtn}
                onClick={handleContinueToBrief}
                disabled={belowMinCompetitors}
                title={belowMinCompetitors ? `At least ${MIN_COMPETITORS} competitors required to continue` : undefined}
              >
                CONTINUE
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
                </svg>
              </button>
            </div>
          </div>
        )}

        {step === 'brief_review' && (
          <div>
            <div className={styles.cardHeader}>
              <div className={styles.iconWrapper}>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              </div>
              <div>
                <h2 className={styles.cardTitle}>Review Your Brand Brief</h2>
                <p className={styles.confirmSectionSubtitle}>
                  We drafted this from your website and documents. Verify or edit each field — at least one is required.
                </p>
              </div>
            </div>

            <div className={styles.formGroup} ref={briefRef}>
              {briefLoading ? (
                <div className={styles.loadingScreen} style={{ padding: '32px 0' }}>
                  <div className={styles.spinner} />
                  <p className={styles.helpText} style={{ marginTop: '12px' }}>Drafting your Brand Brief...</p>
                </div>
              ) : (
                <>
                  {briefEmptyNote && (
                    <p className={styles.helpText}>
                      We couldn&apos;t automatically draft a brief from the available information. Please fill in at least one field below.
                    </p>
                  )}

                  {BRAND_BRIEF_KEYS.map(key => (
                    <div key={key} className={styles.formGroup}>
                      <label className={styles.label}>{BRAND_BRIEF_LABELS[key]}</label>
                      <textarea
                        className={styles.textarea}
                        value={brandBrief[key] || ''}
                        onChange={e => {
                          const value = e.target.value;
                          setBrandBrief(prev => ({ ...prev, [key]: value }));
                          setBriefError('');
                        }}
                        placeholder={BRAND_BRIEF_PLACEHOLDERS[key]}
                        rows={2}
                      />
                    </div>
                  ))}

                  <button type="button" className={styles.addBtn} onClick={handleRegenerateBrief}>
                    Regenerate
                  </button>

                  {briefError && <span className={styles.errorMsg}>{briefError}</span>}
                </>
              )}
            </div>

            <div className={styles.footer}>
              <button className={styles.backBtn} onClick={() => setStep('confirm_competitors')}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/>
                </svg>
                Back
              </button>
              <button
                className={styles.continueBtn}
                onClick={handleFinalConfirm}
                disabled={briefLoading}
              >
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
