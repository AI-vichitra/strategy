import re

file_path = "c:/Users/Cog/Desktop/Strategy/frontend/src/components/builder/TemplateGrid.tsx"

mapping = {
    "Meeting Prep Agent": ["LinkedIn", "Apollo", "ZoomInfo", "Google Calendar", "Google Docs", "Exa", "Firecrawl"],
    "CRM Pipeline Reporter": ["Salesforce", "HubSpot", "Google Sheets", "Google Docs"],
    "Lead Enrichment Agent": ["Apollo", "ZoomInfo", "Hunter.io API Key", "Findymail", "Google Sheets"],
    "Sales Prospecting Agent": ["Apollo", "LinkedIn", "ZoomInfo", "Hunter.io API Key", "Gmail", "Google Calendar"],
    "Competitor Research Agent": ["Firecrawl", "Exa", "SerpAPI", "Reddit"],
    "Cold Outreach Writer": ["LinkedIn", "Apollo", "Gmail", "Exa"],
    "Sales Pitch Generator": ["HubSpot", "Salesforce", "OpenAI API Key"],
    "Cold Calling Script Generator": ["LinkedIn", "HubSpot", "Salesforce", "OpenAI API Key"],

    "Spreadsheet Analyst": ["Google Sheets", "Microsoft Excel"],
    "PostgreSQL Query Agent": ["PostgreSQL"],
    "BigQuery Data Analyst": ["BigQuery"],
    "Snowflake Data Analyst": ["Snowflake"],
    "Report Generator": ["BigQuery", "Snowflake", "Google Docs"],
    "Data Cleanup Agent": ["Google Sheets", "Microsoft Excel"],

    "GEO/AEO": ["Google Search Console", "Ahrefs", "Semrush API Key", "Bing Webmaster", "Firecrawl", "SerpAPI"],
    "Social Media Strategy": ["LinkedIn", "X", "Reddit", "YouTube"],
    "Festival/Topical Campaign Strategy": ["Google Calendar", "Semrush API Key", "Exa", "Reddit", "Firecrawl"],
    "Trend Strategy": ["X", "Reddit", "YouTube", "Exa"],
    "Seasonal Campaign": ["Google Analytics", "Google Search Console", "Semrush API Key"],
    "Legal Agreement Drafter": ["Google Docs", "Notion"],
    "Competition Analysis": ["Firecrawl", "Ahrefs", "Semrush API Key", "Exa"],
    "Content Calendar": ["Semrush API Key", "Reddit", "YouTube", "Notion", "Google Docs"],
    "SEO Strategy": ["Google Search Console", "Ahrefs", "Semrush API Key", "Bing Webmaster", "Firecrawl"],
    "Business Plan Generator": ["Exa", "Firecrawl", "Google Docs"],

    "Brand Audit": ["Google Analytics", "Google Search Console", "Reddit", "X", "Firecrawl"],
    "Brand Positioning": ["Exa", "Firecrawl"],
    "Brand Personality and Guidelines": ["LinkedIn", "X", "Firecrawl"],

    "Campaign Structure Architect": ["Google Ads", "Google Analytics"],
    "Bidding & Budget Optimizer": ["Google Ads", "Google Analytics"],
    "Attribution & Measurement Agent": ["Google Analytics", "Google Ads", "BigQuery"],

    "GTM Strategy": ["HubSpot", "Salesforce", "Google Analytics", "Exa"],
    "Product Launch Strategy": ["Google Analytics", "LinkedIn", "X", "Reddit", "Firecrawl"],
    "Market Sizing & Entry": ["Exa", "Firecrawl", "SerpAPI"],
    "ICP & Personas": ["HubSpot", "Salesforce", "Apollo"],
    "Partnership & Distribution Strategy": ["LinkedIn", "Apollo", "HubSpot"],
    "Revenue Model Strategy": ["HubSpot", "Salesforce", "Google Analytics"],

    "Weekly Recap Agent": ["Jira", "ClickUp", "Asana", "Slack", "Google Calendar"],
    "Internal Knowledge Agent": ["Notion", "Google Drive", "Google Docs", "Confluence"],
    "Executive Assistant": ["Gmail", "Google Calendar", "Google Drive", "Google Docs", "Slack"],
    "Daily Standup Agent": ["Jira", "ClickUp", "Linear", "Google Calendar"],
    "Inbox Manager": ["Gmail", "Microsoft Outlook"],
    "Meeting Notes Agent": ["Google Meet", "Zoom", "Gong", "Google Docs"],

    "Deep Research Agent": ["Exa", "Firecrawl", "SerpAPI", "Perplexity API Key"],
    "Recruiting Sourcer": ["LinkedIn", "Greenhouse", "Ashby"],
    "News & Trends Monitor": ["Exa", "Reddit", "X", "Firecrawl"],
    "Market Research Agent": ["Exa", "Firecrawl", "SerpAPI"],
    "Company Research Agent": ["LinkedIn", "Exa", "Firecrawl"],
    "Competitive Intelligence Agent": ["Firecrawl", "Ahrefs", "Reddit", "X"],

    "Feedback Digest Agent": ["Zendesk", "Freshdesk", "Intercom"],
    "Support Inbox Agent": ["Zendesk", "Freshdesk", "Intercom", "Notion"],
    "Customer Onboarding Agent": ["HubSpot", "Salesforce", "Gmail", "Google Calendar"],
    "Customer Lookup Agent": ["HubSpot", "Salesforce", "Zendesk"],
    "Help Docs Writer": ["Notion", "Google Docs", "Confluence"],
    "Issue Tracker Agent": ["GitHub", "Jira", "Linear"]
}

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

def replacer(match):
    title = match.group(1)
    if title in mapping:
        new_icons = mapping[title]
        # format as: connectors: ['LinkedIn', 'Apollo', ...],
        connectors_str = "connectors: [" + ", ".join([f"'{c}'" for c in new_icons]) + "],"
        return f"title: '{title}',\n    desc: {match.group(2)},\n    {connectors_str}"
    
    # If not found in mapping, replace with empty
    return f"title: '{title}',\n    desc: {match.group(2)},\n    connectors: [],"

# Matches title, desc, and icons.
new_content = re.sub(
    r"title:\s*'([^']+)',\n\s*desc:\s*(.*?),?\n\s*icons:\s*\[.*?\]\,?",
    replacer,
    content
)

# Remove the renderIcon function and any unneeded imports
# We will use getLogoUrl from connectors.ts
new_content = re.sub(r"const renderIcon = \(type: string, color: string\) => \{.*?\};\n\n", "", new_content, flags=re.DOTALL)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(new_content)

print("Updated templates in TemplateGrid.tsx")
