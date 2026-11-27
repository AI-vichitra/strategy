'use client';
// DEV PREVIEW — delete before ship
import { useState } from 'react';
import TaskIntakeQuestions, {
  type TaskIntakeAnswer,
  type TaskIntakeData,
} from '@/components/builder/TaskIntakeQuestions';
import TaskBriefSummary from '@/components/builder/TaskBriefSummary';
import { buildTaskBrief, type TaskBrief } from '@/components/builder/taskBrief';

const mock: TaskIntakeData = {
  task: 'Social media calendar',
  group_name: 'Campaigns, Social and Content',
  group_id: 'G3',
  agent_type: 'Content Calendar',
  matched: true,
  checkpoints: [
    { id: 'C1', name: 'Task', scope: 'core', must: true, state: 'found', value: 'Social media calendar', source: 'prompt' },
    { id: 'C4', name: 'Audience and market', scope: 'core', must: false, state: 'prefilled', value: 'CMOs and marketing heads — India (Mumbai, Delhi NCR)', source: 'brand_brief' },
    { id: 'C2', name: 'Objective', scope: 'core', must: true, state: 'missing', value: null, source: null },
    { id: 'C3', name: 'Focus', scope: 'core', must: true, state: 'missing', value: null, source: null },
    { id: 'C5', name: 'Timeline', scope: 'core', must: true, state: 'missing', value: null, source: null },
    // Added for this phase: demonstrates buildTaskBrief's optional_missing ->
    // omitted rule, matching the real backend's always-present C6 checkpoint.
    { id: 'C6', name: 'Mandatories and references', scope: 'core', must: false, state: 'optional_missing', value: null, source: null },
    { id: 'G3.1', name: 'Platforms / channels', scope: 'group', must: true, state: 'missing', value: null, source: null },
  ],
  missing_required: ['C2', 'C3', 'C5', 'G3.1'],
  research_headings: [
    { id: 'market_industry', label: 'Market and Industry', sub_headers: [
      { id: 'market_overview', label: 'Market overview (size, growth, structure, key players)' },
      { id: 'industry_trends', label: 'Industry trends (innovation, technology, business models)' },
      { id: 'regulations_compliance', label: 'Regulations and compliance' },
      { id: 'investment_funding', label: 'Investment and funding activity' },
    ] },
    { id: 'audience', label: 'Audience', sub_headers: [
      { id: 'profile_segments', label: 'Profile and segments' },
      { id: 'behaviour_journey', label: 'Behaviour and journey (discover, compare, decide, buy)' },
      { id: 'needs_pain_points', label: 'Needs, pain points and motivations' },
      { id: 'social_listening', label: 'Social listening and sentiment' },
      { id: 'search_demand', label: 'Search and keyword demand' },
    ] },
    { id: 'competition', label: 'Competition', sub_headers: [
      { id: 'competitor_landscape', label: 'Competitor landscape (positioning, offerings, pricing, strengths, weaknesses)' },
      { id: 'competitor_communication', label: 'Competitor communication (messaging, campaigns, ads)' },
      { id: 'social_content_audit', label: 'Social and content audit' },
      { id: 'global_benchmarks', label: 'Global benchmarks and best practices' },
    ] },
    { id: 'brand', label: 'Brand', sub_headers: [
      { id: 'brand_audit_perception', label: 'Brand audit and perception (website, social, reviews, search, consistency)' },
      { id: 'swot', label: 'SWOT' },
      { id: 'prospect_partner', label: 'Prospect / partner brand research' },
    ] },
    { id: 'culture_trends', label: 'Culture and Trends', sub_headers: [
      { id: 'cultural_moments', label: 'Cultural moments, festivals and key dates' },
      { id: 'platform_trends', label: 'Platform and content trends' },
      { id: 'visual_trends', label: 'Visual and creative trends' },
    ] },
    { id: 'channels_sales', label: 'Channels and Sales', sub_headers: [
      { id: 'channel_media_landscape', label: 'Channel and media landscape (where the audience is, costs, benchmarks)' },
      { id: 'pricing_sales_landscape', label: 'Pricing and sales landscape (distribution, offers, sales drivers)' },
      { id: 'influencer_landscape', label: 'Influencer and creator landscape' },
      { id: 'news_pr_coverage', label: 'News and PR coverage' },
      { id: 'location_onground', label: 'Location and on-ground insights' },
    ] },
  ],
  step3_preselected: ['audience', 'competition', 'culture_trends'],
  research_market_prefill: { global: false, national: 'India', local: ['Mumbai', 'Delhi NCR'] },
  questions: [
    { checkpoint_id: 'C2', text: 'What should it achieve?', options: ['Awareness', 'Leads', 'Sales', 'Launch', 'Funding', 'Retention / loyalty'], multi_select: false, allow_other: true, skippable: true },
    { checkpoint_id: 'C3', text: 'Whole brand, or a specific product/project/offering?', options: ['Whole brand', 'Specific product / project / offering'], multi_select: false, allow_other: true, skippable: true },
    { checkpoint_id: 'C5', text: 'Period, launch date or deadline', options: ['This month', 'Next 3 months', 'This quarter', 'Specific date'], multi_select: false, allow_other: true, skippable: true },
    { checkpoint_id: 'G3.1', text: 'Platforms / channels', options: ['Instagram', 'LinkedIn', 'Facebook', 'YouTube', 'X / Twitter', 'WhatsApp'], multi_select: true, allow_other: true, skippable: true },
  ],
};

export default function TaskIntakeDevPreview() {
  const [answers, setAnswers] = useState<Record<string, TaskIntakeAnswer> | null>(null);
  const [brief, setBrief] = useState<TaskBrief | null>(null);
  const [confirmedBrief, setConfirmedBrief] = useState<TaskBrief | null>(null);

  const handleComplete = (result: Record<string, TaskIntakeAnswer>) => {
    console.log('TaskIntakeQuestions onComplete:', result);
    setAnswers(result);
    setBrief(buildTaskBrief(mock, result));
  };

  const handleConfirm = (finalBrief: TaskBrief) => {
    console.log('TaskBriefSummary onConfirm:', finalBrief);
    setConfirmedBrief(finalBrief);
  };

  return (
    <div style={{ minHeight: '100vh', background: '#FAF8F5', padding: '48px 24px', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 24 }}>
      {!brief && <TaskIntakeQuestions intake={mock} onComplete={handleComplete} />}
      {brief && !confirmedBrief && <TaskBriefSummary brief={brief} onConfirm={handleConfirm} />}
      {confirmedBrief && (
        <pre style={{ maxWidth: 560, width: '100%', background: '#1A1A1A', color: '#F0ECE4', padding: 16, borderRadius: 12, fontSize: 12, overflowX: 'auto' }}>
          {JSON.stringify(confirmedBrief, null, 2)}
        </pre>
      )}
    </div>
  );
}
