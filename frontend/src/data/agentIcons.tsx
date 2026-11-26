import React from 'react';

/**
 * Professional SVG Icon mappings for agent templates and categories.
 * Replaces all emojis with crisp, modern, stroke/fill SVG icons.
 */

interface IconProps {
  className?: string;
  size?: number;
}

// ── Shared SVG Helper ──────────────────────────────────────────
const IconSvg = ({
  children,
  size = 18,
  className,
}: {
  children: React.ReactNode;
  size?: number;
  className?: string;
}) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    className={className}
    style={{ display: 'block', flexShrink: 0 }}
  >
    {children}
  </svg>
);

// ── Agent Specific Icons ───────────────────────────────────────

/** Competition Analysis: Crosshair / Search with target radar */
export const CompetitionAnalysisIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="11" cy="11" r="8" />
    <line x1="21" y1="21" x2="16.65" y2="16.65" />
    <circle cx="11" cy="11" r="3" />
  </IconSvg>
);

/** GTM Strategy: Rocket / Direct Launch Vector */
export const GtmStrategyIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M4.5 16.5c-1.5 1.26-2 5-2 5s3.74-.5 5-2c.71-.84.7-2.13-.09-2.91a2.18 2.18 0 0 0-2.91-.09z" />
    <path d="m12 15-3-3a22 22 0 0 1 2-3.95A12.88 12.88 0 0 1 22 2c0 2.72-.78 7.5-6 11a22.35 22.35 0 0 1-4 2z" />
    <path d="M9 12H4s.55-3.03 2-4c1.62-1.08 5 0 5 0" />
    <path d="M12 15v5s3.03-.55 4-2c1.08-1.62 0-5 0-5" />
  </IconSvg>
);

/** Product Launch Strategy: Unboxed product package / Deliverable */
export const ProductLaunchIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M16.5 9.4 7.55 4.24a1.78 1.78 0 0 0-2.5 1.55v12.42a1.78 1.78 0 0 0 2.5 1.55L16.5 14.6a1.78 1.78 0 0 0 0-3.2z" />
    <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
    <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
    <line x1="12" y1="22.08" x2="12" y2="12" />
  </IconSvg>
);

/** Social Media Strategy: Network shares / Nodes */
export const SocialMediaIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="18" cy="5" r="3" />
    <circle cx="6" cy="12" r="3" />
    <circle cx="18" cy="19" r="3" />
    <line x1="8.59" y1="13.51" x2="15.42" y2="17.49" />
    <line x1="15.41" y1="6.51" x2="8.59" y2="10.49" />
  </IconSvg>
);

/** Content Calendar: Scheduled Editorial Calendar */
export const ContentCalendarIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <rect x="3" y="4" width="18" height="18" rx="2" ry="2" />
    <line x1="16" y1="2" x2="16" y2="6" />
    <line x1="8" y1="2" x2="8" y2="6" />
    <line x1="3" y1="10" x2="21" y2="10" />
    <line x1="8" y1="14" x2="8.01" y2="14" />
    <line x1="12" y1="14" x2="12.01" y2="14" />
    <line x1="16" y1="14" x2="16.01" y2="14" />
    <line x1="8" y1="18" x2="8.01" y2="18" />
    <line x1="12" y1="18" x2="12.01" y2="18" />
  </IconSvg>
);

/** Festival/Topical Campaign Strategy: Flag / Milestone banner */
export const CampaignStrategyIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M4 15s1-1 4-1 5 2 8 2 4-1 4-1V3s-1 1-4 1-5-2-8-2-4 1-4 1z" />
    <line x1="4" y1="22" x2="4" y2="15" />
  </IconSvg>
);

/** GEO / AEO: AI Optimization / Generative neural nodes */
export const GeoAeoIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <rect x="4" y="4" width="16" height="16" rx="2" />
    <rect x="9" y="9" width="6" height="6" />
    <line x1="9" y1="1" x2="9" y2="4" />
    <line x1="15" y1="1" x2="15" y2="4" />
    <line x1="9" y1="20" x2="9" y2="23" />
    <line x1="15" y1="20" x2="15" y2="23" />
    <line x1="20" y1="9" x2="23" y2="9" />
    <line x1="20" y1="14" x2="23" y2="14" />
    <line x1="1" y1="9" x2="4" y2="9" />
    <line x1="1" y1="14" x2="4" y2="14" />
  </IconSvg>
);

/** SEO Strategy: Trending Upwards Growth Chart */
export const SeoStrategyIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <polyline points="22 7 13.5 15.5 8.5 10.5 2 17" />
    <polyline points="16 7 22 7 22 13" />
  </IconSvg>
);

/** Seasonal Campaign: Cyclic Refresh / Horizon */
export const SeasonalCampaignIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2" />
    <path d="M12 20v2" />
    <path d="m4.93 4.93 1.41 1.41" />
    <path d="m17.66 17.66 1.41 1.41" />
    <path d="M2 12h2" />
    <path d="M20 12h2" />
    <path d="m6.34 17.66-1.41 1.41" />
    <path d="m19.07 4.93-1.41 1.41" />
  </IconSvg>
);

/** Brand Audit: Verified Shield */
export const BrandAuditIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
    <path d="m9 12 2 2 4-4" />
  </IconSvg>
);

/** Brand Positioning: Precision Target Bullseye */
export const BrandPositioningIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="12" cy="12" r="10" />
    <circle cx="12" cy="12" r="6" />
    <circle cx="12" cy="12" r="2" />
  </IconSvg>
);

/** ICP & Personas: User profiles / Audience */
export const IcpPersonasIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
    <circle cx="9" cy="7" r="4" />
    <path d="M22 21v-2a4 4 0 0 0-3-3.87" />
    <path d="M16 3.13a4 4 0 0 1 0 7.75" />
  </IconSvg>
);

/** Campaign Structure Architect: Structured Layers Hierarchy */
export const CampaignArchitectIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <polygon points="12 2 2 7 12 12 22 7 12 2" />
    <polyline points="2 17 12 22 22 17" />
    <polyline points="2 12 12 17 22 12" />
  </IconSvg>
);

/** Bidding & Budget Optimizer: Financial Gauge / Currency */
export const BudgetOptimizerIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="6" x2="12" y2="18" />
    <path d="M16 9.5a2.5 2.5 0 0 0-2.5-2.5h-3a2.5 2.5 0 0 0 0 5h3a2.5 2.5 0 0 1 0 5h-3.5a2.5 2.5 0 0 1-2.5-2.5" />
  </IconSvg>
);

/** Company Research Agent: Enterprise Building */
export const CompanyResearchIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <rect x="4" y="2" width="16" height="20" rx="2" ry="2" />
    <line x1="9" y1="6" x2="9.01" y2="6" />
    <line x1="15" y1="6" x2="15.01" y2="6" />
    <line x1="9" y1="10" x2="9.01" y2="10" />
    <line x1="15" y1="10" x2="15.01" y2="10" />
    <line x1="9" y1="14" x2="9.01" y2="14" />
    <line x1="15" y1="14" x2="15.01" y2="14" />
    <path d="M10 22v-4h4v4" />
  </IconSvg>
);

/** Competitive Intelligence Agent: Radar Sweep */
export const CompetitiveIntelligenceIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="M12 2a10 10 0 0 1 10 10" />
    <path d="M12 6a6 6 0 0 1 6 6" />
    <circle cx="12" cy="12" r="2" />
    <path d="M2 12h2" />
    <path d="M12 22v-2" />
    <path d="m4.93 4.93 1.41 1.41" />
    <path d="m19.07 19.07-1.41-1.41" />
  </IconSvg>
);

// ── Category Default Icons ─────────────────────────────────────

export const DigitalStrategyIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </IconSvg>
);

export const BrandStrategyIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="13.5" cy="6.5" r=".5" fill="currentColor" />
    <circle cx="17.5" cy="10.5" r=".5" fill="currentColor" />
    <circle cx="8.5" cy="7.5" r=".5" fill="currentColor" />
    <circle cx="6.5" cy="12.5" r=".5" fill="currentColor" />
    <path d="M12 2C6.5 2 2 6.5 2 12s4.5 10 10 10c.926 0 1.648-.746 1.648-1.688 0-.437-.18-.835-.437-1.125-.29-.289-.438-.652-.438-1.125a1.64 1.64 0 0 1 1.668-1.668h1.996c3.051 0 5.563-2.512 5.563-5.563C22 6.5 17.5 2 12 2z" />
  </IconSvg>
);

export const PerformanceMarketingIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <line x1="18" y1="20" x2="18" y2="10" />
    <line x1="12" y1="20" x2="12" y2="4" />
    <line x1="6" y1="20" x2="6" y2="14" />
  </IconSvg>
);

export const StrategyPlanningIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <circle cx="12" cy="12" r="10" />
    <polygon points="16.24 7.76 14.12 14.12 7.76 16.24 9.88 9.88 16.24 7.76" />
  </IconSvg>
);

export const LegalOpsIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <path d="m16 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="m2 16 3-8 3 8c-.87.65-1.92 1-3 1s-2.13-.35-3-1Z" />
    <path d="M7 21h10" />
    <path d="M12 3v18" />
    <path d="M3 7h2c2 0 5-1 7-2 2 1 5 2 7 2h2" />
  </IconSvg>
);

export const FallbackAgentIcon = ({ size, className }: IconProps) => (
  <IconSvg size={size} className={className}>
    <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
  </IconSvg>
);

// ── Registry Mapping ───────────────────────────────────────────

export const AGENT_ICON_MAP: Record<string, React.FC<IconProps>> = {
  'Competition Analysis': CompetitionAnalysisIcon,
  'GTM Strategy': GtmStrategyIcon,
  'Product Launch Strategy': ProductLaunchIcon,
  'Social Media Strategy': SocialMediaIcon,
  'Content Calendar': ContentCalendarIcon,
  'Festival/Topical Campaign Strategy': CampaignStrategyIcon,
  'GEO/AEO': GeoAeoIcon,
  'SEO Strategy': SeoStrategyIcon,
  'Seasonal Campaign': SeasonalCampaignIcon,
  'Brand Audit': BrandAuditIcon,
  'Brand Positioning': BrandPositioningIcon,
  'ICP & Personas': IcpPersonasIcon,
  'Campaign Structure Architect': CampaignArchitectIcon,
  'Bidding & Budget Optimizer': BudgetOptimizerIcon,
  'Company Research Agent': CompanyResearchIcon,
  'Competitive Intelligence Agent': CompetitiveIntelligenceIcon,
};

export const CATEGORY_ICON_MAP: Record<string, React.FC<IconProps>> = {
  'digital-strategy': DigitalStrategyIcon,
  'brand-strategy': BrandStrategyIcon,
  'performance-marketing': PerformanceMarketingIcon,
  'strategy-planning': StrategyPlanningIcon,
  'competitive-intelligence': CompetitiveIntelligenceIcon,
  'legal-ops': LegalOpsIcon,
};

/**
 * Returns a sleek, professional React SVG icon element for an agent card.
 */
export function getAgentIcon(title: string, categoryId: string, size = 18): React.ReactElement {
  const IconComponent =
    AGENT_ICON_MAP[title] ||
    CATEGORY_ICON_MAP[categoryId] ||
    FallbackAgentIcon;

  return <IconComponent size={size} />;
}
