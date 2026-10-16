import json

questions = {
  'Product Launch Strategy': [
    {
      'question': 'What are you launching?',
      'options': ['New Product', 'New Service', 'New Feature', 'New Brand', 'New App / Software', 'Existing Product Relaunch', 'Other'],
      'multiSelect': False
    },
    {
      'question': 'What is the primary objective of this launch?',
      'options': ['Generate Sales', 'Generate Leads', 'Build Awareness', 'Acquire Users', 'Drive Product Adoption', 'Enter a New Market', 'Validate Demand', 'Increase Word of Mouth', 'Other'],
      'multiSelect': True
    },
    {
      'question': 'What is your planned launch timeline?',
      'options': ['Within 30 Days', '1–3 Months', '3–6 Months', '6–12 Months', 'Flexible'],
      'multiSelect': False
    }
  ],
  'Social Media Strategy': [
    {
      'question': 'Which social platforms are your priority?',
      'options': ['LinkedIn', 'Instagram', 'Facebook', 'X (Twitter)', 'YouTube', 'Reddit', 'Pinterest', 'Multiple Platform'],
      'multiSelect': True
    },
    {
      'question': 'What is your primary social media goal?',
      'options': ['Brand Awareness', 'Lead Generation', 'Sales', 'Community Building', 'Customer Engagement', 'Thought Leadership', 'Product Adoption', 'Customer Support', 'OTHERS'],
      'multiSelect': False
    },
    {
      'question': 'What is your biggest social media challenge?',
      'options': ['Low Reach', 'Low Engagement', 'Low Followers', 'Low Leads', 'Low Conversions', 'Inconsistent Content', 'Lack of Content Ideas', 'Limited Resources', 'Unsure What Works', 'OTHERS'],
      'multiSelect': False
    }
  ],
  'Content Calendar': [
    {
      'question': 'Which channels need content?',
      'options': ['Blog', 'LinkedIn', 'Instagram', 'Facebook', 'X', 'YouTube', 'Email Newsletter', 'Multiple Channels', 'Other'],
      'multiSelect': True
    },
    {
      'question': 'What is your primary content objective?',
      'options': ['Brand Awareness', 'Lead Generation', 'Sales', 'SEO Growth', 'GEO / AI Visibility', 'Customer Education', 'Community Building', 'Thought Leadership', 'others'],
      'multiSelect': False
    },
    {
      'question': 'What content frequency can your team realistically maintain?',
      'options': ['Daily', '3–5 Times Per Week', 'Weekly', 'Bi-Weekly', 'Monthly'],
      'multiSelect': False
    }
  ],
  'Festival Campaign': [
    {
      'question': 'Which festival or event do you want to build a campaign around?',
      'options': ['Diwali', 'Christmas', 'New Year', "Black Friday / Cyber Monday", "Valentine's Day", 'Eid', 'Holi', 'Independence Day', 'Industry Event', 'Other'],
      'multiSelect': True
    },
    {
      'question': 'What is the primary objective of this campaign?',
      'options': ['Sales', 'Lead Generation', 'Brand Awareness', 'Customer Engagement', 'Product Launch', 'Customer Retention', 'others'],
      'multiSelect': False
    },
    {
      'question': 'What type of offer are you willing to run?',
      'options': ['Discounts', 'Bundles', 'Free Trial', 'Giveaway', 'Content-Led Campaign', 'No Offer (Brand Campaign)', 'Others'],
      'multiSelect': False
    }
  ],
  'Topical Campaign': [
    {
      'question': 'What is the primary topic you want to build authority around?',
      'options': ['AI Marketing', 'Real Estate Investment', 'Diabetes Care', 'Cybersecurity', 'Other'],
      'multiSelect': False
    },
    {
      'question': 'What is the primary objective?',
      'options': ['SEO Rankings', 'GEO / AI Visibility', 'Lead Generation', 'Thought Leadership', 'Brand Awareness'],
      'multiSelect': True
    },
    {
      'question': 'What is your current content maturity?',
      'options': ['No Existing Content', 'Some Content', 'Large Content Library', 'Industry Authority'],
      'multiSelect': False
    }
  ],
  'Trend Strategy': [
    {
      'question': 'Which trend category matters most?',
      'options': ['Industry Trends', 'Consumer Trends', 'Technology Trends', 'Social Media Trends', 'Market Trends', 'All Relevant Trends'],
      'multiSelect': True
    },
    {
      'question': 'What do you want to achieve from trends?',
      'options': ['Content Ideas', 'Lead Generation', 'Thought Leadership', 'Product Innovation', 'Brand Awareness'],
      'multiSelect': True
    },
    {
      'question': 'How quickly can your team act on opportunities?',
      'options': ['Same Day', 'Within a Week', 'Within a Month', 'Quarterly Planning'],
      'multiSelect': False
    }
  ],
  'Seasonal Campaign': [
    {
      'question': 'Does your business experience seasonal demand?',
      'options': ['Yes', 'No', 'Not Sure'],
      'multiSelect': False
    },
    {
      'question': 'Which season matters most to your business?',
      'options': ['Summer', 'Winter', 'Monsoon', 'Multiple Seasons'],
      'multiSelect': False
    },
    {
      'question': 'What is the primary goal of your seasonal campaigns?',
      'options': ['Increase Sales', 'Generate Leads', 'Increase Footfall', 'Brand Awareness', 'Customer Retention'],
      'multiSelect': False
    }
  ],
  'GEO/AEO': [
    {
      'question': 'Which AI visibility channel matters most to you?',
      'options': ['ChatGPT', 'Google AI Overviews', 'Perplexity', 'Gemini', 'Claude'],
      'multiSelect': True
    },
    {
      'question': 'What is your primary GEO/AEO objective?',
      'options': ['Increase Brand Visibility', 'Generate Leads', 'Increase Website Traffic', 'Become an Industry Authority', 'Improve AI Citations', 'Improve Local Visibility'],
      'multiSelect': True
    },
    {
      'question': 'What best describes your current AI visibility?',
      'options': ['No Visibility', 'Rarely Mentioned', 'Occasionally Mentioned', 'Frequently Mentioned', 'others'],
      'multiSelect': False
    }
  ],
  'SEO': [
    {
      'question': 'What is your primary SEO objective?',
      'options': ['More Organic Traffic', 'More Leads', 'More Sales', 'Local SEO Growth', 'Brand Visibility', 'Thought Leadership'],
      'multiSelect': False
    },
    {
      'question': 'What is your biggest SEO challenge?',
      'options': ['Low Rankings', 'Low Traffic', 'Lack of Content', 'Technical SEO Issues', 'Backlinks / Authority', 'Local Visibility', 'Unsure'],
      'multiSelect': False
    },
    {
      'question': 'Which keywords matter most to your business?',
      'options': ['AI Marketing', 'CRM Software', 'Luxury Apartments Gurgaon', 'Other'],
      'multiSelect': False
    }
  ],
  'Business Plan Generator': [
    {
      'question': 'What stage is the business currently in?',
      'options': ['Business Idea', 'MVP / Prototype', 'Early Revenue', 'Growing Business', 'Established Business', 'Pivoting Existing Business'],
      'multiSelect': False
    },
    {
      'question': 'What is the primary purpose of this business plan?',
      'options': ['Start the Business', 'Raise Funding', 'Internal Planning', 'Bank Loan', 'Expansion Strategy', 'Investor Pitch'],
      'multiSelect': True
    },
    {
      'question': 'What is your business model?',
      'options': ['SaaS', 'E-commerce', 'Marketplace', 'Agency', 'Professional Services', 'Healthcare', 'Real Estate', 'Mobile App', 'Manufacturing', 'Other'],
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

# Brand Audit needs custom condition logic like GTM Strategy
brand_audit_str = """  'Brand Audit': [
    {
      question: 'What aspect of your brand concerns you most?',
      options: ['Brand Awareness', 'Brand Perception', 'Messaging Clarity', 'Visual Identity', 'Differentiation', 'Trust & Credibility', 'Consistency Across Channels', 'others'],
      multiSelect: false
    },
    {
      question: 'Who is your primary target customer?',
      options: ['B2C', 'B2B', 'B2B AND B2C', 'Other'],
      multiSelect: false
    },
    {
      id: 'ba_q2_b2c',
      question: 'Select B2C Target Customers:',
      options: ['Consumers (Mass Market)', 'Affluent / Premium Consumers', 'Gen Z', 'Millennials', 'Parents & Families'],
      multiSelect: true,
      condition: (answers) => {
        const ans = answers['Who is your primary target customer?'] || '';
        return ans.includes('B2C') || ans.includes('B2B AND B2C');
      }
    },
    {
      id: 'ba_q2_b2b',
      question: 'Select B2B Target Customers:',
      options: ['Small Businesses (1–50 employees)', 'Mid-Market Companies (51–1000 employees)', 'Enterprise Organizations (1000+ employees)', 'Government / Public Sector'],
      multiSelect: true,
      condition: (answers) => {
        const ans = answers['Who is your primary target customer?'] || '';
        return ans.includes('B2B') || ans.includes('B2B AND B2C');
      }
    },
    {
      question: 'Which outcome are you hoping to improve?',
      options: ['More Leads', 'More Sales', 'Stronger Brand Recognition', 'Better Market Positioning', 'Higher Trust', 'Better Customer Retention'],
      multiSelect: false
    }
  ],
"""

out_str += brand_audit_str

with open("frontend/src/components/builder/MainContent.tsx", "r", encoding="utf-8") as f:
    content = f.read()

# Insert before `};` of `agentQuestions`
target = "};\n\nconst agentPrompts:"
new_content = content.replace(target, out_str + target)

with open("frontend/src/components/builder/MainContent.tsx", "w", encoding="utf-8") as f:
    f.write(new_content)

print("Done")
