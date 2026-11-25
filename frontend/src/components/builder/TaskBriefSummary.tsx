'use client';
import { useState, type CSSProperties } from 'react';
import type { TaskBrief, TaskBriefItem, BriefSource } from './taskBrief';

interface TaskBriefSummaryProps {
  brief: TaskBrief;
  onConfirm?: (brief: TaskBrief) => void;
  readOnly?: boolean;
}

// Same inline-style approach and palette as TaskIntakeQuestions.tsx — gold
// accent, cream surfaces, same borders/radii/spacing — so the two cards read
// as one flow, not two different components.
const GOLD = '#D4A843';
const GOLD_DARK = '#B8912E';
const CREAM = '#FAF8F5';
const BORDER = '#E8E4DC';
const TEXT = '#1A1A1A';
const MUTED = '#6B6560';
// Distinct amber for the "assumed" source tag (§2.10: it should stand out) —
// a step warmer/more saturated than the app's usual gold accent, not a new
// unrelated color.
const AMBER = '#C9821A';
const AMBER_BG = 'rgba(201, 130, 26, 0.1)';
const AMBER_BORDER = 'rgba(201, 130, 26, 0.3)';

const SOURCE_LABELS: Record<BriefSource, string> = {
  prompt: 'from your message',
  brief: 'from brief',
  brand: 'from brand',
  you: 'you added',
  assumed: 'assumed',
};

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
  itemRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    gap: 12,
    padding: '10px 0',
    borderBottom: `1px solid ${BORDER}`,
  },
  itemRowEditing: {
    flexDirection: 'column',
    alignItems: 'stretch',
    gap: 6,
  },
  itemText: {
    fontSize: 13,
    color: TEXT,
  },
  itemName: {
    fontWeight: 600,
  },
  sourceTag: {
    flexShrink: 0,
    fontSize: 11,
    fontWeight: 600,
    color: MUTED,
    background: CREAM,
    border: `1px solid ${BORDER}`,
    borderRadius: 6,
    padding: '2px 8px',
    whiteSpace: 'nowrap',
  },
  sourceTagAssumed: {
    color: AMBER,
    background: AMBER_BG,
    borderColor: AMBER_BORDER,
  },
  editInput: {
    width: '100%',
    height: 36,
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: '0 10px',
    fontSize: 13,
    fontFamily: 'inherit',
    outline: 'none',
  },
  assumptionsLine: {
    fontSize: 12,
    color: MUTED,
    marginTop: 14,
  },
  footer: {
    display: 'flex',
    alignItems: 'center',
    gap: 12,
    marginTop: 16,
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
  editBtn: {
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

export default function TaskBriefSummary({ brief, onConfirm, readOnly = false }: TaskBriefSummaryProps) {
  const [currentBrief, setCurrentBrief] = useState<TaskBrief>(brief);
  const [editing, setEditing] = useState(false);
  const [draftItems, setDraftItems] = useState<TaskBriefItem[]>(brief.items);

  const startEdit = () => {
    if (readOnly) return;
    setDraftItems(currentBrief.items.map(item => ({ ...item })));
    setEditing(true);
  };

  const updateDraftValue = (id: string, value: string) => {
    setDraftItems(prev => prev.map(item => (item.id === id ? { ...item, value, source: 'you' } : item)));
  };

  const handleSave = () => {
    const assumptions = draftItems.filter(item => item.source === 'assumed').map(item => item.name);
    setCurrentBrief({ ...currentBrief, items: draftItems, assumptions });
    setEditing(false);
  };

  const handleContinue = () => onConfirm?.(currentBrief);

  const displayedItems = editing ? draftItems : currentBrief.items;

  return (
    <div style={styles.card}>
      <h2 style={styles.header}>Task Brief — {currentBrief.task ?? 'Task'}</h2>

      {displayedItems.map(item => (
        <div key={item.id} style={{ ...styles.itemRow, ...(editing ? styles.itemRowEditing : {}) }}>
          {editing ? (
            <>
              <span style={styles.itemText}>
                <span style={styles.itemName}>{item.name}</span>
              </span>
              <input
                type="text"
                style={styles.editInput}
                value={item.value}
                onChange={e => updateDraftValue(item.id, e.target.value)}
              />
            </>
          ) : (
            <>
              <span style={styles.itemText}>
                <span style={styles.itemName}>{item.name}:</span> {item.value}
              </span>
              <span style={{ ...styles.sourceTag, ...(item.source === 'assumed' ? styles.sourceTagAssumed : {}) }}>
                {SOURCE_LABELS[item.source]}
              </span>
            </>
          )}
        </div>
      ))}

      <div style={styles.assumptionsLine}>
        {currentBrief.assumptions.length > 0
          ? `Assumptions: ${currentBrief.assumptions.join(', ')}`
          : 'Assumptions: none'}
      </div>

      {!readOnly && (
        <div style={styles.footer}>
          {editing ? (
            <button type="button" style={styles.continueBtn} onClick={handleSave}>
              Save
            </button>
          ) : (
            <>
              <button type="button" style={styles.continueBtn} onClick={handleContinue}>
                Continue
              </button>
              <button type="button" style={styles.editBtn} onClick={startEdit}>
                Edit
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
