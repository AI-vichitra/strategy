import json

questions = {
  'Partnership & Distribution Strategy': [
    {
      'question': 'What is your primary partnership objective?',
      'options': ['Generate Revenue', 'Acquire Customers', 'Expand Distribution', 'Increase Brand Awareness', 'Enter New Markets', 'Access New Technology', 'Strategic Alliances'],
      'multiSelect': False
    },
    {
      'question': 'What type of business are you?',
      'options': ['SaaS', 'E-commerce', 'Agency', 'Professional Services', 'Healthcare', 'Real Estate', 'Marketplace', 'Consumer Brand', 'other'],
      'multiSelect': False
    },
    {
      'question': 'Which partnership model interests you most?',
      'options': ['Referral Partners', 'Resellers', 'Affiliates', 'Strategic Alliances', 'Technology Integrations', 'Channel Partners', 'other'],
      'multiSelect': False
    }
  ],
  'Revenue Model Strategy': [
    {
      'question': 'What best describes your current revenue model?',
      'options': ['Subscription (SaaS)', 'One-Time Purchase', 'Services', 'Marketplace', 'Advertising', 'Licensing', 'Multiple Revenue Streams', 'Pre-Revenue'],
      'multiSelect': False
    },
    {
      'question': 'What is your primary monetization goal?',
      'options': ['Increase Revenue', 'Improve Profitability', 'Introduce New Revenue Streams', 'Improve Pricing', 'Increase Customer Lifetime Value', 'Reduce Customer Churn'],
      'multiSelect': True
    },
    {
      'question': 'What is your biggest revenue challenge?',
      'options': ['Pricing', 'Customer Acquisition Cost', 'Low Retention', 'Low Conversion', 'Limited Revenue Streams', 'Weak Upsells', 'Unsure'],
      'multiSelect': False
    }
  ],
  'Campaign Structure Architect': [
    {
      'question': 'Which advertising platform are you using?',
      'options': ['Google Ads', 'Meta Ads', 'LinkedIn Ads', 'Microsoft Ads', 'Multiple Platforms', 'others'],
      'multiSelect': True
    },
    {
      'question': 'What is your primary campaign objective?',
      'options': ['Lead Generation', 'Sales', 'App Installs', 'Brand Awareness', 'Website Traffic', 'Product Launch', 'others'],
      'multiSelect': True
    },
    {
      'question': 'What best describes your advertising maturity?',
      'options': ['Never Run Ads', 'Beginner', 'Intermediate', 'Advanced', 'Enterprise Scale'],
      'multiSelect': True
    }
  ],
  'Market Sizing & Entry': [
    {
      'question': 'Which market are you evaluating?',
      'options': ['UAE', 'Saudi Arabia', 'US Healthcare', 'AI CRM Software', 'Luxury Real Estate India', 'Other'],
      'multiSelect': False
    },
    {
      'question': 'What is your objective?',
      'options': ['Launch a New Business', 'Launch a New Product', 'Enter a New Geography', 'Enter a New Customer Segment', 'Expansion Planning', 'Investment Evaluation'],
      'multiSelect': True
    }
  ],
  'ICP & Personas': [
    {
      'question': 'Which customer group drives the most value for your business today?',
      'options': ['Consumers', 'Small Businesses', 'Mid-Market Companies', 'Enterprise Organizations', 'Government', 'Not Sure'],
      'multiSelect': False
    },
    {
      'question': 'What is your biggest customer acquisition challenge?',
      'options': ['Wrong Leads', 'Low Conversion', 'Long Sales Cycle', 'Low Awareness', 'High CAC', 'Poor Retention', 'Not Sure'],
      'multiSelect': False
    },
    {
      'question': 'What is your primary growth objective?',
      'options': ['More Leads', 'Higher Conversions', 'Larger Deals', 'Better Retention', 'Market Expansion', 'Product Adoption'],
      'multiSelect': False
    }
  ],
  'Attribution & Measurement Agent': [
    {
      'question': 'What marketing channels are you currently using?',
      'options': ['Google Ads', 'Meta Ads', 'LinkedIn Ads', 'SEO', 'Email Marketing', 'Organic Social', 'Partnerships', 'Multiple Channels'],
      'multiSelect': True
    },
    {
      'question': 'What is your biggest measurement challenge?',
      'options': ["Can't identify what drives conversions", 'Inaccurate attribution', 'Missing tracking', 'Reporting is fragmented', 'No dashboarding', 'Unsure'],
      'multiSelect': False
    },
    {
      'question': 'What decision do you want attribution to improve?',
      'options': ['Budget Allocation', 'Campaign Optimization', 'Channel Performance', 'CAC Reduction', 'Revenue Attribution', 'Executive Reporting'],
      'multiSelect': False
    }
  ],
  'Bidding & Budget Optimizer': [
    {
      'question': 'Which advertising platforms are you actively using?',
      'options': ['Google Ads', 'Meta Ads', 'LinkedIn Ads', 'Microsoft Ads', 'Multiple Platforms'],
      'multiSelect': True
    },
    {
      'question': 'What is your primary advertising objective?',
      'options': ['Lead Generation', 'Sales', 'ROAS Improvement', 'Scale Spend', 'Lower CPA', 'Brand Awareness'],
      'multiSelect': True
    },
    {
      'question': 'What is your biggest performance challenge?',
      'options': ['High CPA', 'Low ROAS', 'Low Conversion Rate', 'Limited Budget', 'Scaling Issues', 'Unstable Performance'],
      'multiSelect': False
    }
  ],
  'Legal Agreement Drafter': [
    {
      'question': 'What type of agreement do you need?',
      'options': ['NDA', 'Service Agreement', 'Partnership Agreement', 'Employment Agreement', 'Vendor Agreement', 'Contractor Agreement', 'Other'],
      'multiSelect': True
    },
    {
      'question': 'Which party are you?',
      'options': ['Service Provider', 'Client', 'Employer', 'Employee', 'Business Partner', 'Vendor'],
      'multiSelect': False
    },
    {
      'question': 'What jurisdiction should this agreement follow?',
      'options': ['India', 'United States', 'United Kingdom', 'UAE', 'Australia', 'Other'],
      'multiSelect': False
    }
  ]
}

# format them
out_str = ""
for key, qs in questions.items():
    out_str += f"  '{key}': [\n"
    for q in qs:
        out_str += "    {\n"
        out_str += f"      question: {json.dumps(q['question'])},\n"
        out_str += f"      options: {json.dumps(q['options'])},\n"
        out_str += f"      multiSelect: {'true' if q['multiSelect'] else 'false'}\n"
        out_str += "    },\n"
    out_str += "  ],\n"

# Brand Personality & Guidelines
brand_pers_str = """  'Brand Personality and Guidelines': [
    {
      question: 'How do you want your brand to be perceived?',
      options: ['Professional', 'Innovative', 'Premium', 'Friendly', 'Authoritative', 'Playful', 'Luxury', 'Trustworthy', 'Bold', 'Approachable'],
      multiSelect: true
    },
    {
      question: 'Who is your primary target customer?',
      options: ['B2C', 'B2B', 'B2B AND B2C', 'Other'],
      multiSelect: false
    },
    {
      id: 'bp_q2_b2c',
      question: 'Select B2C Target Customers:',
      options: ['Consumers (Mass Market)', 'Affluent / Premium Consumers', 'Gen Z', 'Millennials', 'Parents & Families'],
      multiSelect: true,
      condition: (answers) => {
        const ans = answers['Who is your primary target customer?'] || '';
        return ans.includes('B2C') || ans.includes('B2B AND B2C');
      }
    },
    {
      id: 'bp_q2_b2b',
      question: 'Select B2B Target Customers:',
      options: ['Small Businesses (1–50 employees)', 'Mid-Market Companies (51–1000 employees)', 'Enterprise Organizations (1000+ employees)', 'Government / Public Sector'],
      multiSelect: true,
      condition: (answers) => {
        const ans = answers['Who is your primary target customer?'] || '';
        return ans.includes('B2B') || ans.includes('B2B AND B2C');
      }
    },
    {
      question: 'Which brands do you admire from a communication perspective?',
      options: ['Apple', 'Nike', 'HubSpot', 'Tesla', 'Airbnb', 'Other'],
      multiSelect: false
    }
  ],
"""

out_str += brand_pers_str

with open("frontend/src/components/builder/MainContent.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Insert before `};` of `agentQuestions`
target = "};\n\nconst agentPrompts:"
new_content = content.replace(target, out_str + target)

with open("frontend/src/components/builder/MainContent.tsx", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Done")
