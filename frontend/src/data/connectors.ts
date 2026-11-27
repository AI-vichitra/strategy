export type ConnectorType = 'api' | 'oauth' | 'database';
export type ConnectorStatus = 'not_connected' | 'connected' | 'error';

export interface Connector {
  id: string;
  name: string;
  description: string;
  domain: string;
  type: ConnectorType;
  logoUrl?: string;
}

export const CUSTOM_LOGOS: Record<string, string> = {
  // Direct connector IDs
  googleads: '/logos/google/google-ads.svg',
  ga: '/logos/google/google-analytics.svg',
  gsc: '/logos/google/google-search-console.svg',
  gemini: '/logos/google/google-gemini.svg',
  gmail: '/logos/google/gmail.svg',
  gcal: '/logos/google/google-calendar.svg',
  gmeet: '/logos/google/google-meet.svg',
  gdrive: '/logos/google/google-drive.svg',
  gdocs: '/logos/google/google-docs.svg',
  gsheets: '/logos/google/google-sheets.svg',
  gforms: '/logos/google/google-forms.svg',
  looker: '/logos/google/google-looker.svg',
  bigquery: '/logos/google/google-bigquery.svg',
  gcs: '/logos/google/google-cloud-storage.svg',
  firebase: '/logos/google/firebase.svg',
  gappsscript: '/logos/google/google-apps-script.svg',
  youtube: '/logos/google/youtube.svg',

  // By connector domain
  'ads.google.com': '/logos/google/google-ads.svg',
  'analytics.google.com': '/logos/google/google-analytics.svg',
  'search.google.com': '/logos/google/google-search-console.svg',
  'calendar.google.com': '/logos/google/google-calendar.svg',
  'meet.google.com': '/logos/google/google-meet.svg',
  'drive.google.com': '/logos/google/google-drive.svg',
  'docs.google.com': '/logos/google/google-docs.svg',
  'sheets.google.com': '/logos/google/google-sheets.svg',
  'forms.google.com': '/logos/google/google-forms.svg',
  'looker.com': '/logos/google/google-looker.svg',
  'firebase.google.com': '/logos/google/firebase.svg',
  'script.google.com': '/logos/google/google-apps-script.svg',
  'youtube.com': '/logos/google/youtube.svg',
  'gmail.com': '/logos/google/gmail.svg',
};

// Known domain mappings for agent registry connector names to prevent bare-word 404s
export const KNOWN_DOMAINS: Record<string, string> = {
  'tavily': 'tavily.com',
  'instagram': 'instagram.com',
  'meta ads': 'facebook.com',
  'meta': 'meta.com',
  'metaads': 'facebook.com',
  'facebook': 'facebook.com',
  'mailchimp': 'mailchimp.com',
  'tiktok': 'tiktok.com',
  'google': 'google.com',
  'google ads': 'ads.google.com',
  'google analytics': 'analytics.google.com',
  'google search console': 'search.google.com',
  'google calendar': 'calendar.google.com',
  'google meet': 'meet.google.com',
  'google drive': 'drive.google.com',
  'google docs': 'docs.google.com',
  'google sheets': 'sheets.google.com',
  'google forms': 'forms.google.com',
  'youtube': 'youtube.com',
  'reddit': 'reddit.com',
  'bing webmaster': 'bing.com',
  'bing': 'bing.com',
  'ahrefs': 'ahrefs.com',
  'semrush': 'semrush.com',
  'semrush api key': 'semrush.com',
  'serpapi': 'serpapi.com',
  'firecrawl': 'firecrawl.dev',
  'exa': 'exa.ai',
  'apollo': 'apollo.io',
  'hubspot': 'hubspot.com',
  'salesforce': 'salesforce.com',
  'notion': 'notion.so',
  'linkedin': 'linkedin.com',
  'slack': 'slack.com',
  'discord': 'discord.com',
  'github': 'github.com',
  'gitlab': 'gitlab.com',
  'wordpress': 'wordpress.org',
  'shopify': 'shopify.com',
  'canva': 'canva.com',
  'airtable': 'airtable.com',
  'clickup': 'clickup.com',
  'monday': 'monday.com',
  'trello': 'trello.com',
  'asana': 'asana.com',
  'jira': 'atlassian.com',
  'linear': 'linear.app',
  'tableau': 'tableau.com',
  'openai': 'openai.com',
  'anthropic': 'anthropic.com',
  'perplexity': 'perplexity.ai',
  'zoominfo': 'zoominfo.com',
  'hunter': 'hunter.io',
  'findymail': 'findymail.com',
  'apify': 'apify.com',
  'phantombuster': 'phantombuster.com',
  'browserbase': 'browserbase.com',
};

export const connectors: Connector[] = [
  // ── API Connectors ──────────────────────────────────
  { id: 'openai', name: 'OpenAI API Key', description: 'Connect your OpenAI account for GPT models', domain: 'openai.com', type: 'api' },
  { id: 'qwen', name: 'Qwen API Key', description: 'Connect Alibaba Qwen models', domain: 'aliyun.com', type: 'api' },
  { id: 'anthropic', name: 'Anthropic API Key', description: 'Connect Claude models for advanced reasoning', domain: 'anthropic.com', type: 'api' },
  { id: 'gemini', name: 'Google Gemini API Key', description: 'Integrate Google Gemini capabilities', domain: 'google.com', type: 'api', logoUrl: '/logos/google/google-gemini.svg' },
  { id: 'perplexity', name: 'Perplexity API Key', description: 'Real-time search and AI answers', domain: 'perplexity.ai', type: 'api' },
  { id: 'firecrawl', name: 'Firecrawl', description: 'Web scraping and crawling API', domain: 'firecrawl.dev', type: 'api' },
  { id: 'exa', name: 'Exa', description: 'AI search engine and knowledge graph', domain: 'exa.ai', type: 'api' },
  { id: 'serpapi', name: 'SerpAPI', description: 'Real-time search engine results API', domain: 'serpapi.com', type: 'api' },
  { id: 'ahrefs', name: 'Ahrefs', description: 'SEO tools and resources to grow search traffic', domain: 'ahrefs.com', type: 'api' },
  { id: 'semrush', name: 'Semrush API Key', description: 'Online visibility management platform', domain: 'semrush.com', type: 'api' },
  { id: 'hunter', name: 'Hunter.io API Key', description: 'Find professional email addresses', domain: 'hunter.io', type: 'api' },
  { id: 'findymail', name: 'Findymail', description: 'B2B email finder and verifier', domain: 'findymail.com', type: 'api' },
  { id: 'zoominfo', name: 'ZoomInfo API Key', description: 'B2B contact and company database', domain: 'zoominfo.com', type: 'api' },
  { id: 'reddit', name: 'Reddit', description: 'Network of communities and discussions', domain: 'reddit.com', type: 'api' },
  { id: 'x', name: 'X', description: 'Interact with X for social media management', domain: 'x.com', type: 'api' },
  { id: 'youtube', name: 'YouTube', description: 'Video sharing platform', domain: 'youtube.com', type: 'api', logoUrl: '/logos/google/youtube.svg' },
  { id: 'browserbase', name: 'Browserbase', description: 'Headless browser infrastructure', domain: 'browserbase.com', type: 'api' },
  { id: 'apify', name: 'Apify API Key', description: 'Web scraping and automation platform', domain: 'apify.com', type: 'api' },
  { id: 'phantombuster', name: 'PhantomBuster API Key', description: 'Lead generation and automation tool', domain: 'phantombuster.com', type: 'api' },
  { id: 'apollo', name: 'Apollo', description: 'B2B sales intelligence and engagement', domain: 'apollo.io', type: 'api' },
  { id: 'tavily', name: 'Tavily', description: 'Search engine optimized for LLMs', domain: 'tavily.com', type: 'api' },

  // ── OAuth Connectors ────────────────────────────────
  { id: 'instagram', name: 'Instagram', description: 'Instagram social media platform', domain: 'instagram.com', type: 'oauth' },
  { id: 'metaads', name: 'Meta Ads', description: 'Meta Facebook and Instagram Ads management', domain: 'facebook.com', type: 'oauth' },
  { id: 'mailchimp', name: 'Mailchimp', description: 'Marketing automation and email marketing service', domain: 'mailchimp.com', type: 'oauth' },
  { id: 'gsc', name: 'Google Search Console', description: 'Track search traffic and performance', domain: 'search.google.com', type: 'oauth', logoUrl: '/logos/google/google-search-console.svg' },
  { id: 'ga', name: 'Google Analytics', description: 'Transform website data into actionable insights', domain: 'analytics.google.com', type: 'oauth', logoUrl: '/logos/google/google-analytics.svg' },
  { id: 'googleads', name: 'Google Ads', description: 'Manage and track ad campaigns', domain: 'ads.google.com', type: 'oauth', logoUrl: '/logos/google/google-ads.svg' },
  { id: 'bing', name: 'Bing Webmaster', description: 'Optimize your site for Bing search', domain: 'bing.com', type: 'oauth' },
  { id: 'linkedin', name: 'LinkedIn', description: 'Professional networking and lead generation', domain: 'linkedin.com', type: 'oauth' },
  { id: 'hubspot', name: 'HubSpot', description: 'Inbound marketing, sales, and service software', domain: 'hubspot.com', type: 'oauth' },
  { id: 'salesforce', name: 'Salesforce', description: 'Customer relationship management platform', domain: 'salesforce.com', type: 'oauth' },
  { id: 'attio', name: 'Attio', description: 'Data-driven CRM for modern teams', domain: 'attio.com', type: 'oauth' },
  { id: 'pipedrive', name: 'Pipedrive', description: 'Sales CRM and pipeline management', domain: 'pipedrive.com', type: 'oauth' },
  { id: 'freshsales', name: 'Freshsales', description: 'Sales CRM software by Freshworks', domain: 'freshworks.com', type: 'oauth' },
  { id: 'salesloft', name: 'Salesloft', description: 'Sales engagement platform', domain: 'salesloft.com', type: 'oauth' },
  { id: 'zendesk', name: 'Zendesk', description: 'Customer service software and support ticket system', domain: 'zendesk.com', type: 'oauth' },
  { id: 'freshdesk', name: 'Freshdesk', description: 'Customer support software', domain: 'freshworks.com', type: 'oauth' },
  { id: 'intercom', name: 'Intercom', description: 'Customer messaging platform', domain: 'intercom.com', type: 'oauth' },
  { id: 'gmail', name: 'Gmail', description: 'Automate email workflows and enhance communication', domain: 'gmail.com', type: 'oauth', logoUrl: '/logos/google/gmail.svg' },
  { id: 'microsoft', name: 'Microsoft', description: 'Automate email communications and schedules', domain: 'microsoft.com', type: 'oauth' },
  { id: 'outlook', name: 'Outlook Calendar', description: 'Manage calendar events and check availability', domain: 'outlook.com', type: 'oauth' },
  { id: 'gcal', name: 'Google Calendar', description: 'Streamline scheduling and event coordination', domain: 'calendar.google.com', type: 'oauth', logoUrl: '/logos/google/google-calendar.svg' },
  { id: 'gmeet', name: 'Google Meet', description: 'Video conferencing and meetings', domain: 'meet.google.com', type: 'oauth', logoUrl: '/logos/google/google-meet.svg' },
  { id: 'zoom', name: 'Zoom', description: 'Video communications platform', domain: 'zoom.us', type: 'oauth' },
  { id: 'slack', name: 'Slack', description: 'Team messaging and collaboration', domain: 'slack.com', type: 'oauth' },
  { id: 'teams', name: 'Microsoft Teams', description: 'Workspace for real-time collaboration', domain: 'teams.microsoft.com', type: 'oauth' },
  { id: 'discord', name: 'Discord', description: 'Voice, video and text chat platform', domain: 'discord.com', type: 'oauth' },
  { id: 'notion', name: 'Notion', description: 'All-in-one workspace for notes and docs', domain: 'notion.so', type: 'oauth' },
  { id: 'confluence', name: 'Confluence', description: 'Team workspace and knowledge base', domain: 'atlassian.com', type: 'oauth' },
  { id: 'gdrive', name: 'Google Drive', description: 'Streamline file organization and document workflows', domain: 'drive.google.com', type: 'oauth', logoUrl: '/logos/google/google-drive.svg' },
  { id: 'gdocs', name: 'Google Docs', description: 'Automate document creation and content management', domain: 'docs.google.com', type: 'oauth', logoUrl: '/logos/google/google-docs.svg' },
  { id: 'gsheets', name: 'Google Sheets', description: 'Automate data processing tasks seamlessly', domain: 'sheets.google.com', type: 'oauth', logoUrl: '/logos/google/google-sheets.svg' },
  { id: 'excel', name: 'Microsoft Excel', description: 'Spreadsheet software for data analysis', domain: 'excel.office.com', type: 'oauth' },
  { id: 'word', name: 'Microsoft Word', description: 'Word processing software', domain: 'word.office.com', type: 'oauth' },
  { id: 'airtable', name: 'Airtable', description: 'Low-code platform for building collaborative apps', domain: 'airtable.com', type: 'oauth' },
  { id: 'clickup', name: 'ClickUp', description: 'All-in-one productivity platform', domain: 'clickup.com', type: 'oauth' },
  { id: 'monday', name: 'Monday.com', description: 'Work OS for teams', domain: 'monday.com', type: 'oauth' },
  { id: 'trello', name: 'Trello', description: 'Visual project management tool', domain: 'trello.com', type: 'oauth' },
  { id: 'asana', name: 'Asana', description: 'Work management platform', domain: 'asana.com', type: 'oauth' },
  { id: 'jira', name: 'Jira', description: 'Issue and project tracking software', domain: 'atlassian.com', type: 'oauth' },
  { id: 'linear', name: 'Linear', description: 'Issue tracking for modern teams', domain: 'linear.app', type: 'oauth' },
  { id: 'github', name: 'GitHub', description: 'Streamline your development workflow and automate repositories', domain: 'github.com', type: 'oauth' },
  { id: 'gitlab', name: 'GitLab', description: 'DevOps software package', domain: 'gitlab.com', type: 'oauth' },
  { id: 'tableau', name: 'Tableau', description: 'Visual analytics platform', domain: 'tableau.com', type: 'oauth' },
  { id: 'looker', name: 'Google Looker', description: 'Enterprise platform for BI and analytics', domain: 'looker.com', type: 'oauth', logoUrl: '/logos/google/google-looker.svg' },
  { id: 'sigma', name: 'Sigma Computing', description: 'Cloud analytics platform', domain: 'sigmacomputing.com', type: 'oauth' },
  { id: 'wordpress', name: 'WordPress', description: 'Content management system', domain: 'wordpress.org', type: 'oauth' },
  { id: 'webflow', name: 'Webflow', description: 'Visual web development platform', domain: 'webflow.com', type: 'oauth' },
  { id: 'canva', name: 'Canva', description: 'Online design and publishing tool', domain: 'canva.com', type: 'oauth' },
  { id: 'shopify', name: 'Shopify', description: 'E-commerce platform for online stores', domain: 'shopify.com', type: 'oauth' },
  { id: 'greenhouse', name: 'Greenhouse', description: 'Applicant tracking system and recruiting software', domain: 'greenhouse.io', type: 'oauth' },
  { id: 'ashby', name: 'Ashby', description: 'All-in-one recruiting platform', domain: 'ashbyhq.com', type: 'oauth' },
  { id: 'gong', name: 'Gong', description: 'Revenue intelligence platform', domain: 'gong.io', type: 'oauth' },
  { id: 'gforms', name: 'Google Forms', description: 'Create and analyze surveys', domain: 'forms.google.com', type: 'oauth', logoUrl: '/logos/google/google-forms.svg' },
  { id: 'dropbox', name: 'Dropbox', description: 'File hosting and cloud storage', domain: 'dropbox.com', type: 'oauth' },
  { id: 'box', name: 'Box', description: 'Cloud content management and file sharing', domain: 'box.com', type: 'oauth' },
  { id: 'calendly', name: 'Calendly', description: 'Automated scheduling software', domain: 'calendly.com', type: 'oauth' },
  { id: 'calcom', name: 'Cal.com', description: 'Open source scheduling infrastructure', domain: 'cal.com', type: 'oauth' },

  // ── Database Connectors ─────────────────────────────
  { id: 'postgres', name: 'PostgreSQL', description: 'Open source relational database', domain: 'postgresql.org', type: 'database' },
  { id: 'bigquery', name: 'BigQuery', description: 'Enterprise data warehouse', domain: 'cloud.google.com', type: 'database', logoUrl: '/logos/google/google-bigquery.svg' },
  { id: 'snowflake', name: 'Snowflake', description: 'Data cloud platform', domain: 'snowflake.com', type: 'database' },
  { id: 'databricks', name: 'Databricks', description: 'Unified data analytics platform', domain: 'databricks.com', type: 'database' },
  { id: 'clickhouse', name: 'ClickHouse', description: 'Column-oriented database management system', domain: 'clickhouse.com', type: 'database' },
  { id: 'gcs', name: 'Google Cloud Storage', description: 'Object storage for developers and enterprises', domain: 'cloud.google.com', type: 'database', logoUrl: '/logos/google/google-cloud-storage.svg' },
  { id: 'supabase', name: 'Supabase', description: 'Open source Firebase alternative', domain: 'supabase.com', type: 'database' },
  { id: 'firebase', name: 'Firebase', description: 'App development platform by Google', domain: 'firebase.google.com', type: 'database', logoUrl: '/logos/google/firebase.svg' },
  { id: 'netsuite', name: 'NetSuite', description: 'Cloud business software suite', domain: 'netsuite.com', type: 'database' },
  { id: 'snowflakepat', name: 'Snowflake PAT', description: 'Personal Access Token for Snowflake', domain: 'snowflake.com', type: 'api' },
  { id: 'gappsscript', name: 'Google Apps Script', description: 'Rapid application development platform', domain: 'script.google.com', type: 'api', logoUrl: '/logos/google/google-apps-script.svg' },
  { id: 'aws', name: 'AWS Credentials', description: 'Amazon Web Services access', domain: 'aws.amazon.com', type: 'api' },
];

export const getLogoUrl = (domainOrId: string, connectorId?: string): string => {
  if (!domainOrId && !connectorId) return '';

  const clean = (s: string) => s.toLowerCase().trim().replace(/^https?:\/\//, '').replace(/\/.*$/, '');
  const idKey = connectorId ? clean(connectorId) : '';
  const domainKey = domainOrId ? clean(domainOrId) : '';

  if (idKey && CUSTOM_LOGOS[idKey]) return CUSTOM_LOGOS[idKey];
  if (domainKey && CUSTOM_LOGOS[domainKey]) return CUSTOM_LOGOS[domainKey];

  const matched = connectors.find(
    c => (idKey && (clean(c.id) === idKey || clean(c.name) === idKey)) ||
         (domainKey && (clean(c.id) === domainKey || clean(c.domain) === domainKey || clean(c.name) === domainKey))
  );

  if (matched?.logoUrl) return matched.logoUrl;
  if (matched && CUSTOM_LOGOS[matched.id]) return CUSTOM_LOGOS[matched.id];

  // Resolve target domain: if known domain mapping exists, prioritize it
  let targetDomain = matched?.domain || KNOWN_DOMAINS[idKey] || KNOWN_DOMAINS[domainKey] || domainKey;

  // Never send a bare name without a TLD to Google favicon API (causes 404)
  if (!targetDomain.includes('.')) {
    if (KNOWN_DOMAINS[targetDomain]) {
      targetDomain = KNOWN_DOMAINS[targetDomain];
    } else {
      targetDomain = `${targetDomain.replace(/\s+/g, '')}.com`;
    }
  }

  return `https://www.google.com/s2/favicons?sz=64&domain_url=${encodeURIComponent(targetDomain)}`;
};
