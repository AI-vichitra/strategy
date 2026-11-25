// Pure merge helper — no React. Folds a TaskIntakeQuestions answers object
// back together with the original intake (classify+fill+questions) result
// into the final Task Brief shown for confirmation.
//
// Note on the "required" check below: core checkpoints in
// backend/data/task_groups.json carry no "must" field at all (only group
// checkpoints do), so checkpoint_service.py's per-checkpoint `must` comes
// back False for C2/C3/C5 too — only C1 is True. fill_checkpoints' own
// missing_required list sidesteps this with a hardcoded {C1,C2,C3,C5} set;
// this module does the same by treating any core checkpoint other than C4
// as required, rather than trusting `must` for core scope. Group checkpoints
// DO carry a real `must` field, so those are trusted directly.

import type { TaskIntakeData, TaskIntakeAnswer, TaskIntakeCheckpoint } from './TaskIntakeQuestions';

export type BriefSource = 'prompt' | 'brief' | 'brand' | 'you' | 'assumed';

export interface TaskBriefItem {
  id: string;
  name: string;
  value: string;
  source: BriefSource;
}

export interface TaskBrief {
  task: string | null;
  group_name: string;
  agent_type: string | null;
  items: TaskBriefItem[];
  assumptions: string[];
}

function formatValue(value: string | string[] | null): string {
  if (Array.isArray(value)) return value.join(', ');
  return value ?? '';
}

function isRequiredCheckpoint(cp: TaskIntakeCheckpoint): boolean {
  if (cp.scope === 'core') return cp.id !== 'C4';
  return cp.must === true;
}

export function buildTaskBrief(
  intake: TaskIntakeData,
  answers: Record<string, TaskIntakeAnswer>
): TaskBrief {
  const items: TaskBriefItem[] = [];

  for (const cp of intake.checkpoints) {
    const a = answers[cp.id];

    if (cp.id === 'C1') {
      if (a && !a.skipped) {
        items.push({ id: cp.id, name: cp.name, value: formatValue(a.value), source: 'you' });
      } else if (intake.task) {
        items.push({ id: cp.id, name: cp.name, value: intake.task, source: 'prompt' });
      } else {
        items.push({ id: cp.id, name: cp.name, value: 'General task', source: 'assumed' });
      }
      continue;
    }

    if (a && !a.skipped) {
      items.push({ id: cp.id, name: cp.name, value: formatValue(a.value), source: 'you' });
      continue;
    }

    if (cp.state === 'found') {
      items.push({
        id: cp.id,
        name: cp.name,
        value: formatValue(cp.value),
        source: cp.source === 'brief' ? 'brief' : 'prompt',
      });
      continue;
    }

    if (cp.state === 'prefilled') {
      items.push({ id: cp.id, name: cp.name, value: formatValue(cp.value), source: 'brand' });
      continue;
    }

    if (cp.state === 'optional_missing') {
      continue; // omitted entirely, unless already answered above
    }

    // missing + skipped/unanswered
    if (isRequiredCheckpoint(cp)) {
      items.push({ id: cp.id, name: cp.name, value: 'Best judgement', source: 'assumed' });
    }
    // non-must group checkpoint that's missing and unanswered -> omitted
  }

  const assumptions = items.filter(item => item.source === 'assumed').map(item => item.name);

  return {
    task: intake.task,
    group_name: intake.group_name,
    agent_type: intake.agent_type,
    items,
    assumptions,
  };
}
