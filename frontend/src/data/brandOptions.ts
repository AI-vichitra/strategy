// Single source of truth for the Category option list onboarding
// (brand-setup/page.tsx) and the agent-template form (AgentTemplateView)
// both render as pills/a select — kept here so a brand's stored `category`
// always has an exact string match to pre-select in the template form
// instead of the two option sets silently drifting apart.
export const BRAND_CATEGORIES = [
  'Real Estate',
  'Technology & Software',
  'Consumer Electronics',
  'SaaS (Software as a Service)',
  'Healthcare & Life Sciences',
  'E-commerce',
  'D2C (Direct-to-Consumer)',
  'Financial Services & Fintech',
  'Education & EdTech',
  'Retail',
  'Manufacturing & Industrial',
  'FMCG & Consumer Goods',
  'Hospitality & Events',
  'Travel & Tourism',
  'Media & Entertainment',
  'Automotive & Mobility',
  'Professional Services (B2B)',
  'Marketing & Advertising',
  'Wellness, Health & Fitness',
  'Food & Beverage',
  'Fashion & Beauty',
  'Non-Profit / NGO',
  'Other',
] as const;

// Mirrors backend.schemas.brand.TARGET_MARKET_CONFIG['regions'] exactly —
// onboarding itself sources this list dynamically from
// GET /api/brands/target-market-config rather than hardcoding it, but it's
// stable curated config, so the agent-template form (which has no reason to
// make that same network call just for 6 pills) mirrors it statically here.
// `value` is the canonical code stored in BrandConfig.target_market.region;
// `label` is what the template form shows/stores as its Target Audience
// region pill (that field has always been a plain display string, so the
// label — not the code — is what gets written to targetAudience.region).
export const TARGET_MARKET_REGIONS = [
  { value: 'local', label: 'Local / City-specific' },
  { value: 'india', label: 'India' },
  { value: 'us', label: 'United States' },
  { value: 'europe', label: 'Europe' },
  { value: 'global', label: 'Global' },
  { value: 'other', label: 'Other' },
] as const;
