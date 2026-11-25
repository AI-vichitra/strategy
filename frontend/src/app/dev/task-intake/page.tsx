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
