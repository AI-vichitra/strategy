'use client';
import { useState, useEffect, useRef, useMemo } from 'react';
import { useSearchParams, useRouter as useNextRouter } from 'next/navigation';
import TemplateGrid from './TemplateGrid';
import { useTemplates } from '../../hooks/useTemplates';
import ChatInput from './ChatInput';
import AgentQuestionnaire, { type Question } from './AgentQuestionnaire';
import CompetitorForm, { type CompetitorDetail } from '../CompetitorForm';
import BrandKitForm, { type BrandKit } from '../BrandKitForm';
import ExportMenu from '../ExportMenu';
import ConnectorsPanel from './ConnectorsPanel';
import ConnectorsView from './ConnectorsView';
import FilesView from './FilesView';
import ProjectsView from './ProjectsView';
import WorkflowView from './WorkflowView';
import styles from './MainContent.module.css';
import ReportRenderer from '../ReportRenderer';
import SectionEditor from '../SectionEditor';
import TaskIntakeQuestions, { type TaskIntakeData, type TaskIntakeAnswer } from './TaskIntakeQuestions';
import TaskBriefSummary from './TaskBriefSummary';
import ResearchDirection, { type ResearchSelection } from './ResearchDirection';
import { buildTaskBrief, type TaskBrief } from './taskBrief';

type Message = { role: 'user' | 'thinking' | 'assistant' | 'error'; content: string; message_metadata?: string; id?: string };
type ReportInfo = { id: string; title: string; agent_type: string };

// Must match the notice text ai_service.stream_chat embeds directly in a
// truncated report's content (backend/services/ai_service.py). No separate
// persisted flag exists (see TASK: "skip Message persistence") — a reloaded
// message's own content is the only record of truncation, so detecting it
// here is what makes the banner survive a reload/reopen.
const TRUNCATION_MARKER = 'GENERATION TRUNCATED';
function isTruncatedContent(content: string): boolean {
  return content.includes(TRUNCATION_MARKER);
}

// Superseded by the Step-2 task-intake cards (TaskIntakeQuestions /
// TaskBriefSummary). Typed as `boolean`, not the literal `false` — a literal
// `false &&` makes TypeScript treat the guarded branch as unreachable and it
// drops the enclosing `selectedAgent` narrowing there, which this avoids.
const SHOW_LEGACY_AGENT_QUESTIONNAIRE: boolean = false;

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

// Collapsed-by-default summary shown once at the top of a task's chat
// thread, modeled on ReportRenderer.tsx's CollapsibleSection but compact
// (.taskBriefBar*) since it sits above the conversation rather than inside
// report content.
function TaskBriefBar({ brief }: { brief: TaskBrief }) {
  const [expanded, setExpanded] = useState(false);
  return (
    <div className={styles.taskBriefBar}>
      <button
        type="button"
        className={styles.taskBriefBarHeader}
        onClick={() => setExpanded(e => !e)}
        aria-expanded={expanded}
      >
        <span className={styles.taskBriefBarTitle}>Task Brief — {brief.task ?? 'Task'}</span>
        <span className={`${styles.taskBriefBarChevron} ${expanded ? styles.taskBriefBarChevronOpen : ''}`}>
          ▼
        </span>
      </button>
      {expanded && (
        <div className={styles.taskBriefBarBody}>
          <TaskBriefSummary brief={brief} readOnly />
        </div>
      )}
    </div>
  );
}

// One-line "Goal: Leads · Scope: Whole brand · …" summary of what the user
// actually picked/typed/edited across the questions+brief cards (every
// TaskBriefItem buildTaskBrief/TaskBriefSummary's own edit path tags
// source:'you') — posted as the user's own right-aligned chat bubble the
// instant they click Continue, replacing the card. Anything they skipped
// never got a source:'you' item in the first place, so it's omitted for
// free; if they skipped everything, falls back to one line rather than
// posting an empty bubble.
function buildSelectionSummaryLine(brief: TaskBrief): string {
  const picked = brief.items.filter(item => item.source === 'you');
  if (picked.length === 0) return 'Using best judgement for the rest.';
  return picked.map(item => `${item.name}: ${item.value}`).join(' · ');
}

// Ordered stage ids for the staged generation-progress stepper. 'kb_wait' is
// conditional — most generations skip the research-pipeline wait entirely,
// so it's only shown once the backend's 'status' event actually fires.
const GEN_STAGE_ORDER = ['preparing', 'researching', 'kb_wait', 'retrieving', 'composing', 'generating'] as const;
type GenStageId = typeof GEN_STAGE_ORDER[number];

const GEN_STAGE_LABELS: Record<GenStageId, string> = {
  preparing: 'Preparing your report',
  researching: 'Researching your market',
  kb_wait: 'Building brand knowledge base',
  retrieving: 'Retrieving brand research',
  composing: 'Composing your report',
  generating: 'Writing your report',
};

type StepStatus = 'done' | 'active' | 'pending';
type StepRowData = { key: string; status: StepStatus; label: string };

// Shared checklist row + list markup for every staged progress indicator in
// this file (GenerationProgress and SetupStepper below) — one place for the
// done(check)/active(bold)/pending(dimmed) look so the two can never drift
// apart visually.
// `onToggle` is only ever passed by GenerationProgress's own collapsed/expanded
// toggle row (see below) — every other caller (SetupStepper, and
// GenerationProgress's own non-toggle rows) renders a plain, non-interactive
// row exactly as before.
function StepRow({
  status, label, chevronOpen, onToggle,
}: {
  status: StepStatus; label: string; chevronOpen?: boolean; onToggle?: () => void;
}) {
  const statusClass = status === 'done' ? styles.genProgressRow_done : status === 'active' ? styles.genProgressRow_active : styles.genProgressRow_pending;
  const icon = (
    <span className={styles.genProgressIcon}>
      {status === 'done' ? (
        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      ) : status === 'active' ? (
        <span className={styles.genProgressActiveDot} />
      ) : (
        <span className={styles.genProgressDot} />
      )}
    </span>
  );

  if (onToggle) {
    return (
      <button
        type="button"
        className={`${styles.genProgressRow} ${styles.genProgressRowToggle} ${statusClass}`}
        onClick={onToggle}
        aria-expanded={!!chevronOpen}
      >
        <span className={styles.genProgressRowMain}>
          {icon}
          <span>{label}</span>
        </span>
        <span className={`${styles.genProgressChevron} ${chevronOpen ? styles.genProgressChevronOpen : ''}`}>
          ▼
        </span>
      </button>
    );
  }

  return (
    <div className={`${styles.genProgressRow} ${statusClass}`}>
      {icon}
      <span>{label}</span>
    </div>
  );
}

function StepList({ rows }: { rows: StepRowData[] }) {
  return (
    <div className={styles.genProgress}>
      {rows.map(r => <StepRow key={r.key} status={r.status} label={r.label} />)}
    </div>
  );
}

// Vertical stepper driven by real backend 'stage'/'status' SSE events plus
// the client-side "first token received" milestone (see the token branch in
// handleSubmit's SSE loop) — never a fake timed animation.
//
// Collapsed by default (presentation only — `expanded` is local state, never
// touches `stage`/SSE handling): shows ONLY the current running step (or the
// last step, "done", once nothing is active) with a chevron on the right of
// that same row; clicking it reveals the full list below, that row now
// carrying the rotated chevron as its "collapse" control. As SSE advances
// `stage` while collapsed, the single shown row re-derives from `stage` on
// every render exactly as the full list already did, so it updates live with
// no extra state to keep in sync.
function GenerationProgress({
  stage,
  kbWaitText,
  kbWaitSeen,
}: {
  stage: string | null;
  kbWaitText: string | null;
  kbWaitSeen: boolean;
}) {
  const [expanded, setExpanded] = useState(false);

  const visibleStages = GEN_STAGE_ORDER.filter(s => s !== 'kb_wait' || kbWaitSeen);
  const currentIndex = stage ? visibleStages.indexOf(stage as GenStageId) : -1;

  const rows: StepRowData[] = visibleStages.map((s, i) => {
    const status: StepStatus = currentIndex === -1 ? 'pending' : i < currentIndex ? 'done' : i === currentIndex ? 'active' : 'pending';
    // While the kb_wait row is active, show the backend's own live text (it
    // already carries the elapsed-seconds counter) instead of the static
    // label, so the two never read as duplicated phrasing.
    const label = s === 'kb_wait' && status === 'active' && kbWaitText ? kbWaitText : GEN_STAGE_LABELS[s];
    return { key: s, status, label };
  });

  if (rows.length === 0) return null;

  // The one row the collapsed view shows, and the one row the expanded view
  // gives the chevron to: whichever is currently running, or — once nothing
  // is — the final row, re-labelled "Done" so a finished-but-still-mounted
  // stepper never looks stuck on a stale stage name.
  const activeRow = rows.find(r => r.status === 'active');
  const allDone = rows.every(r => r.status === 'done');
  const toggleRow = activeRow ?? (allDone ? { ...rows[rows.length - 1], label: 'Done' } : rows[rows.length - 1]);

  const toggle = () => setExpanded(e => !e);

  if (!expanded) {
    return (
      <StepRow key={toggleRow.key} status={toggleRow.status} label={toggleRow.label} chevronOpen={false} onToggle={toggle} />
    );
  }

  return (
    <div className={styles.genProgress}>
      {rows.map(r => r.key === toggleRow.key
        ? <StepRow key={r.key} status={r.status} label={r.label} chevronOpen={true} onToggle={toggle} />
        : <StepRow key={r.key} status={r.status} label={r.label} />
      )}
    </div>
  );
}

// Shared timer-driven checklist: for any staged loader with no real backend
// sub-progress to key off (SetupStepper, IntakeStepper below), advances
// through `labels` on a fixed interval, marking passed stages done and the
// current one active — same StepList/StepRow look as the backend-driven
// GenerationProgress above, so every loader in this file matches.
function TimedStepList({ labels, intervalMs }: { labels: string[]; intervalMs: number }) {
  const [stageIndex, setStageIndex] = useState(0);

  useEffect(() => {
    setStageIndex(0);
    const id = setInterval(() => {
      setStageIndex(i => (i < labels.length - 1 ? i + 1 : i));
    }, intervalMs);
    return () => clearInterval(id);
    // labels/intervalMs are static per call site (module-level constants),
    // not expected to change across renders of the same stepper instance.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const rows: StepRowData[] = labels.map((label, i) => ({
    key: label,
    status: i < stageIndex ? 'done' : i === stageIndex ? 'active' : 'pending',
    label,
  }));

  return <StepList rows={rows} />;
}

// Setup-gap checklist for the "Setting up your task…" screen (isSettingUp in
// the main render below). The create -> PUT -> forced-send sequence in
// handleBriefConfirm reports no real sub-progress of its own (just an
// awaited start and finish, nothing in between), so unlike GenerationProgress
// there is no backend signal to drive stages from; this always runs the
// timed auto-advance instead.
const SETUP_STAGE_LABELS = [
  'Understanding your request',
  'Gathering context',
  'Preparing your workspace',
  'Finalizing',
];
const SETUP_STAGE_INTERVAL_MS = 1400;

function SetupStepper() {
  return <TimedStepList labels={SETUP_STAGE_LABELS} intervalMs={SETUP_STAGE_INTERVAL_MS} />;
}

// Classify-the-prompt checklist for the "Understanding your request…" screen
// (isIntakeLoading in the main render below) — the POST /api/tasks/intake
// call behind it is a single request/response with no intermediate progress
// either, so this is timed auto-advance too, same as SetupStepper.
const INTAKE_STAGE_LABELS = [
  'Understanding your request',
  'Analyzing your prompt',
  'Almost there',
];
const INTAKE_STAGE_INTERVAL_MS = 1400;

function IntakeStepper() {
  return <TimedStepList labels={INTAKE_STAGE_LABELS} intervalMs={INTAKE_STAGE_INTERVAL_MS} />;
}

export default function MainContent({ onNewChat }: { onNewChat?: () => void }) {
  const searchParams = useSearchParams();
  const nextRouter = useNextRouter();
  const [selectedAgent, setSelectedAgent] = useState<string | null>(null);
  const [selectedModel, setSelectedModel] = useState<string>('');
  type ProviderInfo = {
    providers: { id: string; display_name: string; configured: boolean; model: string }[];
    mode: string;
    advanced_pin: string | null;
    default_provider: string | null;
  };
  const [providerInfo, setProviderInfo] = useState<ProviderInfo | null>(null);
  const [providerNote, setProviderNote] = useState<string>('');
  // Truncation detail for the CURRENTLY streaming message only (from the
  // backend's 'truncated' SSE event) — transient, never persisted. A
  // persisted/reloaded message carries no separate flag: the truncation
  // notice is embedded directly in its content (see TRUNCATION_MARKER
  // below), which is what the banner falls back to after reload.
  type TruncationDetail = { provider: string; model: string; max_tokens: number; output_chars: number };
  const [liveTruncation, setLiveTruncation] = useState<TruncationDetail | null>(null);
  // Staged generation-progress stepper, driven by real backend 'stage'/
  // 'status' SSE events plus the client-side "first token" milestone — see
  // GenerationProgress below. genStage is null outside an active generation.
  const [genStage, setGenStage] = useState<string | null>(null);
  const [kbWaitText, setKbWaitText] = useState<string | null>(null);
  const [kbWaitSeen, setKbWaitSeen] = useState(false);
  const [promptText, setPromptText] = useState('');
  const [showBanner, setShowBanner] = useState(false);
  const [showQuestionnaire, setShowQuestionnaire] = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [threadBrief, setThreadBrief] = useState<TaskBrief | null>(null);
  const [qaAnswers, setQaAnswers] = useState<Array<{ question: string; answer: string }>>([]);
  // Step-2 task-intake state (driven by POST /api/tasks/intake) — additive,
  // alongside the legacy AgentQuestionnaire state above, which stays in
  // place but is no longer rendered (see the .onboardingForms block below).
  const [intakePhase, setIntakePhase] = useState<'idle' | 'questions' | 'brief' | 'research' | 'confirmed'>('idle');
  const [isIntakeLoading, setIsIntakeLoading] = useState(false);
  // True only for the one-time create -> PUT -> send gap right after
  // Continue is clicked, until handleSubmit's forced re-invoke actually
  // enqueues the real "thinking" entry for generation. Explicit state (not
  // derived from intakePhase/messages) because intakePhase stays 'confirmed'
  // for the rest of the task's lifetime, and messages already contains the
  // user's prompt + card-selection bubbles by this point (the whole flow now
  // lives inside the chat), so neither on its own still singles out this gap.
  const [isSettingUp, setIsSettingUp] = useState(false);
  const [intakePayload, setIntakePayload] = useState<TaskIntakeData | null>(null);
  const [intakeAnswers, setIntakeAnswers] = useState<Record<string, TaskIntakeAnswer> | null>(null);
  const [confirmedBrief, setConfirmedBrief] = useState<TaskBrief | null>(null);
  // Lifted out of ResearchDirection (which unmounts/remounts every time
  // intakePhase leaves/re-enters 'research') so Back and a failed project
  // save both restore the user's headings/sub-headers/custom topics/market
  // instead of resetting the screen.
  const [researchSelection, setResearchSelection] = useState<ResearchSelection | null>(null);
  const [classifiedAgent, setClassifiedAgent] = useState<string | null>(null);
  // Set right before a forced re-invoke of handleSubmit() after a Task Brief
  // is confirmed, so that one call skips the intake intercept and the
  // lazy-create gate and sends straight into the already-created project.
  const forcedProjectIdRef = useRef<string | null>(null);
  // Stashes the original prompt right before the intake intercept clears
  // promptText (see setPromptText('') below) — by the time handleBriefConfirm
  // runs its forced re-invoke of handleSubmit(), promptText is long empty
  // (the user has spent the whole questions/brief flow since), so handleSubmit
  // must be handed this ref's value explicitly rather than reading the stale
  // promptText state (was the cause of the "Setting up your task…" screen
  // getting stuck forever: handleSubmit's own `if (!prompt.trim()) return`
  // guard fired on the empty string before ever enqueueing a message).
  const pendingTaskPromptRef = useRef<string>('');
  // Synchronous re-entry guard: intakePhase alone isn't enough, since
  // setIntakePhase() doesn't commit until after the in-flight fetch awaits —
  // a rapid double-send (double-click, Enter held) would otherwise read
  // intakePhase==='idle' twice and fire two POST /api/tasks/intake calls.
  const intakeInFlightRef = useRef(false);
  const [competitors, setCompetitors] = useState<CompetitorDetail[]>([]);
  const [brandKit, setBrandKit] = useState<BrandKit>({});
  const [userContext, setUserContext] = useState('');
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [downloadingPdfIdx, setDownloadingPdfIdx] = useState<number | null>(null);
  const [pdfErrorIdx, setPdfErrorIdx] = useState<number | null>(null);
  const [copiedMsgIdx, setCopiedMsgIdx] = useState<number | null>(null);
  const [reportsByMessageId, setReportsByMessageId] = useState<Record<string, ReportInfo>>({});
  const [downloadingDocxIdx, setDownloadingDocxIdx] = useState<number | null>(null);
  const [docxErrorIdx, setDocxErrorIdx] = useState<number | null>(null);
  const [downloadingPptxIdx, setDownloadingPptxIdx] = useState<number | null>(null);
  const [pptxErrorIdx, setPptxErrorIdx] = useState<number | null>(null);
  const [sharingReportIdx, setSharingReportIdx] = useState<number | null>(null);
  const [shareCopiedIdx, setShareCopiedIdx] = useState<number | null>(null);
  const [shareErrorIdx, setShareErrorIdx] = useState<number | null>(null);
  const [editingReportId, setEditingReportId] = useState<string | null>(null);
  const [view, setView] = useState<'builder' | 'files' | 'projects' | 'agents' | 'workflow' | 'connectors'>('builder');
  const { templates: pptxTemplates } = useTemplates();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const apiBase = process.env.NEXT_PUBLIC_API_URL;
  const authToken = typeof window !== 'undefined' ? (localStorage.getItem('access_token') ?? undefined) : undefined;

  // Fetch which providers are actually configured + the model each would run,
  // so the selector reflects reality instead of a hardcoded list.
  useEffect(() => {
    (async () => {
      try {
        const headers: Record<string, string> = {};
        if (authToken) headers['Authorization'] = `Bearer ${authToken}`;
        const res = await fetch(`${apiBase}/api/chat/providers`, { headers });
        if (res.ok) setProviderInfo(await res.json());
      } catch {
        /* non-blocking: selector falls back to "Loading…" until this succeeds */
      }
    })();
  }, [apiBase, authToken]);

  // Keep the selection on a provider that actually has a key. Corrects the
  // empty initial value AND a saved project provider that is unavailable,
  // falling back to the server's default and saying so — never silently.
  useEffect(() => {
    if (!providerInfo) return;
    const configured = new Set(providerInfo.providers.filter(p => p.configured).map(p => p.id));
    if (selectedModel && configured.has(selectedModel)) {
      setProviderNote('');
      return;
    }
    const fallback = providerInfo.default_provider;
    if (fallback) {
      const label = providerInfo.providers.find(p => p.id === fallback)?.display_name || fallback;
      if (selectedModel) {
        const prev = providerInfo.providers.find(p => p.id === selectedModel)?.display_name || selectedModel;
        setProviderNote(`"${prev}" has no key configured — using ${label} instead.`);
      }
      setSelectedModel(fallback);
    }
  }, [providerInfo, selectedModel]);

  const latestAssistantIdx = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === 'assistant') return i;
    }
    return -1;
  }, [messages]);

  const handleDownloadPdf = async (idx: number, messageId: string) => {
    const reportInfo = reportsByMessageId[messageId];
    if (!reportInfo) return;
    try {
      setPdfErrorIdx(null);
      setDownloadingPdfIdx(idx);

      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const res = await fetch(`${apiBase}/api/reports/${reportInfo.id}/export/pdf`, { headers });
      if (!res.ok) {
        throw new Error(`Server error (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const currentBrandId = activeProject?.brand_config_id || savedBrandId;
      const brandName = ((currentBrandId && brandsMap[currentBrandId]) || activeProject?.title || 'Brand').trim();
      const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
      const fileName = `${sanitize(brandName)}_${sanitize(reportInfo.agent_type || reportInfo.title || 'Report')}.pdf`;

      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export PDF:', err);
      setPdfErrorIdx(idx);
      setTimeout(() => setPdfErrorIdx(null), 4000);
    } finally {
      setDownloadingPdfIdx(null);
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
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
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

      const apiBase = process.env.NEXT_PUBLIC_API_URL;
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

  const handleDownloadPptx = async (idx: number, messageId: string, templateId?: string) => {
    const reportInfo = reportsByMessageId[messageId];
    if (!reportInfo) return;
    try {
      setPptxErrorIdx(null);
      setDownloadingPptxIdx(idx);

      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const exportUrl = `${apiBase}/api/reports/${reportInfo.id}/export/pptx${templateId ? `?template_id=${encodeURIComponent(templateId)}` : ''}`;
      const res = await fetch(exportUrl, { headers });
      if (!res.ok) {
        throw new Error(`Server error (${res.status})`);
      }
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const currentBrandId = activeProject?.brand_config_id || savedBrandId;
      const brandName = ((currentBrandId && brandsMap[currentBrandId]) || activeProject?.title || 'Brand').trim();
      const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
      const fileName = `${sanitize(brandName)}_${sanitize(reportInfo.agent_type || reportInfo.title || 'Report')}.pptx`;

      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export PPTX:', err);
      setPptxErrorIdx(idx);
      setTimeout(() => setPptxErrorIdx(null), 4000);
    } finally {
      setDownloadingPptxIdx(null);
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

      const apiBase = process.env.NEXT_PUBLIC_API_URL;
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
  const [prefilledOnboarding, setPrefilledOnboarding] = useState<{ competitors: boolean; brandKit: boolean }>({ competitors: false, brandKit: false });
  const dropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
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
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
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
    // Capture the params once at mount — do not re-read on re-renders.
    const projectParam = searchParams.get('project');
    const isFreshTask = searchParams.get('new') === '1';
    const brandParam = searchParams.get('brand');

    const init = async () => {
      // Loads brandsMap/brandsList/projectsList (so the header can show the
      // brand) and, as a side effect, may auto-reattach activeProject to an
      // existing project/brand for this user (finding-3b/finding-5). The
      // fresh-task branch below runs AFTER this and overrides activeProject
      // with the '' lazy-create sentinel, so that auto-reattach never wins
      // for this entry path.
      await loadProjectsAndBrands();
      if (isFreshTask) {
        const freshBrandId = brandParam || (typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null);
        if (freshBrandId) {
          if (typeof window !== 'undefined') {
            localStorage.setItem('brand_config_id', freshBrandId);
          }
          setActiveProject({ id: '', title: '', brand_config_id: freshBrandId });
        }
        setMessages([]);
        setThreadBrief(null);
        setIntakePhase('idle');
        // Same pending-draft pickup as the ?project= path below.
        const pendingMessage = typeof window !== 'undefined' ? sessionStorage.getItem('pending_chat_message') : null;
        if (pendingMessage) {
          sessionStorage.removeItem('pending_chat_message');
          setPromptText(pendingMessage);
        }
        // Clear the params so a refresh doesn't re-run the fresh-task reset.
        nextRouter.replace('/build');
      } else if (projectParam) {
        await loadProjectById(projectParam);
        // A draft typed on the project details page's "new chat" field, if any —
        // pre-fills the input so the onboarding form is still reviewed before send.
        const pendingMessage = typeof window !== 'undefined' ? sessionStorage.getItem('pending_chat_message') : null;
        if (pendingMessage) {
          sessionStorage.removeItem('pending_chat_message');
          setPromptText(pendingMessage);
        }
        // Clear the param so a refresh doesn't force-reload the same chat.
        nextRouter.replace('/build');
      }
    };
    init();

    const handleProjectChanged = () => {
      loadProjectsAndBrands();
    };
    window.addEventListener('projectChanged', handleProjectChanged);
    return () => window.removeEventListener('projectChanged', handleProjectChanged);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);



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
    setThreadBrief(null);
    setPromptText('');
    setUserContext('');
    setAttachedFiles([]);
    setQaAnswers([]);
    setCompetitors([]);
    setBrandKit({});
    setPrefilledOnboarding({ competitors: false, brandKit: false });

    // Pre-fill competitor list and brand kit from onboarding data for this brand
    const currentBrandIdForPrefill = activeProject?.brand_config_id || savedBrandId;
    if (currentBrandIdForPrefill) {
      const brand = brandsList.find((b: any) => b.id === currentBrandIdForPrefill);
      if (brand?.competitors) {
        try {
          const onboardingComps = JSON.parse(brand.competitors) as Array<{ name?: string; url?: string; website_url?: string }>;
          const mapped = onboardingComps
            .filter((c) => c && typeof c.name === 'string' && c.name.trim())
            .map((c) => ({ brand_name: c.name!.trim(), website_url: c.url || c.website_url || '', social_media: undefined }));
          if (mapped.length > 0) {
            setCompetitors(mapped);
            setPrefilledOnboarding(prev => ({ ...prev, competitors: true }));
          }
        } catch {}
      }
      const projWithKit = projectsList.find((p: any) => p.brand_config_id === currentBrandIdForPrefill && p.brand_kit);
      if (projWithKit?.brand_kit) {
        setBrandKit(projWithKit.brand_kit);
        setPrefilledOnboarding(prev => ({ ...prev, brandKit: true }));
      }
    }

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
    setThreadBrief(null);
    setQaAnswers([]);
    setCompetitors([]);
    setBrandKit({});
    setPrefilledOnboarding({ competitors: false, brandKit: false });
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
    setThreadBrief(null);
    setGenStage(null);
    setKbWaitText(null);
    setKbWaitSeen(false);
    setQaAnswers([]);
    setCompetitors([]);
    setBrandKit({});
    setPrefilledOnboarding({ competitors: false, brandKit: false });
    setActiveProject(null);
    setIntakePhase('idle');
    setIntakePayload(null);
    setIntakeAnswers(null);
    setConfirmedBrief(null);
    setResearchSelection(null);
    intakeInFlightRef.current = false;
    forcedProjectIdRef.current = null;
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

  const handleBriefConfirm = async (brief: TaskBrief, researchSelection: ResearchSelection) => {
    // Clicking Continue both removes the card (isCardOpen goes false the
    // instant intakePhase leaves 'questions'/'brief') and posts the user's
    // own one-line summary of what they picked, right-aligned, in its place
    // — same chat-bubble treatment as a typed message.
    setIntakePhase('confirmed');
    setIsSettingUp(true);
    setMessages(prev => [...prev, { role: 'user', content: buildSelectionSummaryLine(brief) }]);
    let sent = false;
    try {

      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const activeBrandId = (activeProject?.brand_config_id && activeProject.brand_config_id !== '')
        ? activeProject.brand_config_id
        : (savedBrandId || (brandsList.length > 0 ? brandsList[0].id : (projectsList.length > 0 ? projectsList[0].brand_config_id : null)));

      if (!activeBrandId) {
        throw new Error('No active brand to create the task project under');
      }

      const resolvedAgentType = classifiedAgent || selectedAgent || 'StratAI';

      // Mirrors the existing lazy-create body in handleSubmit exactly,
      // overriding title/agent_type with the classified result.
      const createRes = await fetch(`${apiBase}/api/projects/`, {
        method: 'POST',
        headers,
        body: JSON.stringify({
          title: brief.task || 'New task',
          agent_type: resolvedAgentType,
          brand_config_id: activeBrandId,
          llm_provider: selectedModel,
          competitor_details: (() => {
            const filled = competitors.filter((c) => c.brand_name.trim());
            return filled.length > 0 ? filled : null;
          })(),
          brand_kit: (() => {
            const hasBrandKit = brandKit.logo_url || (brandKit.colors && Object.values(brandKit.colors).some(Boolean));
            return hasBrandKit ? brandKit : null;
          })(),
        }),
      });
      if (!createRes.ok) throw new Error(`Failed to create task project (${createRes.status})`);
      const newP = await createRes.json();

      // POST /api/projects/'s "reuse an existing empty project" branch drops
      // questionnaire_answers, so persist the confirmed brief explicitly —
      // the brief object stays exactly as it was; research_direction is a
      // sibling key added alongside it, never folded into/replacing it.
      await fetch(`${apiBase}/api/projects/${newP.id}`, {
        method: 'PUT',
        headers,
        body: JSON.stringify({ questionnaire_answers: JSON.stringify({ ...brief, research_direction: researchSelection }) }),
      });

      setActiveProject({ id: newP.id, title: newP.title, brand_config_id: newP.brand_config_id ?? activeBrandId });
      setSelectedAgent(resolvedAgentType);
      setThreadBrief(brief);
      if (typeof window !== 'undefined') {
        localStorage.setItem('brand_config_id', activeBrandId);
      }

      // promptText was already cleared back when the Step-2 intercept first
      // ran (setPromptText('') in handleSubmit) — pendingTaskPromptRef is
      // what still holds the original text, so hand it to this forced
      // re-invoke explicitly instead of letting handleSubmit read the
      // (by-now-empty) promptText state, straight into newP.id.
      forcedProjectIdRef.current = newP.id;
      sent = await handleSubmit(pendingTaskPromptRef.current);
    } catch (err) {
      console.error('Task brief confirm failed:', err);
    } finally {
      // The success path already turned isSettingUp off inside handleSubmit
      // itself, right as it enqueues the real "thinking" entry — this is a
      // defensive reset for every other case, so the inline setup stepper
      // never hangs even if a failure surfaces after the last await.
      setIsSettingUp(false);
      // If handleSubmit never got far enough to enqueue that "thinking" entry
      // (sent===false, whether from a thrown error above or handleSubmit's
      // own early-return guard), intakePhase would otherwise be stuck on
      // 'confirmed' with no card and no generation in progress; falling back
      // to the research card here, in a finally, clears it even then. Falls
      // back to 'research' (not 'brief') so the user doesn't have to redo
      // their heading/sub-header/custom-topic/market picks — researchSelection
      // is lifted into this component's own state precisely so it survives
      // this remount, restored via ResearchDirection's initialSelection prop.
      if (!sent) {
        setIntakePhase('research');
      }
    }
  };

  const loadProjectById = async (projectId: string) => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
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
        try {
          setThreadBrief(proj.questionnaire_answers ? JSON.parse(proj.questionnaire_answers) as TaskBrief : null);
        } catch {
          setThreadBrief(null);
        }
        const hasCompetitors = Array.isArray(proj.competitor_details) && proj.competitor_details.length > 0;
        const hasBrandKit = proj.brand_kit && typeof proj.brand_kit === 'object' &&
          (proj.brand_kit.logo_url || proj.brand_kit.colors);
        setCompetitors(hasCompetitors ? proj.competitor_details : []);
        setBrandKit(hasBrandKit ? proj.brand_kit : {});
        setPrefilledOnboarding({ competitors: false, brandKit: false });

        // When the form will show (no messages yet) and data is missing, fetch onboarding defaults
        const willShowForm = !proj.messages || proj.messages.length === 0;
        if (willShowForm && (!hasCompetitors || !hasBrandKit) && proj.brand_config_id) {
          try {
            const detRes = await fetch(`${apiBase}/api/projects/${proj.id}/details`, { headers });
            if (detRes.ok) {
              const details = await detRes.json();
              if (!hasCompetitors && Array.isArray(details.competitors_selected) && details.competitors_selected.length > 0) {
                const mapped = details.competitors_selected.map((c: any) => ({
                  brand_name: c.name || '',
                  website_url: c.website_url || '',
                  social_media: undefined,
                }));
                setCompetitors(mapped);
                setPrefilledOnboarding(prev => ({ ...prev, competitors: true }));
              }
              if (!hasBrandKit && details.brand && (details.brand.logo_url || details.brand.colors)) {
                setBrandKit({ logo_url: details.brand.logo_url ?? null, colors: details.brand.colors ?? null });
                setPrefilledOnboarding(prev => ({ ...prev, brandKit: true }));
              }
            }
          } catch {}
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

  // Submit message → call backend + stream response. Returns whether the
  // first user/thinking message actually got enqueued (false on every early
  // return below) — handleBriefConfirm's forced re-invoke uses this to know
  // whether it's safe to leave intakePhase==='confirmed' (isChatting will
  // flip true) or whether it must reset out of the "Setting up…" screen
  // itself instead of leaving it stuck.
  const handleSubmit = async (overridePrompt?: string): Promise<boolean> => {
    const effectivePrompt = overridePrompt ?? promptText;
    if (!effectivePrompt.trim()) return false;

    // Consumed once per call: set by handleBriefConfirm right before it
    // re-invokes handleSubmit() so this one call skips the intake intercept
    // and the lazy-create gate below, sending straight into the project
    // handleBriefConfirm already created.
    const forced = forcedProjectIdRef.current;
    forcedProjectIdRef.current = null;

    // Whether the user's prompt is already sitting in the chat as a
    // right-aligned bubble — true for the forced re-invoke (handleBriefConfirm
    // posted its own selection-summary bubble when Continue was clicked) and,
    // as of the block right below, for the intake intercept itself (it now
    // posts the raw prompt immediately, switching straight to the chat layout
    // instead of a blank-page loader first). The later normal-send step's
    // setMessages(...) must not add a second copy when this is true — but it
    // is NOT what decides whether `history` (below) needs its own manual
    // append; see the comment at `history` for why those are different
    // questions (one is about committed state, the other about this
    // specific closure's possibly-stale `messages` snapshot).
    let userBubbleAlreadyShown = !!forced;

    // Step-2 task intake: on the very first turn of a fresh task, classify
    // the prompt + fetch checkpoints before sending anything, and surface
    // the question/brief cards instead of sending. intakePhase !== 'idle'
    // guards re-entry so this only ever fires once per task. NO send, NO
    // project creation, NO persistence happens here — that's phase 7d.
    if (!forced && messages.length === 0 && intakePhase === 'idle' && effectivePrompt.trim()) {
      // Synchronous guard — intakePhase is React state and doesn't commit
      // until after the await below, so a rapid double-send (double-click,
      // Enter held down) would otherwise still read intakePhase==='idle'
      // twice and fire two POST /api/tasks/intake calls. The ref updates
      // immediately, before any await, so the second call sees it and bails.
      if (intakeInFlightRef.current) {
        return false;
      }
      intakeInFlightRef.current = true;
      setIsIntakeLoading(true);
      // Stashed BEFORE clearing, so the forced handleSubmit() re-invoke that
      // follows the questions/brief flow (potentially minutes later) can
      // still send the user's original text — see pendingTaskPromptRef.
      pendingTaskPromptRef.current = effectivePrompt;
      // Switch straight to the chat layout right now, like ChatGPT/Claude —
      // the user's prompt becomes a right-aligned bubble immediately; the
      // classify step then renders as a left-aligned IntakeStepper entry
      // below it (see the isChatting branch in the render), never a
      // full-page loader.
      setMessages(prev => [...prev, { role: 'user', content: effectivePrompt.trim() }]);
      userBubbleAlreadyShown = true;
      setPromptText('');

      const savedBrandIdForIntake = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const activeBrandId = (activeProject?.brand_config_id && activeProject.brand_config_id !== '')
        ? activeProject.brand_config_id
        : (savedBrandIdForIntake || (brandsList.length > 0 ? brandsList[0].id : (projectsList.length > 0 ? projectsList[0].brand_config_id : null)));

      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL;
        const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
        const headers: Record<string, string> = { 'Content-Type': 'application/json' };
        if (token) headers['Authorization'] = `Bearer ${token}`;

        const body = activeProject?.id
          ? { project_id: activeProject.id, prompt: effectivePrompt }
          : { brand_config_id: activeBrandId, prompt: effectivePrompt };

        const res = await fetch(`${apiBase}/api/tasks/intake`, {
          method: 'POST',
          headers,
          body: JSON.stringify(body),
        });

        if (res.ok) {
          const payload: TaskIntakeData = await res.json();
          setIntakePayload(payload);
          setClassifiedAgent(payload.agent_type ?? null);
          if (payload.questions?.length) {
            setIntakePhase('questions');
          } else {
            setConfirmedBrief(buildTaskBrief(payload, {}));
            setIntakePhase('brief');
          }
          return false; // do NOT proceed to send
        }
        console.error('Task intake failed:', res.status);
      } catch (err) {
        console.error('Task intake request failed, falling back to normal send:', err);
      } finally {
        intakeInFlightRef.current = false;
        setIsIntakeLoading(false);
      }
      // Any failure above falls through to the normal send below — intake
      // must never block the user from just sending their message.
    }
    let baseContent = effectivePrompt.trim();
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
    setLiveTruncation(null);

    // Build conversation history (only user + assistant, skip thinking/error).
    // `messages` here is a closure snapshot, fixed as of whichever render
    // created THIS handleSubmit instance — it reflects a setMessages call
    // from an EARLIER, already-committed render, but never one made earlier
    // in this SAME call (the local binding can't change mid-call). Only the
    // forced path guarantees that gap: handleBriefConfirm (a separate, later
    // invocation, after real render(s) since the questions/brief flow)
    // already pushed the original prompt as a bubble, so `messages` here
    // already ends with that exact turn — and apiUserContent, derived from
    // the same pendingTaskPromptRef.current text, would duplicate it if
    // appended again. (The selection-summary bubble handleBriefConfirm posts
    // alongside that is a pure UI recap — it was never meant to re-enter the
    // LLM's history as its own turn, forced or not.) The plain, non-forced
    // path — including intake falling through to a normal send within THIS
    // SAME call — has no such guarantee, so it must still append, exactly as
    // before this file's intake-triggered chat layout existed.
    const history = (forced ? messages : [...messages, { role: 'user', content: apiUserContent }])
      .filter(m => m.role === 'user' || m.role === 'assistant')
      .map(m => ({ role: m.role, content: m.content }));

    // Get system prompt for selected agent
    const systemPrompt = selectedAgent
      ? (agentPrompts[selectedAgent] || `You are a helpful ${selectedAgent} agent. Help the user with their request.`)
      : 'You are StratAI, a helpful AI strategy assistant. Help the user with their business strategy, marketing, sales, and growth questions. Be concise, actionable, and data-driven.';

    // Exits the inline "Setting up your task…" stepper (if it was showing)
    // the instant the real generation entry is about to appear, so the chat
    // flows straight from setup into GenerationProgress with no layout jump.
    setIsSettingUp(false);
    setMessages(prev => userBubbleAlreadyShown ? [...prev, thinking] : [...prev, userMsg, thinking]);
    setPromptText('');
    setUserContext('');
    setAttachedFiles([]);
    setQaAnswers([]);
    setShowBanner(false);
    setShowQuestionnaire(false);
    setGenStage('preparing');
    setKbWaitText(null);
    setKbWaitSeen(false);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      const headers: Record<string, string> = { 'Content-Type': 'application/json' };
      if (token) headers['Authorization'] = `Bearer ${token}`;

      let targetProjectId = forced ?? activeProject?.id;
      const savedBrandId = typeof window !== 'undefined' ? localStorage.getItem('brand_config_id') : null;
      const activeBrandId = (activeProject?.brand_config_id && activeProject.brand_config_id !== '')
        ? activeProject.brand_config_id
        : (savedBrandId || (brandsList.length > 0 ? brandsList[0].id : (projectsList.length > 0 ? projectsList[0].brand_config_id : null)));

      if (!forced && (!targetProjectId || targetProjectId === '')) {
        if (activeBrandId) {
          const createRes = await fetch(`${apiBase}/api/projects/`, {
            method: 'POST',
            headers,
            body: JSON.stringify({
              title: selectedAgent || 'New Strategy Chat',
              agent_type: selectedAgent || 'StratAI',
              brand_config_id: activeBrandId,
              llm_provider: selectedModel,
              competitor_details: (() => {
                const filled = competitors.filter((c) => c.brand_name.trim());
                return filled.length > 0 ? filled : null;
              })(),
              brand_kit: (() => {
                const hasBrandKit = brandKit.logo_url || (brandKit.colors && Object.values(brandKit.colors).some(Boolean));
                return hasBrandKit ? brandKit : null;
              })(),
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
        return true;
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
          return true;
        }
        setMessages(prev => [
          ...prev.filter(m => m.role !== 'thinking'),
          { role: 'error', content: `Server error (${res.status}). Make sure the backend is running on port 8000.` },
        ]);
        return true;
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
              // First token received is the client-side milestone into the
              // 'generating' stage — the report text itself takes over from
              // here, so the stepper (mounted on the 'thinking' message) is
              // about to be replaced anyway.
              setGenStage('generating');
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
            } else if (payload.type === 'status') {
              // Research-pipeline wait can now run for several minutes — the
              // stepper (GenerationProgress) shows this now, not the thinking
              // message's own content.
              setGenStage('kb_wait');
              setKbWaitText(payload.content);
              setKbWaitSeen(true);
            } else if (payload.type === 'stage') {
              // Real backend-emitted stage boundary: 'retrieving' | 'composing'
              // | 'generating'.
              setGenStage(payload.stage);
            } else if (payload.type === 'error') {
              setGenStage(null);
              if (!assistantText) {
                setActiveProject(null);
              }
              setMessages(prev => [
                ...prev.filter(m => m.role !== 'thinking'),
                { role: 'error', content: payload.content },
              ]);
              return true;
            } else if (payload.type === 'truncated') {
              // The in-report notice text already arrived as a preceding
              // 'token' event (part of assistantText) — this event only adds
              // the structured detail (exact model/token-limit/output size)
              // for a sharper live banner than parsing that prose would give.
              setLiveTruncation(payload.content);
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
      setGenStage(null);
    } catch (err) {
      setGenStage(null);
      setActiveProject(null);
      setMessages(prev => [
        ...prev.filter(m => m.role !== 'thinking'),
        { role: 'error', content: 'Could not connect to backend. Make sure `uvicorn main:app --reload` is running on port 8000.' },
      ]);
    }

    return true;
  };

  const isChatting = messages.length > 0;
  const isCardOpen = intakePhase === 'questions' || intakePhase === 'brief' || intakePhase === 'research';
  // Must also exclude selectedAgent — the bottom ChatInput's gate below uses
  // this standalone (not nested after a selectedAgent check the way the
  // welcome-heading/grid ternary is), so without !selectedAgent here the
  // agent-detail screen would read as "home" and the input would stay
  // hidden there, reproducing the exact bug this gate is meant to fix.
  const isHome = !selectedAgent && !isCardOpen && !isChatting && !isIntakeLoading;

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
        {latestAssistantIdx !== -1 && messages[latestAssistantIdx].id && reportsByMessageId[messages[latestAssistantIdx].id!] && (
          <button
            className={styles.downloadTopBarBtn}
            onClick={() => handleDownloadPdf(latestAssistantIdx, messages[latestAssistantIdx].id!)}
            disabled={downloadingPdfIdx !== null}
            title="Download latest strategy report as PDF"
          >
            {downloadingPdfIdx === latestAssistantIdx ? (
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
              {threadBrief && <TaskBriefBar brief={threadBrief} />}
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
                      <GenerationProgress stage={genStage} kbWaitText={kbWaitText} kbWaitSeen={kbWaitSeen} />
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
                          <ExportMenu
                            buttonClassName={`${styles.reportActionBtn} ${styles.reportDownloadBtn}`}
                            formats={[
                              ...(msg.id && reportsByMessageId[msg.id] ? [{
                                id: 'pdf',
                                label: 'PDF',
                                extension: '.pdf',
                                chip: 'PDF',
                                onSelect: () => handleDownloadPdf(i, msg.id!),
                                loading: downloadingPdfIdx === i,
                                error: pdfErrorIdx === i,
                              }] : []),
                              ...(msg.id && reportsByMessageId[msg.id] ? [{
                                id: 'docx',
                                label: 'Word',
                                extension: '.docx',
                                chip: 'DOC',
                                onSelect: () => handleDownloadDocx(i, msg.id!),
                                loading: downloadingDocxIdx === i,
                                error: docxErrorIdx === i,
                              }] : []),
                              ...(msg.id && reportsByMessageId[msg.id] ? [{
                                id: 'pptx',
                                label: 'PowerPoint',
                                extension: '.pptx',
                                chip: 'PPT',
                                onSelect: () => handleDownloadPptx(i, msg.id!),
                                onSelectTemplate: (templateId: string) => handleDownloadPptx(i, msg.id!, templateId),
                                templates: pptxTemplates,
                                loading: downloadingPptxIdx === i,
                                error: pptxErrorIdx === i,
                              }] : []),
                            ]}
                          />
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
                          {msg.id && reportsByMessageId[msg.id] && (
                            <button
                              type="button"
                              className={styles.reportActionBtn}
                              onClick={() => setEditingReportId(reportsByMessageId[msg.id!].id)}
                              title="Edit this report's sections"
                            >
                              <span>✏️ Edit Sections</span>
                            </button>
                          )}
                        </div>
                      </div>

                      {isTruncatedContent(msg.content) && (
                        <div
                          role="alert"
                          style={{
                            display: 'flex', alignItems: 'center', gap: '8px',
                            background: '#fee2e2', color: '#b91c1c', border: '1px solid #fca5a5',
                            borderRadius: '8px', padding: '8px 12px', margin: '0 0 12px',
                            fontSize: '13px', fontWeight: 600,
                          }}
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#b91c1c" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                            <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                            <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
                          </svg>
                          <span>
                            {i === latestAssistantIdx && liveTruncation
                              ? `Truncated — ${liveTruncation.provider}/${liveTruncation.model} hit its token limit (max_tokens=${liveTruncation.max_tokens}) after ${liveTruncation.output_chars.toLocaleString()} characters.`
                              : 'This report was cut off before completion — see the notice below.'}
                          </span>
                        </div>
                      )}

                      {msg.id && reportsByMessageId[msg.id] && editingReportId === reportsByMessageId[msg.id].id ? (
                        <SectionEditor
                          reportId={editingReportId}
                          onClose={() => setEditingReportId(null)}
                        />
                      ) : (
                        <div id={`report-markdown-${i}`} className={styles.assistantTextMarkdown}>
                          <ReportRenderer content={msg.content} />
                        </div>
                      )}

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
                          onClick={() => msg.id && handleDownloadPdf(i, msg.id)}
                          disabled={downloadingPdfIdx === i || !msg.id || !reportsByMessageId[msg.id]}
                          title="Download full report as PDF"
                        >
                          {downloadingPdfIdx === i ? (
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
              {/* ── Classify step: left-aligned agent "thinking" entry, like
                     ChatGPT/Claude — never a full-page loader. ───────────── */}
              {isIntakeLoading && (
                <div className={styles.thinkingWrapper}>
                  <div className={styles.thinkingIcon}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <defs><linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#a78bfa"/><stop offset="100%" stopColor="#d4a843"/></linearGradient></defs>
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <div className={styles.thinkingBubble}>
                    <IntakeStepper />
                  </div>
                </div>
              )}
              {/* ── Step-2 task-intake card: left-aligned agent message, next
                     to the icon like every other agent entry — stays a wide
                     card, just not its own page. ───────────────────────── */}
              {isCardOpen && (
                <div className={styles.thinkingWrapper}>
                  <div className={styles.thinkingIcon}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <defs><linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#a78bfa"/><stop offset="100%" stopColor="#d4a843"/></linearGradient></defs>
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <div className={styles.agentCardContent}>
                    {intakePhase === 'questions' && intakePayload && (
                      <TaskIntakeQuestions
                        intake={intakePayload}
                        onComplete={(answers) => {
                          setIntakeAnswers(answers);
                          setConfirmedBrief(buildTaskBrief(intakePayload, answers));
                          setIntakePhase('brief');
                        }}
                      />
                    )}
                    {intakePhase === 'brief' && confirmedBrief && (
                      <TaskBriefSummary
                        brief={confirmedBrief}
                        onConfirm={(brief) => {
                          // Brief is confirmed (possibly edited via TaskBriefSummary's
                          // own Edit flow) — persist that edit, then collect research
                          // direction before generating.
                          setConfirmedBrief(brief);
                          setIntakePhase('research');
                        }}
                      />
                    )}
                    {intakePhase === 'research' && intakePayload && confirmedBrief && (
                      <ResearchDirection
                        headings={intakePayload.research_headings}
                        preselected={intakePayload.step3_preselected}
                        marketPrefill={intakePayload.research_market_prefill}
                        initialSelection={researchSelection}
                        onBack={() => setIntakePhase('brief')}
                        onComplete={(selection) => {
                          setResearchSelection(selection);
                          handleBriefConfirm(confirmedBrief, selection);
                        }}
                      />
                    )}
                  </div>
                </div>
              )}
              {/* ── Create -> PUT -> send-setup gap right after Continue:
                     left-aligned agent "thinking" entry too, inline. ─────── */}
              {isSettingUp && (
                <div className={styles.thinkingWrapper}>
                  <div className={styles.thinkingIcon}>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <defs><linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="100%"><stop offset="0%" stopColor="#a78bfa"/><stop offset="100%" stopColor="#d4a843"/></linearGradient></defs>
                      <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                    </svg>
                  </div>
                  <div className={styles.thinkingBubble}>
                    <SetupStepper />
                  </div>
                </div>
              )}
              <div style={{ height: '140px', width: '100%', flexShrink: 0 }} />
              <div ref={messagesEndRef} />
            </div>
          ) : selectedAgent && !isCardOpen ? (
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
          ) : isHome ? (
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
                  providers={providerInfo?.providers}
                  advancedPin={providerInfo?.advanced_pin ?? null}
                  providerNote={providerNote}
                  hideUserContext={true}
                />
              </div>
            </div>
          ) : null}

        </div>
        )}
      </div>

      {/* Chat Input Fixed at Bottom */}
      {/* isChatting now turns true the moment intake starts (the user's
          prompt lands in the chat immediately), so it alone can no longer
          stand in for "nothing to hide" the way it used to — isIntakeLoading/
          isCardOpen/isSettingUp must each still suppress this bar directly,
          same as the ChatInput-visibility gate just inside it below. */}
      {view !== 'files' && view !== 'projects' && view !== 'agents' && (selectedAgent !== null || isChatting) && !isSettingUp && !isIntakeLoading && !isCardOpen && (
        <div className={styles.chatContainer}>
          {selectedAgent && messages.length === 0 && !isCardOpen && (
            <div className={styles.onboardingForms}>
              <BrandKitForm
                brandKit={brandKit}
                onChange={(kit) => { setBrandKit(kit); setPrefilledOnboarding(prev => ({ ...prev, brandKit: false })); }}
                apiBase={apiBase}
                authToken={authToken}
              />
              {prefilledOnboarding.brandKit && (
                <p className={styles.prefilledNote}>From your brand setup — edit to override for this report.</p>
              )}
              <div className={styles.formDivider} />
              <CompetitorForm
                competitors={competitors}
                onChange={(comps) => { setCompetitors(comps); setPrefilledOnboarding(prev => ({ ...prev, competitors: false })); }}
              />
              {prefilledOnboarding.competitors && (
                <p className={styles.prefilledNote}>From your brand setup — edit to override for this report.</p>
              )}
              {/* Superseded by the Step-2 task-intake cards (TaskIntakeQuestions /
                  TaskBriefSummary, now rendered centered in the main content area,
                  not here) — handlers and state stay in place, but this legacy
                  card no longer renders. */}
              {SHOW_LEGACY_AGENT_QUESTIONNAIRE && showQuestionnaire && agentQuestions[selectedAgent] && (
                <>
                  <div className={styles.formDivider} />
                  <AgentQuestionnaire
                    questions={agentQuestions[selectedAgent]}
                    onComplete={handleQuestionnaireComplete}
                    onDismiss={handleQuestionnaireDismiss}
                  />
                </>
              )}
            </div>
          )}
          {(!isHome && !isCardOpen && !isIntakeLoading) && (
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
              providers={providerInfo?.providers}
              advancedPin={providerInfo?.advanced_pin ?? null}
              providerNote={providerNote}
              hideUserContext={true}
            />
          )}
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
