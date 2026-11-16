/**
 * Per-agent and per-category icon assignments for the agent catalog.
 *
 * NOTE: the previous hardcoded `allTemplates` array (TemplateGrid.tsx) never had
 * a per-agent icon field — cards only ever showed connector favicons. These emoji
 * assignments are new, not "restored" originals; ORIGINAL_AGENT_ICONS below just
 * covers the same 16 titles that existed before the agent catalog moved to the
 * backend registry, so their look stays stable going forward.
 */

export const ORIGINAL_AGENT_ICONS: Record<string, string> = {
  'Competition Analysis': '🔍',
  'GTM Strategy': '🚀',
  'Product Launch Strategy': '📦',
  'Social Media Strategy': '📱',
  'Content Calendar': '🗓️',
  'Festival/Topical Campaign Strategy': '🎉',
  'GEO/AEO': '🤖',
  'SEO Strategy': '📈',
  'Seasonal Campaign': '🍂',
  'Brand Audit': '🪞',
  'Brand Positioning': '🎯',
  'ICP & Personas': '👥',
  'Campaign Structure Architect': '🏗️',
  'Bidding & Budget Optimizer': '💰',
  'Company Research Agent': '🏢',
  'Competitive Intelligence Agent': '🛰️',
};

export const CATEGORY_DEFAULT_ICONS: Record<string, string> = {
  'digital-strategy': '📡',
  'brand-strategy': '🎨',
  'performance-marketing': '📊',
  'strategy-planning': '🧭',
  'competitive-intelligence': '🛰️',
  'legal-ops': '⚖️',
};

const FALLBACK_ICON = '✨';

/** Always returns a non-empty icon — never render a card with no icon. */
export function getAgentIcon(title: string, categoryId: string): string {
  return (
    ORIGINAL_AGENT_ICONS[title] ||
    CATEGORY_DEFAULT_ICONS[categoryId] ||
    FALLBACK_ICON
  );
}
