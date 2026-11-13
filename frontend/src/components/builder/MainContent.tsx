'use client';
import { useState, useEffect, useRef, useMemo } from 'react';
import TemplateGrid from './TemplateGrid';
import { connectors as allConnectorsData, getLogoUrl } from '../../data/connectors';
import { useAgents } from '../../hooks/useAgents';
import ChatInput from './ChatInput';
import AgentQuestionnaire, { type Question } from './AgentQuestionnaire';
import ConnectorsPanel from './ConnectorsPanel';
import ConnectorsView from './ConnectorsView';
import FilesView from './FilesView';
import ProjectsView from './ProjectsView';
import WorkflowView from './WorkflowView';
import styles from './MainContent.module.css';
import ReportRenderer from '../ReportRenderer';
import { exportReportToPdf } from '../../utils/pdfExport';

type Message = { role: 'user' | 'thinking' | 'assistant' | 'error'; content: string; message_metadata?: string; id?: string };
type ReportInfo = { id: string; title: string; agent_type: string };

// ── Per-agent questionnaire configs ───────────────────────────────
const agentQuestions: Record<string, Question[]> = {
  'SEO Audit': [
    {
      question: "What's your primary traffic goal right now?",
      multiSelect: true,
      options: [
        'More organic leads',
        'More organic sales',
        'Brand awareness & visibility',
        'Rank for specific keywords',
      ],
    },
    {
      question: 'Which 3-5 keywords or search queries is your business most desperate to rank for?',
      options: [
        'I have specific keywords in mind',
        "I'm not sure - help me identify them",
        'General industry keywords',
        'Long-tail/customer problem keywords',
      ],
    },
    {
      question: "What's your biggest current SEO pain point?",
      options: [
        'Low rankings despite optimization efforts',
        'Low click-through rate (good rankings, few clicks)',
        'Technical SEO issues (speed, indexing, crawl errors)',
        'Thin or outdated content',
        'Weak backlink profile & domain authority',
      ],
    },
  ],
  'GTM Strategy': [
    {
      id: 'gtm_q1',
      question: 'What is your primary GTM objective?',
      options: [
        'Launch a new product/service',
        'Enter a new geographic market',
        'Enter a new customer segment',
        'Increase customer acquisition',
        'Increase revenue from existing customers',
        'Improve product adoption',
        'Increase market share',
        'Reposition the brand',
        'Other'
      ],
      multiSelect: true,
    },
    {
      id: 'gtm_q2',
      question: 'Who is your primary target customer?',
      options: [
        'B2C',
        'B2B',
        'B2B AND B2C',
        'Other'
      ],
      multiSelect: false,
    },
    {
      id: 'gtm_q2_b2c',
      question: 'Select B2C Target Customers:',
      options: [
        'Consumers (Mass Market)',
        'Affluent / Premium Consumers',
        'Gen Z',
        'Millennials',
        'Parents & Families'
      ],
      multiSelect: true,
      condition: (answers) => {
        const ans = answers['Who is your primary target customer?'] || '';
        return ans.includes('B2C') || ans.includes('B2B AND B2C');
      }
    },
    {
      id: 'gtm_q2_b2b',
      question: 'Select B2B Target Customers:',
      options: [
        'Small Businesses (1–50 employees)',
        'Mid-Market Companies (51–1000 employees)',
        'Enterprise Organizations (1000+ employees)',
        'Government / Public Sector'
      ],
      multiSelect: true,
      condition: (answers) => {
        const ans = answers['Who is your primary target customer?'] || '';
        return ans.includes('B2B') || ans.includes('B2B AND B2C');
      }
    },
    {
      id: 'gtm_q3',
      question: 'What is your biggest growth constraint today?',
      options: [
        'Limited marketing budget',
        'Low brand awareness',
        'Strong competition',
        'Lack of qualified leads',
        'Low conversion rates',
        'Weak sales process',
        'Long sales cycles',
        'Product adoption challenges',
        'Customer retention issues',
        'Market education required',
        'Limited internal resources',
        'Other'
      ],
      multiSelect: true,
    },
    {
      id: 'gtm_q4',
      question: 'What stage is your business currently in?',
      options: [
        'New business / Startup',
        'Early growth',
        'Scaling',
        'Mature business',
        'Market leader',
        'Declining / Stagnant growth'
      ],
      multiSelect: false,
    }
  ],
  'Product Launch Strategy': [
    {
      question: "What are you launching?",
      options: ["New Product", "New Service", "New Feature", "New Brand", "New App / Software", "Existing Product Relaunch", "Other"],
      multiSelect: false
    },
    {
      question: "What is the primary objective of this launch?",
      options: ["Generate Sales", "Generate Leads", "Build Awareness", "Acquire Users", "Drive Product Adoption", "Enter a New Market", "Validate Demand", "Increase Word of Mouth", "Other"],
      multiSelect: true
    },
    {
      question: "What is your planned launch timeline?",
      options: ["Within 30 Days", "1\u20133 Months", "3\u20136 Months", "6\u201312 Months", "Flexible"],
      multiSelect: false
    },
  ],
  'Social Media Strategy': [
    {
      question: "Which social platforms are your priority?",
      options: ["LinkedIn", "Instagram", "Facebook", "X (Twitter)", "YouTube", "Reddit", "Pinterest", "Multiple Platform"],
      multiSelect: true
    },
    {
      question: "What is your primary social media goal?",
      options: ["Brand Awareness", "Lead Generation", "Sales", "Community Building", "Customer Engagement", "Thought Leadership", "Product Adoption", "Customer Support", "OTHERS"],
      multiSelect: false
    },
    {
      question: "What is your biggest social media challenge?",
      options: ["Low Reach", "Low Engagement", "Low Followers", "Low Leads", "Low Conversions", "Inconsistent Content", "Lack of Content Ideas", "Limited Resources", "Unsure What Works", "OTHERS"],
      multiSelect: false
    },
  ],
  'Content Calendar': [
    {
      question: "Which channels need content?",
      options: ["Blog", "LinkedIn", "Instagram", "Facebook", "X", "YouTube", "Email Newsletter", "Multiple Channels", "Other"],
      multiSelect: true
    },
    {
      question: "What is your primary content objective?",
      options: ["Brand Awareness", "Lead Generation", "Sales", "SEO Growth", "GEO / AI Visibility", "Customer Education", "Community Building", "Thought Leadership", "others"],
      multiSelect: false
    },
    {
      question: "What content frequency can your team realistically maintain?",
      options: ["Daily", "3\u20135 Times Per Week", "Weekly", "Bi-Weekly", "Monthly"],
      multiSelect: false
    },
  ],
  'Festival Campaign': [
    {
      question: "Which festival or event do you want to build a campaign around?",
      options: ["Diwali", "Christmas", "New Year", "Black Friday / Cyber Monday", "Valentine's Day", "Eid", "Holi", "Independence Day", "Industry Event", "Other"],
      multiSelect: true
    },
    {
      question: "What is the primary objective of this campaign?",
      options: ["Sales", "Lead Generation", "Brand Awareness", "Customer Engagement", "Product Launch", "Customer Retention", "others"],
      multiSelect: false
    },
    {
      question: "What type of offer are you willing to run?",
      options: ["Discounts", "Bundles", "Free Trial", "Giveaway", "Content-Led Campaign", "No Offer (Brand Campaign)", "Others"],
      multiSelect: false
    },
  ],
  'Topical Campaign': [
    {
      question: "What is the primary topic you want to build authority around?",
      options: ["AI Marketing", "Real Estate Investment", "Diabetes Care", "Cybersecurity", "Other"],
      multiSelect: false
    },
    {
      question: "What is the primary objective?",
      options: ["SEO Rankings", "GEO / AI Visibility", "Lead Generation", "Thought Leadership", "Brand Awareness"],
      multiSelect: true
    },
    {
      question: "What is your current content maturity?",
      options: ["No Existing Content", "Some Content", "Large Content Library", "Industry Authority"],
      multiSelect: false
    },
  ],
  'Trend Strategy': [
    {
      question: "Which trend category matters most?",
      options: ["Industry Trends", "Consumer Trends", "Technology Trends", "Social Media Trends", "Market Trends", "All Relevant Trends"],
      multiSelect: true
    },
    {
      question: "What do you want to achieve from trends?",
      options: ["Content Ideas", "Lead Generation", "Thought Leadership", "Product Innovation", "Brand Awareness"],
      multiSelect: true
    },
    {
      question: "How quickly can your team act on opportunities?",
      options: ["Same Day", "Within a Week", "Within a Month", "Quarterly Planning"],
      multiSelect: false
    },
  ],
  'Seasonal Campaign': [
    {
      question: "Does your business experience seasonal demand?",
      options: ["Yes", "No", "Not Sure"],
      multiSelect: false
    },
    {
      question: "Which season matters most to your business?",
      options: ["Summer", "Winter", "Monsoon", "Multiple Seasons"],
      multiSelect: false
    },
    {
      question: "What is the primary goal of your seasonal campaigns?",
      options: ["Increase Sales", "Generate Leads", "Increase Footfall", "Brand Awareness", "Customer Retention"],
      multiSelect: false
    },
  ],
  'GEO/AEO': [
    {
      question: "Which AI visibility channel matters most to you?",
      options: ["ChatGPT", "Google AI Overviews", "Perplexity", "Gemini", "Claude"],
      multiSelect: true
    },
    {
      question: "What is your primary GEO/AEO objective?",
      options: ["Increase Brand Visibility", "Generate Leads", "Increase Website Traffic", "Become an Industry Authority", "Improve AI Citations", "Improve Local Visibility"],
      multiSelect: true
    },
    {
      question: "What best describes your current AI visibility?",
      options: ["No Visibility", "Rarely Mentioned", "Occasionally Mentioned", "Frequently Mentioned", "others"],
      multiSelect: false
    },
  ],
  'SEO': [
    {
      question: "What is your primary SEO objective?",
      options: ["More Organic Traffic", "More Leads", "More Sales", "Local SEO Growth", "Brand Visibility", "Thought Leadership"],
      multiSelect: false
    },
    {
      question: "What is your biggest SEO challenge?",
      options: ["Low Rankings", "Low Traffic", "Lack of Content", "Technical SEO Issues", "Backlinks / Authority", "Local Visibility", "Unsure"],
      multiSelect: false
    },
    {
      question: "Which keywords matter most to your business?",
      options: ["AI Marketing", "CRM Software", "Luxury Apartments Gurgaon", "Other"],
      multiSelect: false
    },
  ],
  'Business Plan Generator': [
    {
      question: "What stage is the business currently in?",
      options: ["Business Idea", "MVP / Prototype", "Early Revenue", "Growing Business", "Established Business", "Pivoting Existing Business"],
      multiSelect: false
    },
    {
      question: "What is the primary purpose of this business plan?",
      options: ["Start the Business", "Raise Funding", "Internal Planning", "Bank Loan", "Expansion Strategy", "Investor Pitch"],
      multiSelect: true
    },
    {
      question: "What is your business model?",
      options: ["SaaS", "E-commerce", "Marketplace", "Agency", "Professional Services", "Healthcare", "Real Estate", "Consumer Electronics", "Mobile App", "Manufacturing", "Other"],
      multiSelect: false
    },
  ],
  'Brand Audit': [
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
  'Partnership & Distribution Strategy': [
    {
      question: "What is your primary partnership objective?",
      options: ["Generate Revenue", "Acquire Customers", "Expand Distribution", "Increase Brand Awareness", "Enter New Markets", "Access New Technology", "Strategic Alliances"],
      multiSelect: false
    },
    {
      question: "What type of business are you?",
      options: ["SaaS", "E-commerce", "Agency", "Professional Services", "Healthcare", "Real Estate", "Marketplace", "Consumer Brand", "Consumer Electronics", "other"],
      multiSelect: false
    },
    {
      question: "Which partnership model interests you most?",
      options: ["Referral Partners", "Resellers", "Affiliates", "Strategic Alliances", "Technology Integrations", "Channel Partners", "other"],
      multiSelect: false
    },
  ],
  'Revenue Model Strategy': [
    {
      question: "What best describes your current revenue model?",
      options: ["Subscription (SaaS)", "One-Time Purchase", "Services", "Marketplace", "Advertising", "Licensing", "Multiple Revenue Streams", "Pre-Revenue"],
      multiSelect: false
    },
    {
      question: "What is your primary monetization goal?",
      options: ["Increase Revenue", "Improve Profitability", "Introduce New Revenue Streams", "Improve Pricing", "Increase Customer Lifetime Value", "Reduce Customer Churn"],
      multiSelect: true
    },
    {
      question: "What is your biggest revenue challenge?",
      options: ["Pricing", "Customer Acquisition Cost", "Low Retention", "Low Conversion", "Limited Revenue Streams", "Weak Upsells", "Unsure"],
      multiSelect: false
    },
  ],
  'Campaign Structure Architect': [
    {
      question: "Which advertising platform are you using?",
      options: ["Google Ads", "Meta Ads", "LinkedIn Ads", "Microsoft Ads", "Multiple Platforms", "others"],
      multiSelect: true
    },
    {
      question: "What is your primary campaign objective?",
      options: ["Lead Generation", "Sales", "App Installs", "Brand Awareness", "Website Traffic", "Product Launch", "others"],
      multiSelect: true
    },
    {
      question: "What best describes your advertising maturity?",
      options: ["Never Run Ads", "Beginner", "Intermediate", "Advanced", "Enterprise Scale"],
      multiSelect: true
    },
  ],
  'Market Sizing & Entry': [
    {
      question: "Which market are you evaluating?",
      options: ["UAE", "Saudi Arabia", "US Healthcare", "AI CRM Software", "Luxury Real Estate India", "Other"],
      multiSelect: false
    },
    {
      question: "What is your objective?",
      options: ["Launch a New Business", "Launch a New Product", "Enter a New Geography", "Enter a New Customer Segment", "Expansion Planning", "Investment Evaluation"],
      multiSelect: true
    },
  ],
  'ICP & Personas': [
    {
      question: "Which customer group drives the most value for your business today?",
      options: ["Consumers", "Small Businesses", "Mid-Market Companies", "Enterprise Organizations", "Government", "Not Sure"],
      multiSelect: false
    },
    {
      question: "What is your biggest customer acquisition challenge?",
      options: ["Wrong Leads", "Low Conversion", "Long Sales Cycle", "Low Awareness", "High CAC", "Poor Retention", "Not Sure"],
      multiSelect: false
    },
    {
      question: "What is your primary growth objective?",
      options: ["More Leads", "Higher Conversions", "Larger Deals", "Better Retention", "Market Expansion", "Product Adoption"],
      multiSelect: false
    },
  ],
  'Attribution & Measurement Agent': [
    {
      question: "What marketing channels are you currently using?",
      options: ["Google Ads", "Meta Ads", "LinkedIn Ads", "SEO", "Email Marketing", "Organic Social", "Partnerships", "Multiple Channels"],
      multiSelect: true
    },
    {
      question: "What is your biggest measurement challenge?",
      options: ["Can't identify what drives conversions", "Inaccurate attribution", "Missing tracking", "Reporting is fragmented", "No dashboarding", "Unsure"],
      multiSelect: false
    },
    {
      question: "What decision do you want attribution to improve?",
      options: ["Budget Allocation", "Campaign Optimization", "Channel Performance", "CAC Reduction", "Revenue Attribution", "Executive Reporting"],
      multiSelect: false
    },
  ],
  'Bidding & Budget Optimizer': [
    {
      question: "Which advertising platforms are you actively using?",
      options: ["Google Ads", "Meta Ads", "LinkedIn Ads", "Microsoft Ads", "Multiple Platforms"],
      multiSelect: true
    },
    {
      question: "What is your primary advertising objective?",
      options: ["Lead Generation", "Sales", "ROAS Improvement", "Scale Spend", "Lower CPA", "Brand Awareness"],
      multiSelect: true
    },
    {
      question: "What is your biggest performance challenge?",
      options: ["High CPA", "Low ROAS", "Low Conversion Rate", "Limited Budget", "Scaling Issues", "Unstable Performance"],
      multiSelect: false
    },
  ],
  'Legal Agreement Drafter': [
    {
      question: "What type of agreement do you need?",
      options: ["NDA", "Service Agreement", "Partnership Agreement", "Employment Agreement", "Vendor Agreement", "Contractor Agreement", "Other"],
      multiSelect: true
    },
    {
      question: "Which party are you?",
      options: ["Service Provider", "Client", "Employer", "Employee", "Business Partner", "Vendor"],
      multiSelect: false
    },
    {
      question: "What jurisdiction should this agreement follow?",
      options: ["India", "United States", "United Kingdom", "UAE", "Australia", "Other"],
      multiSelect: false
    },
  ],
  'Brand Personality and Guidelines': [
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
  'Competitor Research Agent': [
    {
      question: "What is your competitor's name?",
      options: [],
      multiSelect: false
    },
    {
      question: "What is your competitor's URL?",
      options: [],
      multiSelect: false
    },
  ],
};

const agentPrompts: Record<string, string> = {
  'Meeting Prep Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A meeting prep agent. Before any external call, it researches the attendees and their companies and puts together a one-page briefing with background and suggested talking points. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'CRM Pipeline Reporter': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A reporting agent that summarizes your Salesforce pipeline. It pulls deal data, breaks it down by stage and owner, and puts together a clean weekly report. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Lead Enrichment Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. An agent that enriches lead lists. Give it a spreadsheet of contacts and it fills in company data, verifies emails, and scores each lead against your ideal customer profile. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Sales Prospecting Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A proactive sales agent that helps with prospecting and outreach. It researches target accounts, finds the right contacts, drafts personalized emails, and books meetings. Should suggest who to reach out to and why. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Competitor Research Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A research agent that digs into any competitor. Give it a company name or website and it comes back with their pricing, features, recent news, and how they stack up. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Cold Outreach Writer': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A cold email writer that does its homework first. Give it a prospect and it researches their company, finds relevant talking points, and drafts a personalized email ready to review. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Spreadsheet Analyst': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. An analyst for your Google Sheets data. Give it a spreadsheet and ask questions — it finds patterns, creates summaries, and writes up its findings. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'PostgreSQL Query Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A query agent for your PostgreSQL database. Ask questions in plain English and it writes safe read-only SQL, runs it, and explains the results. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'BigQuery Data Analyst': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A data analyst for your BigQuery warehouse. Ask it any business question and it writes the SQL, runs the query, and explains what the data means in plain language. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Snowflake Data Analyst': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A data analyst for your Snowflake warehouse. It explores tables, answers questions with SQL, and documents what it learns along the way so it gets smarter over time. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Report Generator': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A report writer connected to your data warehouse. Ask a business question and it produces a polished report with tables, takeaways, and the raw data to dig deeper. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Data Cleanup Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A cleanup agent for messy spreadsheets. Give it a Google Sheet and it deduplicates rows, standardizes formats, and fills in missing info where it can. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Feedback Digest Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A feedback summarizer. It reads through support tickets, groups feedback by theme, and puts together a weekly digest of what customers are asking for most. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Support Inbox Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A support agent that handles incoming tickets. It reads each one, finds the right answer from your knowledge base, and drafts a response. Escalates anything it can't handle. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Customer Onboarding Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. An onboarding agent for new customers. It sets up their checklist, schedules a kickoff call, and sends a welcome email with everything they need to get started. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Customer Lookup Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A customer lookup agent. Give it a name and it pulls together everything — account info, open tickets, recent activity — into one quick summary. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Help Docs Writer': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A documentation writer. Give it a topic and it researches best practices, checks your existing docs for gaps, and drafts a clear help article. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Issue Tracker Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A triage agent for GitHub issues. It categorizes new issues, finds related ones, and sends you a daily digest of what needs attention. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Social Media Writer': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A social media writer. Give it a topic and it drafts posts for LinkedIn and X with the right tone, hashtags, and formatting for each platform. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Competitive Content Analyst': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A competitive content analyst. Point it at a competitor's website and it breaks down their messaging, content strategy, and where they're leaving gaps you can fill. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Newsletter Curator': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A newsletter writer. It finds the best recent articles and trends on a topic, writes engaging summaries, and formats the whole thing ready to send. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Content Calendar Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A content planner. It researches what's trending, proposes a monthly calendar of topics, and drafts a brief for each piece. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Blog Post Writer': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A blog writer that does its own research. Give it a topic and it comes back with a polished draft, complete with supporting data and SEO-friendly titles. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'SEO Audit Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. An SEO auditor. Give it a website URL and it crawls the pages, identifies issues, and produces an actionable report with what to fix first. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Weekly Recap Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A weekly recap agent. Every Friday it looks back at the week's tickets, meetings, and accomplishments and writes up a summary for your team. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Internal Knowledge Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. An internal knowledge agent. Ask it any question and it searches your company docs and wikis to find the answer. Always cites where it found the info. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Executive Assistant': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A personal assistant that manages your calendar, drafts emails, organizes files, and keeps your docs in order. Proactive — suggests next actions before you ask. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Daily Standup Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A standup prep agent. Each morning it checks your tickets and calendar and puts together a quick brief — what happened yesterday, what's today, and what's blocked. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Inbox Manager': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. An email manager. It goes through your inbox, sorts what's urgent from what's not, drafts replies for the routine stuff, and flags what actually needs you. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Meeting Notes Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A meeting notes agent. It listens to your calls, pulls out the key decisions and action items, writes clean notes, and sends a summary to everyone who was there. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Deep Research Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A thorough research agent. Give it any question and it searches across multiple sources in parallel, reads through the results, and compiles everything into a comprehensive brief with sources. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Recruiting Sourcer': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A recruiting sourcer. Give it a job description and it finds matching candidates, scores them against the role, and logs the best profiles for your team to review. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'News & Trends Monitor': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A news monitoring agent. It tracks industry news and emerging trends, filters for what actually matters, and puts together a daily briefing with sources. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Market Research Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A market research agent. Give it an industry or category and it maps out the market — size, key players, trends, and recent developments. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Company Research Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A company research agent. Give it a company name and it puts together a one-pager covering their product, team, funding, news, and competitive landscape. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Competitive Intelligence Agent': `I want you to help me set up the following agent. Help me connect the right accounts, tailor it to my specific workflow, and configure everything so it's ready to use. A competitive intel agent. It watches competitor websites for changes, tracks their announcements and press coverage, and flags anything notable. Once everything is configured, also set up your own profile image and write a short description for yourself. Then, setup 4 example prompts for this agent I can use to get started with it.`,
  'Sales Pitch Generator': `You are a seasoned sales professional with a proven track record of effectively communicating value propositions and closing deals. Your verbal pitch is concise, persuasive, and tailored to the needs of each prospect. You excel at building rapport, identifying pain points, and offering solutions that address specific customer challenges. Your pitch highlights the unique features and benefits of your product or service, while also showcasing how it can solve the customer's problems and improve their business outcomes.`,
  'Cold Calling Script Generator': `You are a skilled copywriter with experience in crafting persuasive and engaging scripts for cold calling scenarios. Your background includes a strong understanding of sales techniques and the ability to tailor messaging to different target audiences. You excel at creating scripts that grab the attention of prospects, build rapport, address objections, and ultimately drive conversions. Your writing style is clear, concise, and impactful, with a focus on guiding the conversation towards a desired outcome. You are familiar with the nuances of cold calling etiquette and have a track record of producing high-quality scripts that deliver results.`,
  'Facebook Content Writer': `You are a social media strategist with expertise in crafting engaging and professional Facebook posts that resonate with a business audience. You understand the nuances of Facebook as a platform for networking and thought leadership, and you are skilled at using a conversational yet professional tone. You have a proven ability to create content that encourages interaction, showcases expertise, and highlights industry trends.\n\nOutput format\nFacebook posts should be short but interesting. They should engage senior professionals.`,
  'Twitter Content Writer': `You are a Twitter post writer specializing in transforming blog content into engaging Twitter posts designed to maximize user interaction and engagement. Your primary objective is to craft posts that captivate the audience through a curiosity gap-style hook, effectively summarize the core message of the blog, and conclude with a compelling call to action. Your writing should maintain a conversational and witty tone, infused with subtle stoner humor, to appeal to a broad audience. Avoid using hashtags to keep the focus on the message itself. Ensure that each post is concise, not exceeding 280 characters, to fit within Twitter's character limit.\n\nTo excel in this role, consider the following guidelines:\nCuriosity Gap Hook: Start with an intriguing statement or question that piques interest without revealing too much. For example, "Ever wondered why cats love boxes? It's not just about comfort..."\nSummary of Key Information: Condense the blog's main points into a few sentences that are easy to digest. Avoid jargon and keep it relatable.\nCall to Action: Encourage readers to engage further, whether by visiting the blog, sharing the post, or commenting. For instance, "Find out more about this feline mystery in our latest blog!"\n\nGood Practices:\nUse humor that is light-hearted and universally relatable.\n• Maintain a balance between wit and clarity to ensure the message is understood.\n\nBad Practices:\n• Avoid overly complex language or niche humor that might alienate some readers.\n• Do not use hashtags or excessive punctuation that can distract from the message.\n\nHandling Edge Cases:\n• If the blog content is highly technical, simplify the language without losing the essence of the message.\n• For sensitive topics, ensure humor is respectful and considerate.\n\nQuality Standards:\n• Posts should be free of grammatical errors and typos.\n• Ensure the tone is consistent with the brand's voice and the intended humor is appropriate for the audience.\n\nOutput format\nYour output should be a single Twitter post that adheres to the following structure:\n1. Curiosity Gap Hook: Begin with a statement or question that draws the reader in.\n2. Summary of Key Information: Provide a brief overview of the blog's main points.\n3. Call to Action: End with a prompt that encourages further engagement.\n\nFormatting Guidelines:\n• Keep the total character count under 280 characters.\n• Use proper sentence structure and punctuation.\n• Ensure the post flows logically from the hook to the call to action.\n\nQuality Checks:\n• Verify that the post is free of spelling and grammatical errors.\n• Confirm that the tone is conversational and includes subtle stoner humor.\n• Ensure the message is clear and engaging without the use of hashtags.\n\nExamples of Good Outputs:\n• "Why do cats love boxes? It's not just about comfort... Discover the science behind this feline fascination in our latest blog!"\n\nExamples of Bad Outputs:\n• "Cats & boxes: a love story. Read more! #cats #boxes #blog" (Avoids hashtags and lacks a curiosity gap hook)\n\nCommon Pitfalls to Avoid:\n• Overloading the post with information, making it hard to read.\n• Using humor that might not resonate with a wide audience.`,
  'LinkedIn Post Writer': `You are an AI assistant specializing in crafting engaging and informative social media posts for a Financial advisor/wealth planner named Umar Yusof, based in Singapore. Your primary role is to enhance Umar's online presence by creating content that reflects his professional expertise and personal interests. Umar is a financial advisor, wealth planner, and legacy planner with a focus on finance, investment, business, and legacy planning. He is also a father of two and a husband, which adds a personal dimension to his professional persona. Your task is to create posts that cover topics such as investment strategies, asset protection, risk management, and legacy planning. You should aim to position Umar as a thought leader in the financial sector, while also making his content relatable and approachable. Examples of good practices include using clear, concise language and incorporating personal anecdotes to humanize the content. Bad practices include using jargon-heavy language that may alienate the audience or failing to provide actionable insights. In edge cases, such as addressing complex financial topics, break down the information into digestible parts and use analogies to simplify concepts. Maintain a balance between professional content and personal touches to engage a broad audience. Adhere to high-quality standards by ensuring accuracy, relevance, and timeliness of the information shared.\n\nOutput format\nYour output should be meticulously structured and clear, ensuring all necessary information is included and presented in a professional manner. When creating posts, adhere to the following detailed guidelines: Maintain a tone that is professional yet approachable, showcasing Umar's expertise and thought leadership. The content mix should consist of 60% professional insights, 30% industry news/trends, and 10% personal touches. Use bullet points for clarity where appropriate, and ensure all contact information is accurate and prominently displayed. Before finalizing, conduct a thorough quality check to eliminate grammatical errors and ensure completeness of information. Examples of good outputs include well-organized posts with clear headings and subheadings, while bad outputs are disorganized or lack essential details. Avoid common pitfalls such as using overly technical language or failing to address potential audience questions. Always format the output in a visually appealing manner, using consistent font styles and sizes. Incorporate a visual element, such as an image or infographic, to enhance engagement. Ensure that visuals are relevant and of high quality. Additionally, provide a brief caption or description for each visual element to contextualize its relevance to the post. Regularly update content to reflect the latest industry trends and insights, ensuring that Umar's social media presence remains dynamic and authoritative.`,
  'Email Campaign Generator': `You are a skilled and experienced professional writer with a comprehensive understanding of email etiquette and communication strategies. Your primary role is to craft emails that are not only professional, concise, and engaging but also tailored to the specific needs and brand voice of each client. You excel in adapting your tone and voice to align with the client's brand and communication style, ensuring consistency and authenticity in every message. Your expertise extends to creating emails that are clear, persuasive, and effective in achieving the desired outcomes, whether it be to inform, persuade, or engage the recipient. You possess a keen eye for detail, grammar, and spelling, ensuring that all emails are error-free and polished to the highest standard. Your extensive experience spans a variety of clients across different industries, allowing you to understand diverse needs and deliver high-quality email content that resonates with the target audience. You are adept at handling edge cases, such as addressing sensitive topics or managing client-specific requests, with tact and professionalism. You are also knowledgeable about the latest trends in digital communication and email marketing, which you incorporate into your writing to enhance effectiveness. Examples of good practices include using clear subject lines, maintaining a positive tone, and providing actionable steps. Bad practices to avoid include using jargon, being overly verbose, or neglecting the client's brand guidelines. Quality standards require that emails are not only grammatically correct but also strategically structured to guide the reader towards the intended action.\n\nOutput format\nThe output should be a well-structured email that includes the following components: 1. Subject Line: A clear and concise subject line that accurately reflects the content of the email and captures the recipient's attention. 2. Greeting: A personalized greeting that addresses the recipient appropriately, using their name and title if known. 3. Introduction: A brief introduction that sets the context and purpose of the email. 4. Body: The main content of the email, organized into clear and logical paragraphs. Each paragraph should focus on a single idea or point, using bullet points or numbered lists where appropriate to enhance readability. 5. Call to Action: A clear and compelling call to action that specifies what the recipient should do next. 6. Closing: A polite and professional closing that reinforces the email's purpose and leaves a positive impression. 7. Signature: A professional signature that includes the sender's name, position, and contact information. Quality checks should ensure that the email is free from spelling and grammatical errors, follows the client's brand guidelines, and is formatted for easy readability. Examples of good outputs include emails that are concise, relevant, and engaging, while bad outputs are those that are vague, overly complex, or misaligned with the client's objectives. Common pitfalls to avoid include failing to proofread, using inappropriate language, or neglecting to include a call to action.`,
  'User Persona Generator': `You're a world-class user persona researcher. Given a business, you are tasked with creating a comprehensive User Persona Report to help the business better understand its target audience. The report should be well-structured and informative.\n\nUser Personas:\nCreate 3 personas for different user segments. Each persona should include:\nName: Give the persona a name for easy reference.\nDemographics: Age, gender, location, income, education, etc.\nBackground: Provide a brief overview of their personal and professional life.\nGoals and Objectives: Clearly outline their primary goals, both long-term and short-term.\nPain Points and Challenges: Identify their pain points and obstacles they face in their daily lives.\nMotivations: Understand what drives and motivates them to take action.\nBehaviors and Preferences: Describe how they behave, make decisions, and their preferences when it comes to products or services.\nNeeds and Expectations: Highlight what they expect from our product or service.\nReal Quotes and Anecdotes: Include real quotes, anecdotes, or testimonials from interviews and surveys with users. These can make the personas more relatable and authentic.\n\nSummary of Key Insights:\nProvide a concise summary that captures the key insights gained from the personas. Emphasize the common themes, challenges, and opportunities that emerge from the personas.\n\n3 User Acquisition Ideas:\nSuggest three user acquisition ideas based on the personas and their characteristics. Be creative and specific in your recommendations.\nIdea 1:\nIdea 2:\nIdea 3:\n\n3 Conversion Rate Optimization Ideas:\nPropose three conversion rate optimization ideas tailored to the personas. Ensure these ideas are actionable and have a direct impact on improving conversion rates.\nIdea 1:\nIdea 2:\nIdea 3:\n\n3 Content Marketing Ideas:\nPresent three content marketing ideas designed to resonate with the personas and their interests. Ensure these ideas are engaging and address their pain points and needs.\nIdea 1:\nIdea 2:\nIdea 3:`,
  'Business Plan Generator': `You are an expert business analyst and strategist skilled at transforming raw business ideas into detailed, actionable business plans. Your role is to conduct extensive research on every aspect of the user's idea, including product, marketing, sales, finance, hiring, competition, and funding. For each category, you will gather relevant data, analyze market trends, and synthesize insights to create a robust business plan. You will structure the plan in a format suitable for Excel, with each main category as a separate sheet or section, and each aspect within a category detailed in a canvas format (e.g., problem, solution, key metrics, channels, etc.).\n\nGuidelines:\n• Always clarify ambiguous or incomplete user input by making reasonable assumptions and stating them clearly.\n• Use up-to-date, reputable sources for research and cite them where appropriate.\n• For each category, provide actionable recommendations, realistic projections, and clear justifications, and write your report in a document canvas using Text Canvas\n• If information is unavailable or speculative, clearly label it as such and suggest next steps for validation.\n• Maintain a professional, concise, and user-friendly tone.\n\nConstraints:\n• Do not fabricate data; use estimates only when necessary and label them as such.\n• Avoid jargon unless it is explained or commonly understood in business contexts.\n• Do not provide legal or financial advice beyond general business planning.\n\nError Handling:\n• If the user's idea is too vague, request clarification or provide a list of assumptions made.\n• If research yields conflicting information, summarize the main viewpoints and recommend a course of action.\n\nOutput format\nOutput Format:\n• For each main category (Product, Marketing, Sales, Finance, Hiring, Competition, Funding), create a document to report them.\n\nQuality Standards:\n• All information must be well-researched, relevant, and actionable.\n• Projections and recommendations should be realistic and justified.\n• The plan should be logically structured and easy to follow.\n\nCommon Mistakes to Avoid:\n• Overly generic or vague recommendations.\n• Failing to clarify assumptions or limitations.\n• Ignoring key business plan categories or omitting critical details.\n\nBest Practices:\n• Use clear, consistent formatting for easy Excel transfer.\n• Reference reputable sources where possible.\n• Clearly state any assumptions or areas needing further validation.\n• Tailor recommendations to the user's specific idea and context.`,
  'Legal Agreement Drafter': `You are an experienced contract lawyer with a strong background in drafting legal agreements. You have a deep understanding of contract law principles and are skilled at creating clear, concise, and legally binding documents. Your expertise includes identifying key terms and conditions, ensuring compliance with relevant laws and regulations, and protecting the interests of all parties involved in the agreement. You have a keen eye for detail, excellent communication skills, and the ability to tailor contracts to meet the specific needs and objectives of your clients.`,
  'Competition Analysis': `Generate a complete, board-ready competitive analysis report for my brand and competitors based on all our scanned website and Instagram knowledge base data. Include full comparison tables, Recharts dashboard visualizations for pricing/scale/share of voice, SWOT analysis, and personalized next steps.`,
  'Content Calendar': `Generate a comprehensive monthly content calendar and campaign strategy based on our brand and competitor research.`,
  'SEO Audit': `Generate a full SEO and generative search optimization (GEO/AEO) audit based on our scanned brand data.`,
  'Ad Copywriter': `Generate high-converting ad copy sets across Meta and Google Ads tailored to our brand positioning and competitive differentiators.`,
};

const getDomain = (connectorName: string) => {
  const c = allConnectorsData.find(c => c.name === connectorName);
  return c ? c.domain : 'google.com';
};

export default function MainContent({ onNewChat }: { onNewChat?: () => void }) {
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('mistral');
  const [promptText, setPromptText] = useState('');
  const [showBanner, setShowBanner] = useState(false);
  const [showQuestionnaire, setShowQuestionnaire] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [qaAnswers, setQaAnswers] = useState<Array<{ question: string; answer: string }>>([]);
  const [userContext, setUserContext] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [downloadingMsgIdx, setDownloadingMsgIdx] = useState<number | null>(null);
  const [copiedMsgIdx, setCopiedMsgIdx] = useState<number | null>(null);
  const [reportsByMessageId, setReportsByMessageId] = useState<Record<string, ReportInfo>>({});
  const [downloadingDocxIdx, setDownloadingDocxIdx] = useState<number | null>(null);
  const [docxErrorIdx, setDocxErrorIdx] = useState<number | null>(null);
  const [sharingReportIdx, setSharingReportIdx] = useState<number | null>(null);
  const [shareCopiedIdx, setShareCopiedIdx] = useState<number | null>(null);
  const [shareErrorIdx, setShareErrorIdx] = useState<number | null>(null);
  const [view, setView] = useState<'builder' | 'files' | 'projects' | 'agents' | 'workflow' | 'connectors'>('builder');
  const { agents: catalogAgents, categories: catalogCategories, loading: agentsLoading, error: agentsError, refetch: refetchAgents } = useAgents();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const latestAssistantIdx = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return i;
    }
    return -1;
  }, [messages]);

  const handleDownloadPdf = async (idx: number, content: string) => {
    try {
      setDownloadingMsgIdx(idx);
      const el = document.getElementById(`report-markdown-${idx}`);
      if (!el) {
        alert('Could not find report content to export.');
        return;
      }
      const headerMatch = content.match(/^#+\s*(.+)$/m);
      const reportTitle = headerMatch ? headerMatch[1].trim() : `${selectedAgent || 'StratAI'} Strategy Report`;

      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const currentBrandId = activeProject?.brand_config_id || savedBrandId;
      const brandName = ((currentBrandId && brandsMap[currentBrandId]) || activeProject?.title || 'Brand').trim();
      const agentName = (selectedAgent || 'Strategy Report').trim();

      const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
      const fileName = `${sanitize(brandName)}_${sanitize(agentName)}.pdf`;

      await exportReportToPdf({
        element: el,
        reportTitle,
        brandName,
        agentName,
        fileName,
      });
    } catch (err) {
      console.error('Failed to export PDF:', err);
      alert('Failed to generate PDF. Please try again.');
    } finally {
      setDownloadingMsgIdx(null);
    }
  };

  const handleCopyReport = async (idx: number, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMsgIdx(idx);
      setTimeout(() => setCopiedMsgIdx(null), 2000);
    } catch (err) {
      console.error('Failed to copy report text:', err);
    }
  };

  const fetchReportsForProject = async (projectId: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/projects/${projectId}/reports`, { headers });
      if (!res.ok) return;
      const list = await res.json();
      const map: Record<string, ReportInfo> = {};
      for (const r of list) {
        if (r.message_id) {
          map[r.message_id] = { id: r.id, title: r.title, agent_type: r.agent_type };
        }
      }
      setReportsByMessageId(map);
    } catch (err) {
      console.error('Failed to fetch reports for project:', err);
    }
  };

  const handleDownloadDocx = async (idx: number, messageId: string) => {
    const reportInfo = reportsByMessageId[messageId];
    if (!reportInfo) return;
    try {
      setDocxErrorIdx(null);
      setDownloadingDocxIdx(idx);

      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/reports/${reportInfo.id}/export/docx`, { headers });
      if (!res.ok) {
        throw new Error(`Server error (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const currentBrandId = activeProject?.brand_config_id || savedBrandId;
      const brandName = ((currentBrandId && brandsMap[currentBrandId]) || activeProject?.title || 'Brand').trim();
      const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
      const fileName = `${sanitize(brandName)}_${sanitize(reportInfo.agent_type || reportInfo.title || 'Report')}.docx`;

      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export DOCX:', err);
      setDocxErrorIdx(idx);
      setTimeout(() => setDocxErrorIdx(null), 4000);
    } finally {
      setDownloadingDocxIdx(null);
    }
  };

  const copyTextWithFallback = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fallback: select a hidden input's text so the browser's copy still works
      const input = document.createElement('input');
      input.value = text;
      input.style.position = 'fixed';
      input.style.left = '-9999px';
      document.body.appendChild(input);
      input.select();
      try {
        document.execCommand('copy');
      } catch {
        // best effort — nothing more we can do here
      }
      document.body.removeChild(input);
    }
  };

  const handleShareReport = async (idx: number, messageId: string) => {
    const reportInfo = reportsByMessageId[messageId];
    if (!reportInfo) return;
    try {
      setShareErrorIdx(null);
      setSharingReportIdx(idx);

      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/reports/${reportInfo.id}/share`, {
        method: 'POST',
        headers,
      });
      if (!res.ok) {
        throw new Error(`Server error (${res.status})`);
      }
      const data = await res.json();
      const publicUrl = `${window.location.origin}/r/${data.token}`;

      await copyTextWithFallback(publicUrl);

      setShareCopiedIdx(idx);
      setTimeout(() => setShareCopiedIdx(null), 3000);
    } catch (err) {
      console.error('Failed to create share link:', err);
      setShareErrorIdx(idx);
      setTimeout(() => setShareErrorIdx(null), 4000);
    } finally {
      setSharingReportIdx(null);
    }
  };

  // Project selector state
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [projectsList, setProjectsList] = useState<any[]>([]);
  const [brandsList, setBrandsList] = useState<any[]>([]);
  const [brandsMap, setBrandsMap] = useState<Record<string, string>>({});
  const [activeProject, setActiveProject] = useState<{ id: string; title: string; brand_config_id?: string } | null>(null);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const [homeSearchQuery, setHomeSearchQuery] = useState('');
  const homeSearchContainerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (homeSearchContainerRef.current && !homeSearchContainerRef.current.contains(e.target as Node)) {
        setHomeSearchQuery('');
      }
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  // Fetch projects and brands for dropdown
  const loadProjectsAndBrands = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const [res, brandsRes] = await Promise.all([
        fetch(`${apiBase}/api/projects/`, { headers }),
        fetch(`${apiBase}/api/brands/`, { headers })
      ]);

      if (res.ok && brandsRes.ok) {
        const data = await res.json();
        const brandsData = await brandsRes.json();
        const bMap: Record<string, string> = {};
        brandsData.forEach((b: any) => { bMap[b.id] = b.brand_name; });
        setBrandsMap(bMap);
        setBrandsList(brandsData || []);
        setProjectsList(data || []);

        const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;

        if (savedBrandId) {
          const matchingProj = (data || []).find((p: any) => p.brand_config_id === savedBrandId);
          if (matchingProj) {
            setActiveProject({
              id: matchingProj.id,
              title: bMap[matchingProj.brand_config_id] || matchingProj.title || 'Brand Project',
              brand_config_id: matchingProj.brand_config_id
            });
            return;
          }
          const matchingBrand = (brandsData || []).find((b: any) => b.id === savedBrandId);
          if (matchingBrand) {
            setActiveProject({
              id: matchingBrand.id,
              title: matchingBrand.brand_name,
              brand_config_id: matchingBrand.id
            });
            return;
          }
        }

        if (!activeProject && data && data.length > 0) {
          const first = data[0];
          setActiveProject({
            id: first.id,
            title: bMap[first.brand_config_id] || first.title || 'Brand Project',
            brand_config_id: first.brand_config_id
          });
          if (first.brand_config_id && typeof window !== 'undefined') {
            localStorage.setItem('brand_config_id', first.brand_config_id);
          }
        } else if (!activeProject && brandsData && brandsData.length > 0) {
          const firstB = brandsData[0];
          setActiveProject({
            id: firstB.id,
            title: firstB.brand_name,
            brand_config_id: firstB.id
          });
          if (typeof window !== 'undefined') {
            localStorage.setItem('brand_config_id', firstB.id);
          }
        }
      }
    } catch (err) {
      console.error('Failed to load projects/brands for dropdown', err);
    }
  };

  useEffect(() => {
    loadProjectsAndBrands();

    const handleProjectChanged = () => {
      loadProjectsAndBrands();
    };
    window.addEventListener('projectChanged', handleProjectChanged);
    return () => window.removeEventListener('projectChanged', handleProjectChanged);
  }, []);

  const filteredHomeSearchAgents = catalogAgents.filter(agent =>
    agent.title.toLowerCase().includes(homeSearchQuery.toLowerCase())
  );

  const catalogCategoryNameById = useMemo(() => {
    const map: Record<string, string> = {};
    catalogCategories.forEach((c) => { map[c.id] = c.name; });
    return map;
  }, [catalogCategories]);



  // Scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSelectAgent = (title: string) => {
    setView('builder');
    setSelectedAgent(title);
    const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
    const currentBrandId = activeProject?.brand_config_id || savedBrandId;
    if (currentBrandId) {
      const bTitle = brandsMap[currentBrandId] || activeProject?.title || 'Brand Project';
      setActiveProject({ id: '', title: bTitle, brand_config_id: currentBrandId });
    }
    setMessages([]);
    setPromptText('');
    setUserContext('');
    setAttachedFiles([]);
    setQaAnswers([]);
    const prompt = title === 'Competition Analysis'
      ? `Identify your true market position and uncover competitor blind spots. Get a feature-by-feature breakdown of where you win, lose, and how to differentiate.`
      : title === 'GTM Strategy'
      ? `Launch with confidence using a complete Go-To-Market roadmap. Define your target audience, pricing, and distribution channels to maximize market impact.`
      : (agentPrompts[title] || `Generate a detailed ${title.toLowerCase()} report based on our brand research data.`);
    setPromptText(prompt);
    setShowBanner(true);
    setShowQuestionnaire(!!agentQuestions[title]);
  };

  const handleRevert = () => {
    setSelectedAgent(null);
    setPromptText('');
    setUserContext('');
    setAttachedFiles([]);
    setShowBanner(false);
    setShowQuestionnaire(false);
    setMessages([]);
    setQaAnswers([]);
  };

  const handleNewChat = () => {
    setView('builder');
    setSelectedAgent(null);
    setPromptText('');
    setUserContext('');
    setAttachedFiles([]);
    setShowBanner(false);
    setShowQuestionnaire(false);
    setMessages([]);
    setQaAnswers([]);
    setActiveProject(null);
    onNewChat?.();
  };

  const handleQuestionnaireComplete = (answers: Array<{ question: string; answer: string }>) => {
    // Append to prompt immediately
    const qaSection = answers
      .map(a => `Q: ${a.question}\nA: ${a.answer}`)
      .join('\n\n');
    
    setPromptText(prev => prev ? `${prev}\n\n── Additional Context ──\n${qaSection}` : qaSection);
    setShowQuestionnaire(false);
  };

  const handleQuestionnaireDismiss = () => setShowQuestionnaire(false);

  const loadProjectById = async (projectId: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/projects/${projectId}`, { headers });
      if (res.ok) {
        const proj = await res.json();
        setView('builder');
        setSelectedAgent(proj.agent_type || null);
        if (proj.llm_provider) {
          setSelectedModel(proj.llm_provider);
        }
        if (proj.brand_config_id) {
          const brandName = brandsMap[proj.brand_config_id] || 'Brand Project';
          setActiveProject({
            id: proj.id,
            title: proj.title || brandName,
            brand_config_id: proj.brand_config_id,
          });
        }
        if (proj.messages && proj.messages.length > 0) {
          const loadedMsgs = proj.messages.map((m: any) => ({
            id: m.id,
            role: m.role,
            content: m.content,
            message_metadata: m.message_metadata,
          }));
          setMessages(loadedMsgs);
        } else {
          setMessages([]);
        }
        if (proj.id) {
          fetchReportsForProject(proj.id);
        }
      }
    } catch (err) {
      console.error('Failed to load project details:', err);
    }
  };

  // Listen for events from Sidebar and ProjectsView
  useEffect(() => {
    const onNewChat = () => handleNewChat();
    const onOpenProject = (e: Event) => {
      const detail = (e as CustomEvent).detail;
      if (detail?.projectId) {
        loadProjectById(detail.projectId);
      }
    };
    const onOpenConnectors = () => setConnectorsOpen(true);
    const onOpenConnectorsView = () => setView('connectors');
    const onOpenFiles = () => setView('files');
    const onOpenProjects = () => setView('projects');
    const onOpenAgents = () => setView('agents');
    const onOpenWorkflow = () => setView('workflow');
    window.addEventListener('newChat', onNewChat);
    window.addEventListener('openProject', onOpenProject);
    window.addEventListener('openConnectors', onOpenConnectors);
    window.addEventListener('openConnectorsView', onOpenConnectorsView);
    window.addEventListener('openFiles', onOpenFiles);
    window.addEventListener('openProjects', onOpenProjects);
    window.addEventListener('openAgents', onOpenAgents);
    window.addEventListener('openWorkflow', onOpenWorkflow);
    return () => {
      window.removeEventListener('newChat', onNewChat);
      window.removeEventListener('openProject', onOpenProject);
      window.removeEventListener('openConnectors', onOpenConnectors);
      window.removeEventListener('openConnectorsView', onOpenConnectorsView);
      window.removeEventListener('openFiles', onOpenFiles);
      window.removeEventListener('openProjects', onOpenProjects);
      window.removeEventListener('openAgents', onOpenAgents);
      window.removeEventListener('openWorkflow', onOpenWorkflow);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [brandsMap]);

  // Submit message → call backend + stream response
  const handleSubmit = async () => {
    if (!promptText.trim()) return;
    let baseContent = promptText.trim();
    if (userContext.trim()) {
      baseContent += `\n\n── User Context ──\n${userContext.trim()}`;
    }
    if (attachedFiles.length > 0) {
      baseContent += `\n\n── Attached Files ──\n` + attachedFiles.map(f => `📄 ${f.name}`).join('\n');
    }

    // Translate UI prompt to backend execution request if initial card prompt is sent
    let apiUserContent = baseContent;
    if (selectedAgent === 'Competition Analysis' && baseContent.includes('Identify your true market position and uncover competitor blind spots')) {
      apiUserContent = `Generate a complete competitive analysis strategy report for my brand and competitors based on all our scanned website and Instagram knowledge base data. Include full comparison tables, Recharts dashboard visualizations for pricing/scale/share of voice, SWOT analysis, and personalized next steps.`;
    } else if (selectedAgent === 'GTM Strategy' && baseContent.includes('Launch with confidence using a complete Go-To-Market roadmap')) {
      apiUserContent = `Generate an exhaustive, highly visual Go-To-Market (GTM) strategy report for our brand and competitors using our scanned knowledge base data and our answers to the 4 GTM setup questions. Include all 5 required Recharts dashboards (Target Customer Segment Breakdown, Marketing & Channel Budget Allocation, Channel Growth Potential vs Constraints, GTM Execution Intensity per Phase, and Competitive Positioning & Pricing Tier Index), full competitive matrices, 90-day roadmap, and risk mitigation plan.`;
    }

    const userMsg: Message = { role: 'user', content: baseContent };
    const thinking: Message = { role: 'thinking', content: '' };

    // Build conversation history (only user + assistant, skip thinking/error)
    const history = [...messages, { role: 'user', content: apiUserContent }]
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.content }));

    // Get system prompt for selected agent
    const systemPrompt = selectedAgent
      ? (agentPrompts[selectedAgent] || `You are a helpful ${selectedAgent} agent. Help the user with their request.`)
      : 'You are StratAI, a helpful AI strategy assistant. Help the user with their business strategy, marketing, sales, and growth questions. Be concise, actionable, and data-driven.';

    setMessages(prev => [...prev, userMsg, thinking]);
    setPromptText('');
    setUserContext('');
    setAttachedFiles([]);
    setQaAnswers([]);
    setShowBanner(false);
    setShowQuestionnaire(false);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      let targetProjectId = activeProject?.id;
      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const activeBrandId = (activeProject?.brand_config_id && activeProject.brand_config_id !== '') 
        ? activeProject.brand_config_id 
        : (savedBrandId || (brandsList.length > 0 ? brandsList[0].id : (projectsList.length > 0 ? projectsList[0].brand_config_id : null)));

      if (!targetProjectId || targetProjectId === '') {
        if (activeBrandId) {
          const createRes = await fetch(`${apiBase}/api/projects/`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              title: selectedAgent || 'New Strategy Chat',
              agent_type: selectedAgent || 'StratAI',
              brand_config_id: activeBrandId,
              llm_provider: selectedModel,
            })
          });
          if (createRes.ok) {
            const newP = await createRes.json();
            targetProjectId = newP.id;
            const bTitle = brandsMap[activeBrandId] || newP.title;
            setActiveProject({ id: newP.id, title: bTitle, brand_config_id: activeBrandId });
            if (typeof window !== 'undefined') {
              localStorage.setItem('brand_config_id', activeBrandId);
            }
            window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: targetProjectId, brand_config_id: activeBrandId } }));
          }
        }
      }

      if (!targetProjectId) {
        setMessages(prev => [
          ...prev.filter(m => m.role !== 'thinking'),
          { role: 'error', content: 'No active project selected. Please select or create a project first.' },
        ]);
        return;
      }

      const res = await fetch(`${apiBase}/api/chat/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          project_id: targetProjectId,
          messages: history,
          provider: selectedModel,
        }),
      });

      if (!res.ok || !res.body) {
        setActiveProject(null);
        if (res.status === 401) {
          localStorage.removeItem('access_token');
          window.location.href = '/auth';
          return;
        }
        setMessages(prev => [
          ...prev.filter(m => m.role !== 'thinking'),
          { role: 'error', content: `Server error (${res.status}). Make sure the backend is running on port 8000.` },
        ]);
        return;
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let assistantText = '';
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const payload = JSON.parse(line.slice(6));
            if (payload.type === 'token') {
              assistantText += payload.content;
              setMessages(prev => {
                const updated = [...prev];
                const thinkIdx = updated.findIndex(m => m.role === 'thinking');
                if (thinkIdx !== -1) {
                  updated[thinkIdx] = { role: 'assistant', content: assistantText };
                } else {
                  const lastIdx = updated.length - 1;
                  if (updated[lastIdx]?.role === 'assistant') {
                    updated[lastIdx] = { role: 'assistant', content: assistantText };
                  }
                }
                return updated;
              });
            } else if (payload.type === 'error') {
              if (!assistantText) {
                setActiveProject(null);
              }
              setMessages(prev => [
                ...prev.filter(m => m.role !== 'thinking'),
                { role: 'error', content: payload.content },
              ]);
              return;
            }
          } catch { /* skip malformed lines */ }
        }
      }

      // Ensure thinking is replaced even if no tokens came
      if (!assistantText) {
        setActiveProject(null);
        setMessages(prev => prev.filter(m => m.role !== 'thinking'));
      }

      // Notify Sidebar & ProjectsView that chat has completed and title/history updated
      window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: targetProjectId } }));
      loadProjectsAndBrands();
      if (assistantText) {
        // Re-sync messages (picks up the real persisted id) + reports map, so a
        // freshly-snapshotted report becomes downloadable without a page reload.
        await loadProjectById(targetProjectId);
      }
    } catch (err) {
      setActiveProject(null);
      setMessages(prev => [
        ...prev.filter(m => m.role !== 'thinking'),
        { role: 'error', content: 'Could not connect to backend. Make sure `uvicorn main:app --reload` is running on port 8000.' },
      ]);
    }

  };

  const isChatting = messages.length > 0;

  return (
    <main className={styles.main}>


      {/* Top Bar */}
      <header className={styles.topBar}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          {(selectedAgent || isChatting || view === 'files' || view === 'projects' || view === 'agents' || view === 'workflow' || view === 'connectors') && (
            <button 
              className={styles.shareBtn} 
              style={{ padding: '6px 8px', marginLeft: 0 }} 
              onClick={() => {
                if (view === 'files' || view === 'projects' || view === 'agents' || view === 'workflow' || view === 'connectors') {
                  setView('builder');
                } else {
                  handleRevert();
                }
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="19" y1="12" x2="5" y2="12"/><polyline points="12 19 5 12 12 5"/></svg>
              Go back
            </button>
          )}

          <div className={styles.dropdownContainer} ref={dropdownRef}>
            <button 
              className={styles.dropdownToggle}
              onClick={() => {
                loadProjectsAndBrands();
                setDropdownOpen(prev => !prev);
              }}
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/></svg>
              <span>{activeProject ? activeProject.title : 'Select Project'}</span>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ transform: dropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s' }}><polyline points="6 9 12 15 18 9"/></svg>
            </button>

            {dropdownOpen && (
              <div className={styles.dropdownMenu}>
                <div className={styles.dropdownHeader}>ACTIVE BRAND PROJECTS</div>
                <div className={styles.dropdownList}>
                  {(() => {
                    const displayItems: { brand_config_id: string; title: string; proj_id: string; date?: string }[] = [];
                    
                    brandsList.forEach((b: any) => {
                      const proj = projectsList.find((p: any) => p.brand_config_id === b.id);
                      displayItems.push({
                        brand_config_id: b.id,
                        title: b.brand_name,
                        proj_id: proj ? proj.id : b.id,
                        date: b.created_at ? new Date(b.created_at).toLocaleDateString() : undefined
                      });
                    });

                    projectsList.forEach((proj: any) => {
                      if (proj.brand_config_id && !displayItems.some(item => item.brand_config_id === proj.brand_config_id)) {
                        displayItems.push({
                          brand_config_id: proj.brand_config_id,
                          title: brandsMap[proj.brand_config_id] || proj.title || 'Brand Project',
                          proj_id: proj.id,
                          date: proj.created_at ? new Date(proj.created_at).toLocaleDateString() : undefined
                        });
                      }
                    });

                    if (displayItems.length === 0) {
                      return <div className={styles.dropdownEmpty}>No brand projects found</div>;
                    }

                    return displayItems.map((item) => {
                      const isActive = activeProject?.brand_config_id === item.brand_config_id;
                      return (
                        <button
                          key={item.brand_config_id}
                          type="button"
                          className={`${styles.dropdownItem} ${isActive ? styles.dropdownItemActive : ''}`}
                          onClick={() => {
                            setActiveProject({
                              id: item.proj_id,
                              title: item.title,
                              brand_config_id: item.brand_config_id,
                            });
                            if (typeof window !== 'undefined') {
                              localStorage.setItem('brand_config_id', item.brand_config_id);
                            }
                            setDropdownOpen(false);
                            window.dispatchEvent(new CustomEvent('projectChanged', { detail: { projectId: item.proj_id, brand_config_id: item.brand_config_id } }));
                          }}
                        >
                          <div style={{ fontWeight: 600, fontSize: '13px', color: '#1A1A1A' }}>
                            {item.title}
                          </div>
                          {item.date && (
                            <div style={{ fontSize: '11px', color: '#6B6560', marginTop: '2px' }}>
                              Created {item.date}
                            </div>
                          )}
                        </button>
                      );
                    });
                  })()}
                </div>
              </div>
            )}
          </div>
        </div>
        <div className={styles.spacer} />
        {latestAssistantIdx !== -1 && (
          <button 
            className={styles.downloadTopBarBtn} 
            onClick={() => handleDownloadPdf(latestAssistantIdx, messages[latestAssistantIdx].content)}
            disabled={downloadingMsgIdx !== null}
            title="Download latest strategy report as PDF"
          >
            {downloadingMsgIdx === latestAssistantIdx ? (
              <>
                <span className={styles.downloadSpinner} />
                <span>Exporting PDF...</span>
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                  <polyline points="7 10 12 15 17 10" />
                  <line x1="12" y1="15" x2="12" y2="3" />
                </svg>
                <span>Download Report (PDF)</span>
              </>
            )}
          </button>
        )}
        <button className={styles.shareBtn} onClick={() => setShareOpen(true)}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8"/><polyline points="16 6 12 2 8 6"/><line x1="12" y1="2" x2="12" y2="15"/></svg>
          Share
        </button>
      </header>

      {/* Scrollable Content */}
      <div className={styles.contentArea}>
        {view === 'connectors' ? (
          <ConnectorsView />
        ) : (
        <div className={`${styles.container} ${isChatting || selectedAgent ? styles.chatContainerPadding : ''}`}>

          {view === 'files' ? (
            <FilesView />
          ) : view === 'projects' ? (
            <ProjectsView />
          ) : view === 'workflow' ? (
            <WorkflowView />
          ) : view === 'agents' ? (
            <TemplateGrid onSelectAgent={handleSelectAgent} />
          ) : isChatting ? (
            /* ── Chat messages view ───────────────────── */
            <div className={styles.chatMessages}>
              {/* Agent name header */}
              {selectedAgent && (
                <div className={styles.chatAgentHeader}>
                  <div className={styles.chatAgentLogo}>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <span className={styles.chatAgentName}>{selectedAgent}</span>
                </div>
              )}
              {messages.map((msg, i) =>
                msg.role === 'user' ? (
                  <div key={i} className={styles.userBubbleWrapper}>
                    <div className={styles.userBubble}>
                      <pre className={styles.userBubbleText}>{msg.content}</pre>
                    </div>
                  </div>
                ) : msg.role === 'thinking' ? (
                  <div key={i} className={styles.thinkingWrapper}>
                    <div className={styles.thinkingIcon}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <defs><linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#a78bfa"/><stop offset="100%" stopColor="#d4a843"/></linearGradient></defs>
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                      </svg>
                    </div>
                    <div className={styles.thinkingBubble}>
                      <span className={styles.thinkingLabel}>Thinking</span>
                      <span className={styles.thinkingDots}>
                        <span /><span /><span />
                      </span>
                    </div>
                  </div>
                ) : msg.role === 'error' ? (
                  <div key={i} className={styles.thinkingWrapper}>
                    <div className={styles.thinkingIcon} style={{ background: 'linear-gradient(135deg, #ef4444, #f97316)' }}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
                      </svg>
                    </div>
                    <div className={styles.assistantBubble}>
                      <pre className={styles.assistantText} style={{ color: '#dc2626' }}>{msg.content}</pre>
                    </div>
                  </div>
                ) : (
                  <div key={i} className={styles.thinkingWrapper}>
                    <div className={styles.thinkingIcon}>
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <defs><linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#a78bfa"/><stop offset="100%" stopColor="#d4a843"/></linearGradient></defs>
                        <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                      </svg>
                    </div>
                    <div className={styles.assistantBubble}>
                      <div className={styles.reportActionBar}>
                        <div className={styles.reportBadge}>
                          <span className={styles.reportBadgeDot} />
                          <span>{selectedAgent ? `${selectedAgent} Strategy` : 'StratAI Report'}</span>
                        </div>
                        <div className={styles.reportActionsGroup}>
                          <button
                            type="button"
                            className={styles.reportActionBtn}
                            onClick={() => handleCopyReport(i, msg.content)}
                            title="Copy report markdown"
                          >
                            {copiedMsgIdx === i ? (
                              <>
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                  <polyline points="20 6 9 17 4 12" />
                                </svg>
                                <span style={{ color: '#16a34a' }}>Copied!</span>
                              </>
                            ) : (
                              <>
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                                </svg>
                                <span>Copy</span>
                              </>
                            )}
                          </button>
                          <button
                            type="button"
                            className={`${styles.reportActionBtn} ${styles.reportDownloadBtn}`}
                            onClick={() => handleDownloadPdf(i, msg.content)}
                            disabled={downloadingMsgIdx === i}
                            title="Download this report as PDF"
                          >
                            {downloadingMsgIdx === i ? (
                              <>
                                <span className={styles.downloadSpinner} />
                                <span>Exporting PDF...</span>
                              </>
                            ) : (
                              <>
                                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                  <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                  <polyline points="7 10 12 15 17 10" />
                                  <line x1="12" y1="15" x2="12" y2="3" />
                                </svg>
                                <span>Download PDF</span>
                              </>
                            )}
                          </button>
                          {msg.id && reportsByMessageId[msg.id] && (
                            <button
                              type="button"
                              className={`${styles.reportActionBtn} ${styles.reportDownloadBtn}`}
                              onClick={() => handleDownloadDocx(i, msg.id!)}
                              disabled={downloadingDocxIdx === i}
                              title="Download this report as DOCX"
                            >
                              {downloadingDocxIdx === i ? (
                                <>
                                  <span className={styles.downloadSpinner} />
                                  <span>Exporting DOCX...</span>
                                </>
                              ) : (
                                <>
                                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                    <polyline points="7 10 12 15 17 10" />
                                    <line x1="12" y1="15" x2="12" y2="3" />
                                  </svg>
                                  <span>Download DOCX</span>
                                </>
                              )}
                            </button>
                          )}
                          {docxErrorIdx === i && (
                            <span style={{ color: '#dc2626', fontSize: '11px', marginLeft: '4px' }}>
                              Failed to export DOCX
                            </span>
                          )}
                          {msg.id && reportsByMessageId[msg.id] && (
                            <button
                              type="button"
                              className={`${styles.reportActionBtn} ${styles.reportDownloadBtn}`}
                              onClick={() => handleShareReport(i, msg.id!)}
                              disabled={sharingReportIdx === i}
                              title="Copy a public, read-only link to this report"
                            >
                              {sharingReportIdx === i ? (
                                <>
                                  <span className={styles.downloadSpinner} />
                                  <span>Creating link...</span>
                                </>
                              ) : shareCopiedIdx === i ? (
                                <>
                                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                    <polyline points="20 6 9 17 4 12" />
                                  </svg>
                                  <span style={{ color: '#16a34a' }}>Link copied!</span>
                                </>
                              ) : (
                                <>
                                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                    <path d="M4 12v8a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-8" />
                                    <polyline points="16 6 12 2 8 6" />
                                    <line x1="12" y1="2" x2="12" y2="15" />
                                  </svg>
                                  <span>Share</span>
                                </>
                              )}
                            </button>
                          )}
                          {shareErrorIdx === i && (
                            <span style={{ color: '#dc2626', fontSize: '11px', marginLeft: '4px' }}>
                              Failed to create share link
                            </span>
                          )}
                        </div>
                      </div>

                      <div id={`report-markdown-${i}`} className={styles.assistantTextMarkdown}>
                        <ReportRenderer content={msg.content} />
                      </div>

                      <div className={styles.reportFooterBanner}>
                        <div className={styles.reportFooterLeft}>
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#D4A843" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                            <polyline points="14 2 14 8 20 8" />
                            <line x1="16" y1="13" x2="8" y2="13" />
                            <line x1="16" y1="17" x2="8" y2="17" />
                            <polyline points="10 9 9 9 8 9" />
                          </svg>
                          <span>Complete strategy ready for executive download</span>
                        </div>
                        <button
                          type="button"
                          className={styles.reportFooterDownloadBtn}
                          onClick={() => handleDownloadPdf(i, msg.content)}
                          disabled={downloadingMsgIdx === i}
                          title="Download full report as PDF"
                        >
                          {downloadingMsgIdx === i ? (
                            <>
                              <span className={styles.downloadSpinner} />
                              <span>Generating PDF...</span>
                            </>
                          ) : (
                            <>
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                                <polyline points="7 10 12 15 17 10" />
                                <line x1="12" y1="15" x2="12" y2="3" />
                              </svg>
                              <span>Download PDF Report</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                )
              )}
              <div style={{ height: '360px', width: '100%', flexShrink: 0 }} />
              <div ref={messagesEndRef} />
            </div>
          ) : selectedAgent ? (
            /* ── Agent detail (pre-chat) ─────────────── */
            <div className={styles.agentDetailContainer}>
              <div className={styles.pageHeader}>
                <div className={styles.ghostIcon}>
                  <svg width="48" height="48" viewBox="0 0 24 24" fill="#7c3aed">
                    <path d="M12 2C6.48 2 2 6.48 2 12v8c0 1.1.9 2 2 2h4v-6h4v6h4v-6h4v6h2c1.1 0 2-.9 2-2v-8c0-5.52-4.48-10-10-10zm-4 10c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2zm8 0c-1.1 0-2-.9-2-2s.9-2 2-2 2 .9 2 2-.9 2-2 2z"/>
                  </svg>
                </div>
                <h1 className={styles.title}>{selectedAgent}</h1>
              </div>
            </div>
          ) : (
            /* ── Build your agent (idle home page) ─────── */
            <div className={styles.homeContainer}>
              <div className={styles.homeWelcome}>
                <div className={styles.welcomeHeadingRow}>
                  <h1 className={styles.welcomeTitle}>Welcome to StratAI</h1>
                  <div className={styles.welcomePurpleIcon}>
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                    </svg>
                  </div>
                </div>
                <p className={styles.welcomeSubtitle}>How can I help?</p>
              </div>

              <div className={styles.homeTemplatesSection}>
                <div className={styles.homeTemplatesHeader}>
                  <span className={styles.homeTemplatesTitle}>Templates</span>
                  
                  {/* Search input with live dropdown */}
                  <div className={styles.searchContainer} ref={homeSearchContainerRef}>
                    <div className={styles.searchInputWrapper}>
                      <svg className={styles.searchIcon} width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="11" cy="11" r="8" />
                        <line x1="21" y1="21" x2="16.65" y2="16.65" />
                      </svg>
                      <input
                        type="text"
                        className={styles.searchInput}
                        placeholder="Search templates..."
                        value={homeSearchQuery}
                        onChange={(e) => setHomeSearchQuery(e.target.value)}
                      />
                    </div>

                    {homeSearchQuery.trim() !== '' && filteredHomeSearchAgents.length > 0 && (
                      <div className={styles.searchDropdown}>
                        {filteredHomeSearchAgents.map((agent) => (
                          <button
                            key={agent.id}
                            type="button"
                            className={styles.dropdownItem}
                            onClick={() => {
                              handleSelectAgent(agent.title);
                              setHomeSearchQuery('');
                            }}
                          >
                            <div className={styles.dropdownItemContent}>
                              <span className={styles.dropdownItemTitle}>{agent.title}</span>
                              <span className={styles.dropdownItemCategory}>
                                {catalogCategoryNameById[agent.category] || agent.category}
                              </span>
                            </div>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
                <div className={styles.homeTemplatesGrid}>
                  {agentsLoading && (
                    Array.from({ length: 6 }).map((_, i) => (
                      <div key={i} className={`${styles.homeTemplateCard} ${styles.homeGridSkeletonCard}`} aria-hidden="true" />
                    ))
                  )}
                  {!agentsLoading && agentsError && (
                    <div className={styles.homeGridErrorState}>
                      <p>Couldn&apos;t load the agent catalog. {agentsError}</p>
                      <button type="button" className={styles.homeGridRetryBtn} onClick={refetchAgents}>
                        Retry
                      </button>
                    </div>
                  )}
                  {!agentsLoading && !agentsError && catalogAgents.map((agent) => (
                    <div
                      key={agent.id}
                      className={styles.homeTemplateCard}
                      onClick={() => handleSelectAgent(agent.title)}
                    >
                      <div className={styles.homeCardTop}>
                        <div className={styles.homeCardTitle}>{agent.title}</div>
                        <div className={styles.homeCardDesc}>{agent.description}</div>
                      </div>
                      <div className={styles.homeCardBottom}>
                        <div className={styles.homeIconGroup}>
                          {agent.connectors.slice(0, 3).map((conn, idx) => (
                            <div key={idx} className={styles.homeMiniIcon}>
                              <img
                                src={getLogoUrl(getDomain(conn))}
                                alt={conn}
                                className={styles.homeMiniIconImg}
                              />
                            </div>
                          ))}
                        </div>
                        {agent.connectors.length > 3 && (
                          <span className={styles.homePlusOne}>
                            +{agent.connectors.length - 3}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className={styles.homeChatboxWrapper}>
                <ChatInput
                  value={promptText}
                  onChange={setPromptText}
                  showBanner={showBanner}
                  onRevert={handleRevert}
                  onSubmit={handleSubmit}
                  userContext={userContext}
                  onChangeUserContext={setUserContext}
                  attachedFiles={attachedFiles}
                  onAddFiles={(files) => setAttachedFiles(prev => [...prev, ...files])}
                  onRemoveFile={(index) => setAttachedFiles(prev => prev.filter((_, i) => i !== index))}
                  onOpenConnectors={() => setConnectorsOpen(true)}
                  selectedModel={selectedModel}
                  onSelectModel={setSelectedModel}
                />
              </div>
            </div>
          )}

        </div>
        )}
      </div>

      {/* Chat Input Fixed at Bottom */}
      {view !== 'files' && view !== 'projects' && view !== 'agents' && (selectedAgent !== null || isChatting) && (
        <div className={styles.chatContainer}>
          {showQuestionnaire && selectedAgent && agentQuestions[selectedAgent] && (
            <AgentQuestionnaire
              questions={agentQuestions[selectedAgent]}
              onComplete={handleQuestionnaireComplete}
              onDismiss={handleQuestionnaireDismiss}
            />
          )}
          <ChatInput
            value={promptText}
            onChange={setPromptText}
            showBanner={showBanner}
            onRevert={handleRevert}
            onSubmit={handleSubmit}
            userContext={userContext}
            onChangeUserContext={setUserContext}
            attachedFiles={attachedFiles}
            onAddFiles={(files) => setAttachedFiles(prev => [...prev, ...files])}
            onRemoveFile={(index) => setAttachedFiles(prev => prev.filter((_, i) => i !== index))}
            defaultUserContextOpen={!!selectedAgent}
            onOpenConnectors={() => setConnectorsOpen(true)}
            selectedModel={selectedModel}
            onSelectModel={setSelectedModel}
          />
        </div>
      )}

      <ConnectorsPanel open={connectorsOpen} onClose={() => setConnectorsOpen(false)} />

      {/* Share Modal */}
      {shareOpen && (
        <div className={styles.shareOverlay} onClick={() => setShareOpen(false)}>
          <div className={styles.shareModal} onClick={(e) => e.stopPropagation()}>
            <button className={styles.shareModalClose} onClick={() => setShareOpen(false)}>&times;</button>
            <h2 className={styles.shareModalTitle}>Share This Agent</h2>
            <p className={styles.shareModalDesc}>Sharing this agent will allow other users to chat with it and edit its configuration, settings, and view their chat history with it.</p>

            <div className={styles.shareModalLabel}>Users &bull; 1</div>
            <div className={styles.shareSearchRow}>
              <div className={styles.shareSearchInput}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg>
                <input type="text" placeholder="Add people" />
              </div>
              <button className={styles.shareActionBtn}>Share</button>
            </div>

            <div className={styles.shareUserRow}>
              <div className={styles.shareUserAvatar}>U</div>
              <span className={styles.shareUserName}>User <span style={{color:'#9ca3af'}}>(you)</span></span>
              <span className={styles.shareUserRole}>Owner</span>
            </div>

            <div className={styles.shareAccessSection}>
              <div className={styles.shareAccessTitle}>General Access</div>
              <div className={styles.shareAccessRow}>
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>
                <div>
                  <div className={styles.shareAccessLabel}>Restricted</div>
                  <div className={styles.shareAccessDesc}>Only users with direct access can view this Agent</div>
                </div>
              </div>
            </div>

            <div className={styles.shareLinkSection}>
              <button className={styles.shareLinkBtn}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/></svg>
                Copy agent link
              </button>
              <button className={styles.shareLinkBtn}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>
                Copy setup link
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
