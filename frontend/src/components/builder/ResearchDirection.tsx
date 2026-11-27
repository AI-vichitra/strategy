'use client';
import { useState, type CSSProperties } from 'react';

export interface ResearchSubHeader {
  id: string;
  label: string;
}

export interface ResearchHeading {
  id: string;
  label: string;
  sub_headers: ResearchSubHeader[];
}

export interface ResearchMarket {
  global: boolean;
  national: string | null;
  local: string[];
  // Only meaningful when local.length > 1 — null whenever there are 0 or 1
  // local entries (set back to null the moment a 2nd entry is removed).
  multi_city_mode: 'combined' | 'compare' | null;
}

export interface ResearchMarketPrefill {
  global: boolean;
  national: string | null;
  local: string[];
}

export interface ResearchSelection {
  headings: string[];
  // heading_id -> included sub-header ids. Present ONLY for headings the
  // user actually customised to something other than "everything ticked" —
  // a heading left at its default (never opened, or opened and left fully
  // ticked) has no entry here, meaning "all sub-headers included".
  sub_headers: Record<string, string[]>;
  custom_topics: string[];
  market: ResearchMarket;
}

interface ResearchDirectionProps {
  headings: ResearchHeading[];
  preselected: string[];
  marketPrefill: ResearchMarketPrefill;
  // When provided (a remount after Back, or after a failed save), every
  // field is restored from here instead of from preselected/marketPrefill —
  // see MainContent's lifted researchSelection state.
  initialSelection?: ResearchSelection | null;
  onBack: () => void;
  onComplete: (selection: ResearchSelection) => void;
}

// Same palette/visual language as TaskIntakeQuestions.tsx / TaskBriefSummary.tsx.
const GOLD = '#D4A843';
const GOLD_DARK = '#B8912E';
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
    margin: '0 0 6px',
  },
  subheader: {
    fontSize: 13,
    color: MUTED,
    margin: '0 0 18px',
  },
  marketBlock: {
    marginBottom: 18,
    paddingBottom: 16,
    borderBottom: `1px solid ${BORDER}`,
  },
  marketRow: {
    display: 'flex',
    alignItems: 'baseline',
    flexWrap: 'wrap',
    gap: 8,
    padding: '10px 12px',
    background: '#FAF8F5',
    border: `1px solid ${BORDER}`,
    borderRadius: 10,
    fontSize: 13,
    color: MUTED,
  },
  marketLabel: {
    fontWeight: 600,
    color: TEXT,
  },
  marketValue: {
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
  marketPanel: {
    marginTop: 10,
    padding: 14,
    border: `1px solid ${BORDER}`,
    borderRadius: 10,
    display: 'flex',
    flexDirection: 'column',
    gap: 12,
  },
  marketPanelRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: TEXT,
    cursor: 'pointer',
  },
  marketPanelField: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
  },
  marketFieldLabel: {
    fontSize: 12,
    fontWeight: 600,
    color: MUTED,
  },
  marketInput: {
    height: 34,
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: '0 10px',
    fontSize: 13,
    fontFamily: 'inherit',
    outline: 'none',
  },
  localChipsRow: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 6,
    marginBottom: 6,
  },
  localChip: {
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    fontSize: 12,
    color: TEXT,
    background: '#FAF8F5',
    border: `1px solid ${BORDER}`,
    borderRadius: 999,
    padding: '4px 6px 4px 10px',
  },
  removeChipBtn: {
    background: 'none',
    border: 'none',
    color: FAINT,
    fontSize: 14,
    cursor: 'pointer',
    padding: '0 2px',
    lineHeight: 1,
  },
  localAddRow: {
    display: 'flex',
    gap: 8,
  },
  addLocalBtn: {
    padding: '0 14px',
    background: 'none',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    color: GOLD_DARK,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
  },
  multiCityRow: {
    display: 'flex',
    flexDirection: 'column',
    gap: 6,
    paddingTop: 4,
  },
  radioRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 6,
    fontSize: 13,
    color: TEXT,
    cursor: 'pointer',
  },
  doneBtn: {
    alignSelf: 'flex-start',
    background: 'none',
    border: 'none',
    color: GOLD_DARK,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    padding: 0,
  },
  headingBlock: {
    padding: '12px 0',
    borderBottom: `1px solid ${BORDER}`,
  },
  headingRow: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    gap: 8,
  },
  headingLabelRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    cursor: 'pointer',
  },
  checkbox: {
    width: 16,
    height: 16,
    flexShrink: 0,
    accentColor: GOLD_DARK,
    cursor: 'pointer',
  },
  headingText: {
    fontSize: 14,
    fontWeight: 600,
    color: TEXT,
  },
  customiseLink: {
    background: 'none',
    border: 'none',
    color: GOLD_DARK,
    fontSize: 12,
    fontWeight: 600,
    cursor: 'pointer',
    padding: 0,
    whiteSpace: 'nowrap',
  },
  subHeaderList: {
    marginTop: 10,
    marginLeft: 26,
    display: 'flex',
    flexDirection: 'column',
    gap: 8,
  },
  subHeaderRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    fontSize: 13,
    color: TEXT,
    cursor: 'pointer',
  },
  customTopicsBlock: {
    marginTop: 16,
  },
  topicRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 8,
  },
  topicText: {
    fontSize: 13,
    color: TEXT,
    background: '#FAF8F5',
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: '6px 10px',
    flex: 1,
  },
  removeTopicBtn: {
    background: 'none',
    border: 'none',
    color: FAINT,
    fontSize: 16,
    cursor: 'pointer',
    padding: '0 6px',
    lineHeight: 1,
  },
  topicInput: {
    width: '100%',
    height: 36,
    border: `1px solid ${BORDER}`,
    borderRadius: 8,
    padding: '0 10px',
    fontSize: 13,
    fontFamily: 'inherit',
    outline: 'none',
  },
  addTopicLink: {
    background: 'none',
    border: 'none',
    color: GOLD_DARK,
    fontSize: 13,
    fontWeight: 600,
    cursor: 'pointer',
    padding: 0,
  },
  note: {
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
  continueBtnDisabled: {
    opacity: 0.45,
    cursor: 'not-allowed',
  },
  backBtn: {
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

export default function ResearchDirection({ headings, preselected, marketPrefill, initialSelection, onBack, onComplete }: ResearchDirectionProps) {
  const [checkedHeadings, setCheckedHeadings] = useState<Set<string>>(
    () => new Set(initialSelection ? initialSelection.headings : preselected)
  );
  const [openCustomise, setOpenCustomise] = useState<Set<string>>(
    () => new Set(initialSelection ? Object.keys(initialSelection.sub_headers) : [])
  );
  // heading_id -> set of sub-header ids currently ticked. Only populated once
  // a heading's Customise panel is opened (lazily seeded to "all ticked"), or
  // restored here from initialSelection on a remount.
  const [subHeaderState, setSubHeaderState] = useState<Record<string, Set<string>>>(() => {
    if (!initialSelection) return {};
    const out: Record<string, Set<string>> = {};
    for (const [headingId, subIds] of Object.entries(initialSelection.sub_headers)) {
      out[headingId] = new Set(subIds);
    }
    return out;
  });
  const [customTopics, setCustomTopics] = useState<string[]>(() => (initialSelection ? [...initialSelection.custom_topics] : []));
  const [addingTopic, setAddingTopic] = useState(false);
  const [topicDraft, setTopicDraft] = useState('');

  const [market, setMarket] = useState<ResearchMarket>(() => {
    if (initialSelection) return initialSelection.market;
    return {
      global: marketPrefill.global,
      national: marketPrefill.national,
      local: [...marketPrefill.local],
      multi_city_mode: marketPrefill.local.length > 1 ? 'combined' : null,
    };
  });
  const [marketPanelOpen, setMarketPanelOpen] = useState(false);
  const [localDraft, setLocalDraft] = useState('');

  const marketSummary = (): string => {
    const parts: string[] = [];
    if (market.global) parts.push('Global');
    if (market.national) parts.push(market.national);
    if (market.local.length) parts.push(market.local.join(', '));
    return parts.length ? parts.join(' · ') : 'Not set';
  };

  const toggleGlobal = () => setMarket(m => ({ ...m, global: !m.global }));
  const setNational = (value: string) => setMarket(m => ({ ...m, national: value === '' ? null : value }));

  const addLocal = () => {
    const text = localDraft.trim();
    if (!text) return;
    setMarket(m => {
      const nextLocal = [...m.local, text];
      return { ...m, local: nextLocal, multi_city_mode: nextLocal.length > 1 ? (m.multi_city_mode ?? 'combined') : null };
    });
    setLocalDraft('');
  };

  const removeLocal = (idx: number) => {
    setMarket(m => {
      const nextLocal = m.local.filter((_, i) => i !== idx);
      return { ...m, local: nextLocal, multi_city_mode: nextLocal.length > 1 ? (m.multi_city_mode ?? 'combined') : null };
    });
  };

  const setMultiCityMode = (mode: 'combined' | 'compare') => setMarket(m => ({ ...m, multi_city_mode: mode }));

  const toggleHeading = (id: string) => {
    setCheckedHeadings(prev => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id); else next.add(id);
      return next;
    });
  };

  const toggleCustomise = (heading: ResearchHeading) => {
    setOpenCustomise(prev => {
      const next = new Set(prev);
      if (next.has(heading.id)) {
        next.delete(heading.id);
      } else {
        next.add(heading.id);
        setSubHeaderState(sh => (sh[heading.id] ? sh : { ...sh, [heading.id]: new Set(heading.sub_headers.map(s => s.id)) }));
      }
      return next;
    });
  };

  const toggleSubHeader = (headingId: string, subId: string) => {
    setSubHeaderState(prev => {
      const current = new Set(prev[headingId]);
      if (current.has(subId)) current.delete(subId); else current.add(subId);
      return { ...prev, [headingId]: current };
    });
  };

  const commitTopicDraft = () => {
    const text = topicDraft.trim();
    if (text) setCustomTopics(prev => [...prev, text]);
    setTopicDraft('');
    setAddingTopic(false);
  };

  const removeTopic = (idx: number) => {
    setCustomTopics(prev => prev.filter((_, i) => i !== idx));
  };

  const hasSelection = checkedHeadings.size > 0 || customTopics.length > 0;

  const handleContinue = () => {
    if (!hasSelection) return;

    const sub_headers: Record<string, string[]> = {};
    for (const heading of headings) {
      if (!checkedHeadings.has(heading.id)) continue;
      const subSet = subHeaderState[heading.id];
      if (!subSet || subSet.size === heading.sub_headers.length) continue; // never customised, or customised back to "all" — same as default
      sub_headers[heading.id] = heading.sub_headers.filter(s => subSet.has(s.id)).map(s => s.id);
    }

    onComplete({
      headings: headings.filter(h => checkedHeadings.has(h.id)).map(h => h.id),
      sub_headers,
      custom_topics: customTopics,
      market,
    });
  };

  return (
    <div style={styles.card}>
      <h2 style={styles.header}>Research Direction</h2>
      <p style={styles.subheader}>
        We&rsquo;ll research these areas for this task. Untick anything you don&rsquo;t need, or customise what&rsquo;s covered.
      </p>

      <div style={styles.marketBlock}>
        {!marketPanelOpen ? (
          <div style={styles.marketRow}>
            <span style={styles.marketLabel}>Research market:</span>
            <span style={styles.marketValue}>{marketSummary()}</span>
            <button type="button" style={styles.changeLink} onClick={() => setMarketPanelOpen(true)}>
              [Change]
            </button>
          </div>
        ) : (
          <div style={styles.marketPanel}>
            <label style={styles.marketPanelRow}>
              <input type="checkbox" style={styles.checkbox} checked={market.global} onChange={toggleGlobal} />
              <span>Global</span>
            </label>

            <div style={styles.marketPanelField}>
              <span style={styles.marketFieldLabel}>National</span>
              <input
                type="text"
                style={styles.marketInput}
                placeholder="e.g. India"
                value={market.national ?? ''}
                onChange={e => setNational(e.target.value)}
              />
            </div>

            <div style={styles.marketPanelField}>
              <span style={styles.marketFieldLabel}>Local</span>
              {market.local.length > 0 && (
                <div style={styles.localChipsRow}>
                  {market.local.map((loc, idx) => (
                    <span key={`${loc}-${idx}`} style={styles.localChip}>
                      {loc}
                      <button type="button" style={styles.removeChipBtn} onClick={() => removeLocal(idx)} aria-label="Remove">
                        ×
                      </button>
                    </span>
                  ))}
                </div>
              )}
              <div style={styles.localAddRow}>
                <input
                  type="text"
                  style={{ ...styles.marketInput, flex: 1 }}
                  placeholder="Add a city or region…"
                  value={localDraft}
                  onChange={e => setLocalDraft(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      addLocal();
                    }
                  }}
                />
                <button type="button" style={styles.addLocalBtn} onClick={addLocal}>
                  Add
                </button>
              </div>
            </div>

            {market.local.length > 1 && (
              <div style={styles.multiCityRow}>
                <span style={styles.marketFieldLabel}>Multiple cities selected</span>
                <label style={styles.radioRow}>
                  <input type="radio" checked={market.multi_city_mode === 'combined'} onChange={() => setMultiCityMode('combined')} />
                  Treat as one combined market
                </label>
                <label style={styles.radioRow}>
                  <input type="radio" checked={market.multi_city_mode === 'compare'} onChange={() => setMultiCityMode('compare')} />
                  Compare city by city
                </label>
              </div>
            )}

            <button type="button" style={styles.doneBtn} onClick={() => setMarketPanelOpen(false)}>
              Done
            </button>
          </div>
        )}
      </div>

      {headings.map(heading => {
        const checked = checkedHeadings.has(heading.id);
        const expanded = checked && openCustomise.has(heading.id);
        const subSet = subHeaderState[heading.id];

        return (
          <div key={heading.id} style={styles.headingBlock}>
            <div style={styles.headingRow}>
              <label style={styles.headingLabelRow}>
                <input
                  type="checkbox"
                  style={styles.checkbox}
                  checked={checked}
                  onChange={() => toggleHeading(heading.id)}
                />
                <span style={styles.headingText}>{heading.label}</span>
              </label>
              {checked && heading.sub_headers.length > 0 && (
                <button type="button" style={styles.customiseLink} onClick={() => toggleCustomise(heading)}>
                  {expanded ? 'Hide ▾' : 'Customise ▸'}
                </button>
              )}
            </div>

            {expanded && (
              <div style={styles.subHeaderList}>
                {heading.sub_headers.map(sub => (
                  <label key={sub.id} style={styles.subHeaderRow}>
                    <input
                      type="checkbox"
                      style={styles.checkbox}
                      checked={subSet ? subSet.has(sub.id) : true}
                      onChange={() => toggleSubHeader(heading.id, sub.id)}
                    />
                    <span>{sub.label}</span>
                  </label>
                ))}
              </div>
            )}
          </div>
        );
      })}

      <div style={styles.customTopicsBlock}>
        {customTopics.map((topic, idx) => (
          <div key={idx} style={styles.topicRow}>
            <span style={styles.topicText}>{topic}</span>
            <button type="button" style={styles.removeTopicBtn} onClick={() => removeTopic(idx)} aria-label="Remove topic">
              ×
            </button>
          </div>
        ))}
        {addingTopic ? (
          <input
            type="text"
            autoFocus
            style={styles.topicInput}
            placeholder="Type a custom research topic…"
            value={topicDraft}
            onChange={e => setTopicDraft(e.target.value)}
            onKeyDown={e => {
              if (e.key === 'Enter') commitTopicDraft();
            }}
            onBlur={commitTopicDraft}
          />
        ) : (
          <button type="button" style={styles.addTopicLink} onClick={() => setAddingTopic(true)}>
            + Add a custom topic
          </button>
        )}
      </div>

      {!hasSelection && <div style={styles.note}>Select at least one heading or add a custom topic</div>}

      <div style={styles.footer}>
        <button
          type="button"
          style={{ ...styles.continueBtn, ...(hasSelection ? {} : styles.continueBtnDisabled) }}
          onClick={handleContinue}
          disabled={!hasSelection}
        >
          Continue
        </button>
        <button type="button" style={styles.backBtn} onClick={onBack}>
          Back
        </button>
      </div>
    </div>
  );
}
