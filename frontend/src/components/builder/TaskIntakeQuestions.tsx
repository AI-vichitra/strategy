'use client';
import { useState, type CSSProperties } from 'react';
import sharedStyles from './MainContent.module.css';
import type { ResearchHeading } from './ResearchDirection';

export interface TaskIntakeCheckpoint {
  id: string;
  name: string;
  scope: string;
  must: boolean;
  state: string;
  value: string | string[] | null;
  source: string | null;
}

export interface TaskIntakeQuestion {
  checkpoint_id: string;
  text: string;
  options: string[];
  multi_select?: boolean;
  allow_other?: boolean;
  skippable?: boolean;
}

export interface TaskIntakeData {
  task: string | null;
  group_name: string;
  group_id: string;
  agent_type: string | null;
  matched: boolean;
  checkpoints: TaskIntakeCheckpoint[];
  questions: TaskIntakeQuestion[];
  missing_required: string[];
  research_headings: ResearchHeading[];
  step3_preselected: string[];
  research_market_prefill: { global: boolean; national: string | null; local: string[] };
}

export type TaskIntakeAnswer = { value: string | string[] | null; skipped: boolean };

interface TaskIntakeQuestionsProps {
  intake: TaskIntakeData;
  onComplete: (answers: Record<string, TaskIntakeAnswer>) => void;
}

interface QuestionLocalState {
  selectedOptions: string[];
  otherActive: boolean;
  otherText: string;
}

const GOLD = '#D4A843';
const GOLD_DARK = '#B8912E';
const CREAM = '#FAF8F5';
const BORDER = '#E8E4DC';
const TEXT = '#1A1A1A';
const MUTED = '#6B6560';
const FAINT = '#A39E97';

const styles: Record<string, CSSProperties> = {
  card: {
    background: '#ffffff',
    border: `1px solid ${BORDER}`,
    borderRadius: 16,
    padding: 24,
    width: '100%',
    boxSizing: 'border-box',
    fontFamily: 'inherit',
    boxShadow: '0 4px 20px rgba(0,0,0,0.03), 0 2px 8px rgba(0,0,0,0.02)',
  },
  header: {
    fontSize: 17,
    fontWeight: 700,
    color: TEXT,
    margin: '0 0 18px',
  },
  c4Row: {
    display: 'flex',
    alignItems: 'baseline',
    flexWrap: 'wrap',
    gap: 8,
    padding: '10px 12px',
    background: CREAM,
    border: `1px solid ${BORDER}`,
    borderRadius: 10,
    marginBottom: 20,
    fontSize: 13,
    color: MUTED,
  },
  c4Value: {
    color: TEXT,
    fontWeight: 500,
  },
  changeLink: {
    background: 'none',
    border: 'none',
    color: GOLD_DARK,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    padding: 0,
  },
  c4Input: {
    width: '100%',
    marginTop: 8,
    height: 36,
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: '0 10px',
    fontSize: 13,
    fontFamily: 'inherit',
    outline: 'none',
  },
  questionBlock: {
    marginBottom: 20,
  },
  questionText: {
    fontSize: 14,
    fontWeight: 600,
    color: TEXT,
    marginBottom: 10,
  },
  chipRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
  },
  otherInput: {
    width: '100%',
    marginTop: 8,
    height: 36,
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: '0 10px',
    fontSize: 13,
    fontFamily: 'inherit',
    outline: 'none',
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginTop: 8,
    paddingTop: 16,
    borderTop: `1px solid ${BORDER}`,
  },
  continueBtn: {
    padding: '10px 20px',
    background: `linear-gradient(135deg, ${GOLD}, ${GOLD_DARK})`,
    color: '#ffffff',
    border: 'none',
    borderRadius: 8,
    fontSize: 14,
    fontWeight: 600,
    cursor: 'pointer',
  },
  skipBtn: {
    padding: '10px 16px',
    background: 'none',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    color: MUTED,
    fontSize: 13,
    fontWeight: 500,
    cursor: 'pointer',
  },
};

function emptyQState(): QuestionLocalState {
  return { selectedOptions: [], otherActive: false, otherText: '' };
}

export default function TaskIntakeQuestions({ intake, onComplete }: TaskIntakeQuestionsProps) {
  const [qState, setQState] = useState<Record<string, QuestionLocalState>>({});
  const [c4ChangeOpen, setC4ChangeOpen] = useState(false);
  const [c4ChangeUsed, setC4ChangeUsed] = useState(false);
  const [c4Draft, setC4Draft] = useState('');

  const c4 = intake.checkpoints.find(cp => cp.id === 'C4' && cp.state === 'prefilled');

  const getQState = (checkpointId: string): QuestionLocalState => qState[checkpointId] || emptyQState();

  // Generic rule for any multi_select question: "All" is exclusive —
  // selecting it clears every other chip, and selecting anything else
  // clears "All" first. Works for any question that happens to offer an
  // "All" option, not just C2.
  const isAllOption = (option: string) => option.trim().toLowerCase() === 'all';

  const handleChipClick = (q: TaskIntakeQuestion, option: string) => {
    setQState(prev => {
      const cur = prev[q.checkpoint_id] || emptyQState();
      if (q.multi_select) {
        if (isAllOption(option)) {
          const allSelected = cur.selectedOptions.some(isAllOption);
          const selectedOptions = allSelected ? [] : [option];
          return { ...prev, [q.checkpoint_id]: { ...cur, selectedOptions } };
        }
        const withoutAll = cur.selectedOptions.filter(o => !isAllOption(o));
        const exists = withoutAll.includes(option);
        const selectedOptions = exists
          ? withoutAll.filter(o => o !== option)
          : [...withoutAll, option];
        return { ...prev, [q.checkpoint_id]: { ...cur, selectedOptions } };
      }
      const isSame = cur.selectedOptions[0] === option;
      return {
        ...prev,
        [q.checkpoint_id]: { selectedOptions: isSame ? [] : [option], otherActive: false, otherText: cur.otherText },
      };
    });
  };

  const handleOtherToggle = (q: TaskIntakeQuestion) => {
    setQState(prev => {
      const cur = prev[q.checkpoint_id] || emptyQState();
      const nextActive = !cur.otherActive;
      if (q.multi_select) {
        return { ...prev, [q.checkpoint_id]: { ...cur, otherActive: nextActive } };
      }
      // Single-select: activating Other clears any chip selection.
      return {
        ...prev,
        [q.checkpoint_id]: { selectedOptions: nextActive ? [] : cur.selectedOptions, otherActive: nextActive, otherText: cur.otherText },
      };
    });
  };

  const handleOtherTextChange = (q: TaskIntakeQuestion, text: string) => {
    setQState(prev => {
      const cur = prev[q.checkpoint_id] || emptyQState();
      return { ...prev, [q.checkpoint_id]: { ...cur, otherText: text } };
    });
  };

  const openC4Change = () => {
    const initial = Array.isArray(c4?.value) ? c4!.value.join(', ') : (c4?.value || '');
    setC4Draft(initial);
    setC4ChangeOpen(true);
    setC4ChangeUsed(true);
  };

  const buildAnswers = (forceSkip: boolean): Record<string, TaskIntakeAnswer> => {
    const answers: Record<string, TaskIntakeAnswer> = {};

    intake.questions.forEach(q => {
      if (forceSkip) {
        answers[q.checkpoint_id] = { value: null, skipped: true };
        return;
      }
      const cur = getQState(q.checkpoint_id);
      if (q.multi_select) {
        const combined = [...cur.selectedOptions, ...(cur.otherActive && cur.otherText.trim() ? [cur.otherText.trim()] : [])];
        answers[q.checkpoint_id] = combined.length > 0 ? { value: combined, skipped: false } : { value: null, skipped: true };
      } else {
        const otherVal = cur.otherActive && cur.otherText.trim() ? cur.otherText.trim() : null;
        const chipVal = cur.selectedOptions[0] ?? null;
        const val = otherVal ?? chipVal;
        answers[q.checkpoint_id] = val ? { value: val, skipped: false } : { value: null, skipped: true };
      }
    });

    // C4 is included only when [Change] was actually used — on either
    // Continue or Skip — never as an untouched/skipped entry.
    if (c4ChangeUsed) {
      answers['C4'] = { value: c4Draft.trim() || null, skipped: false };
    }

    return answers;
  };

  const handleContinue = () => onComplete(buildAnswers(false));
  const handleSkip = () => onComplete(buildAnswers(true));

  return (
    <div style={styles.card}>
      <h2 style={styles.header}>
        {intake.task ? `To tailor your ${intake.task}, a few quick questions:` : 'A few quick questions:'}
      </h2>

      {c4 && (
        <div style={styles.c4Row}>
          <span>
            Audience &amp; market from your brand:{' '}
            <span style={styles.c4Value}>{Array.isArray(c4.value) ? c4.value.join(', ') : c4.value}</span>
          </span>
          {!c4ChangeOpen && (
            <button type="button" style={styles.changeLink} onClick={openC4Change}>
              [Change]
            </button>
          )}
          {c4ChangeOpen && (
            <input
              type="text"
              style={styles.c4Input}
              value={c4Draft}
              onChange={e => setC4Draft(e.target.value)}
            />
          )}
        </div>
      )}

      {intake.questions.map(q => {
        const cur = getQState(q.checkpoint_id);
        return (
          <div key={q.checkpoint_id} style={styles.questionBlock}>
            <div style={styles.questionText}>{q.text}</div>
            <div style={styles.chipRow}>
              {q.options.map(option => {
                const selected = cur.selectedOptions.includes(option);
                return (
                  <button
                    key={option}
                    type="button"
                    className={`${sharedStyles.intakeChip} ${selected ? sharedStyles.intakeChipSelected : ''}`}
                    onClick={() => handleChipClick(q, option)}
                  >
                    {option}
                  </button>
                );
              })}
              {q.allow_other && (
                <button
                  type="button"
                  className={`${sharedStyles.intakeChip} ${cur.otherActive ? sharedStyles.intakeChipSelected : ''}`}
                  onClick={() => handleOtherToggle(q)}
                >
                  Other
                </button>
              )}
            </div>
            {q.allow_other && cur.otherActive && (
              <input
                type="text"
                style={styles.otherInput}
                placeholder="Type your answer…"
                value={cur.otherText}
                onChange={e => handleOtherTextChange(q, e.target.value)}
              />
            )}
          </div>
        );
      })}

      <div style={styles.footer}>
        <button type="button" style={styles.continueBtn} onClick={handleContinue}>
          Continue
        </button>
        <button type="button" style={styles.skipBtn} onClick={handleSkip}>
          Skip – use your best judgement
        </button>
      </div>
    </div>
  );
}
