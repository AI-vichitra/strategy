'use client';
import { useEffect, useState } from 'react';
import ReportRenderer from './ReportRenderer';
import { useSections, type ReportSection } from '../hooks/useSections';
import styles from './SectionEditor.module.css';

interface ReportMeta {
  title: string;
  agent_type: string;
}

function detectSectionType(content: string): string {
  if (content.includes('```recharts')) return 'chart';
  if (/\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)+\|?/.test(content)) return 'table';
  return 'heading';
}

function replaceHeadingLine(content: string, newTitle: string): string {
  const lines = content.split('\n');
  const idx = lines.findIndex((l) => /^###\s+/.test(l));
  if (idx === -1) return content;
  lines[idx] = `### ${newTitle}`;
  return lines.join('\n');
}

function extractTitleFromContent(content: string): string | null {
  const match = content.match(/^###[ \t]+(.+)$/m);
  if (!match) return null;
  const title = match[1].replace(/\*+/g, '').trim();
  return title || null;
}

function autoGrow(el: HTMLTextAreaElement | null) {
  if (!el) return;
  el.style.height = 'auto';
  el.style.height = `${Math.max(el.scrollHeight, 200)}px`;
}

function AddRow({
  afterOrder,
  isOpen,
  busy,
  title,
  content,
  onOpen,
  onTitleChange,
  onContentChange,
  onCancel,
  onSubmit,
}: {
  afterOrder: number;
  isOpen: boolean;
  busy: boolean;
  title: string;
  content: string;
  onOpen: (afterOrder: number) => void;
  onTitleChange: (value: string) => void;
  onContentChange: (value: string) => void;
  onCancel: () => void;
  onSubmit: () => void;
}) {
  if (!isOpen) {
    return (
      <button type="button" className={styles.addSectionRow} onClick={() => onOpen(afterOrder)} title="Add a section here">
        <span className={styles.addSectionPlus}>+</span>
        <span>Add Section</span>
      </button>
    );
  }
  return (
    <div className={styles.addForm}>
      <input
        type="text"
        className={styles.addFormInput}
        placeholder="Section title (optional)"
        value={title}
        onChange={(e) => onTitleChange(e.target.value)}
      />
      <textarea
        className={styles.addFormTextarea}
        placeholder="Markdown content for this section..."
        value={content}
        onChange={(e) => onContentChange(e.target.value)}
        rows={4}
      />
      <div className={styles.addFormActions}>
        <button type="button" className={styles.addFormCancel} onClick={onCancel}>
          Cancel
        </button>
        <button type="button" className={styles.addFormSubmit} onClick={onSubmit} disabled={busy || !content.trim()}>
          Add Section
        </button>
      </div>
    </div>
  );
}

function getApiBase(): string {
  return process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
}

function getAuthHeaders(): Record<string, string> {
  const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
  const headers: Record<string, string> = {};
  if (token) headers['Authorization'] = `Bearer ${token}`;
  return headers;
}

export default function SectionEditor({ reportId, onClose }: { reportId: string; onClose: () => void }) {
  const {
    fetchSections,
    parseReport,
    createSection,
    updateSection,
    deleteSection,
    reorderSections,
    getFinalizedContent,
  } = useSections();

  const [sections, setSections] = useState<ReportSection[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [reportMeta, setReportMeta] = useState<ReportMeta | null>(null);
  const [editingTitleId, setEditingTitleId] = useState<number | null>(null);
  const [titleDraft, setTitleDraft] = useState('');
  const [editingSectionId, setEditingSectionId] = useState<number | null>(null);
  const [contentDraft, setContentDraft] = useState('');
  const [expandedSectionId, setExpandedSectionId] = useState<number | null>(null);
  const [addFormAfterOrder, setAddFormAfterOrder] = useState<number | null>(null);
  const [newTitle, setNewTitle] = useState('');
  const [newContent, setNewContent] = useState('');
  const [exportingDocx, setExportingDocx] = useState(false);
  const [busy, setBusy] = useState(false);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      let data = await fetchSections(reportId);
      if (data.length === 0) {
        data = await parseReport(reportId);
      }
      setSections(data);
    } catch (err) {
      console.error('Failed to load sections:', err);
      setError('Could not load sections for this report.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    (async () => {
      try {
        const res = await fetch(`${getApiBase()}/api/reports/${reportId}`, { headers: getAuthHeaders() });
        if (res.ok) {
          const data = await res.json();
          setReportMeta({ title: data.title, agent_type: data.agent_type });
        }
      } catch (err) {
        console.error('Failed to load report metadata:', err);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportId]);

  const handleMove = async (index: number, direction: -1 | 1) => {
    const targetIndex = index + direction;
    if (targetIndex < 0 || targetIndex >= sections.length) return;
    const reordered = [...sections];
    [reordered[index], reordered[targetIndex]] = [reordered[targetIndex], reordered[index]];
    setSections(reordered);
    setBusy(true);
    try {
      const updated = await reorderSections(reportId, reordered.map((s) => s.id));
      setSections(updated);
    } catch (err) {
      console.error('Failed to reorder sections:', err);
      setError('Failed to reorder. Please try again.');
      await load();
    } finally {
      setBusy(false);
    }
  };

  const commitTitle = async (section: ReportSection) => {
    const trimmed = titleDraft.trim();
    setEditingTitleId(null);
    if (!trimmed || trimmed === section.title) return;
    setBusy(true);
    try {
      const newContentStr = replaceHeadingLine(section.content, trimmed);
      const updated = await updateSection(reportId, section.id, { title: trimmed, content: newContentStr });
      setSections((prev) => prev.map((s) => (s.id === section.id ? updated : s)));
    } catch (err) {
      console.error('Failed to update title:', err);
      setError('Failed to update title. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const toggleVisible = async (section: ReportSection) => {
    setBusy(true);
    try {
      const updated = await updateSection(reportId, section.id, { visible: !section.visible });
      setSections((prev) => prev.map((s) => (s.id === section.id ? updated : s)));
    } catch (err) {
      console.error('Failed to toggle visibility:', err);
      setError('Failed to update visibility. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (section: ReportSection) => {
    if (!confirm('Delete this section?')) return;
    setBusy(true);
    try {
      await deleteSection(reportId, section.id);
      await load();
    } catch (err) {
      console.error('Failed to delete section:', err);
      setError('Failed to delete section. Please try again.');
    } finally {
      setBusy(false);
    }
  };

  const toggleExpand = (section: ReportSection) => {
    // Don't let navigating headers abandon an in-progress edit elsewhere —
    // same invariant the Edit button itself enforces.
    if (editingSectionId !== null && editingSectionId !== section.id) return;
    setExpandedSectionId((prev) => (prev === section.id ? null : section.id));
  };

  const startEditContent = (section: ReportSection) => {
    setEditingSectionId(section.id);
    setContentDraft(section.content);
    setExpandedSectionId(section.id);
  };

  const cancelEditContent = () => {
    setEditingSectionId(null);
    setContentDraft('');
  };

  const saveEditContent = async (section: ReportSection) => {
    setBusy(true);
    try {
      const extractedTitle = extractTitleFromContent(contentDraft) ?? undefined;
      const updated = await updateSection(reportId, section.id, {
        content: contentDraft,
        title: extractedTitle,
      });
      setSections((prev) => prev.map((s) => (s.id === section.id ? updated : s)));
      setEditingSectionId(null);
      setContentDraft('');
    } catch (err) {
      console.error('Failed to update section content:', err);
      const detail = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to save section: ${detail}`);
    } finally {
      setBusy(false);
    }
  };

  const openAddForm = (afterOrder: number) => {
    setAddFormAfterOrder(afterOrder);
    setNewTitle('');
    setNewContent('');
  };

  const submitAddForm = async () => {
    if (addFormAfterOrder === null) return;
    const content = newContent.trim();
    const title = newTitle.trim();
    if (!content) return;
    const sectionType = detectSectionType(content);
    const fullContent = title && !/^###\s+/.test(content) ? `### ${title}\n${content}` : content;
    setBusy(true);
    try {
      await createSection(reportId, {
        after_order: addFormAfterOrder,
        title: title || null,
        content: fullContent,
        section_type: sectionType,
      });
      setAddFormAfterOrder(null);
      await load();
    } catch (err) {
      console.error('Failed to create section:', err);
      const detail = err instanceof Error ? err.message : 'Unknown error';
      setError(`Failed to add section: ${detail}`);
    } finally {
      setBusy(false);
    }
  };

  const handleExportDocx = async () => {
    setExportingDocx(true);
    try {
      const content = await getFinalizedContent(reportId);
      const res = await fetch(`${getApiBase()}/api/reports/${reportId}/export/docx`, {
        method: 'POST',
        headers: { ...getAuthHeaders(), 'Content-Type': 'application/json' },
        body: JSON.stringify({ content }),
      });
      if (!res.ok) throw new Error(`Server error (${res.status})`);
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);

      const sanitize = (s: string) => s.replace(/[/\\?%*:|"<>]/g, '').trim();
      const fileName = `${sanitize(reportMeta?.agent_type || reportMeta?.title || 'Report')}.docx`;

      const a = document.createElement('a');
      a.href = url;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error('Failed to export DOCX:', err);
      alert('Failed to export DOCX. Please try again.');
    } finally {
      setExportingDocx(false);
    }
  };

  return (
    <div className={styles.editorContainer}>
      <div className={styles.topBar}>
        <button type="button" className={styles.backBtn} onClick={onClose}>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          <span>Back to Report</span>
        </button>
        <span className={styles.topBarTitle}>Edit Sections</span>
        <button
          type="button"
          className={styles.exportBtn}
          onClick={handleExportDocx}
          disabled={exportingDocx || loading}
        >
          {exportingDocx ? (
            <>
              <span className={styles.spinner} />
              <span>Exporting...</span>
            </>
          ) : (
            <span>Export DOCX</span>
          )}
        </button>
      </div>

      {error && <div className={styles.errorBanner}>{error}</div>}

      {loading ? (
        <div className={styles.loadingState}>Loading sections...</div>
      ) : (
        <div className={styles.sectionsList}>
          {sections.map((section, idx) => {
            const isEditing = editingSectionId === section.id;
            const isExpanded = expandedSectionId === section.id || isEditing;
            return (
            <div key={section.id}>
              <div
                className={`${styles.sectionCard} ${!section.visible ? styles.sectionCardHidden : ''} ${isEditing ? styles.sectionCardEditing : ''}`}
              >
                <div
                  className={styles.sectionHeaderRow}
                  onClick={() => toggleExpand(section)}
                  role="button"
                  tabIndex={0}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') toggleExpand(section);
                  }}
                >
                  <span className={`${styles.chevron} ${isExpanded ? styles.chevronExpanded : ''}`}>▼</span>
                  <span className={`${styles.collapsedTitle} ${!section.visible ? styles.sectionTitleStrike : ''}`}>
                    {section.title || 'Untitled Section'}
                  </span>

                  <div className={styles.sectionCardControls} onClick={(e) => e.stopPropagation()}>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() => handleMove(idx, -1)}
                      disabled={idx === 0 || busy || isEditing}
                      title="Move up"
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() => handleMove(idx, 1)}
                      disabled={idx === sections.length - 1 || busy || isEditing}
                      title="Move down"
                    >
                      ↓
                    </button>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() => toggleVisible(section)}
                      disabled={busy || isEditing}
                      title={section.visible ? 'Hide section' : 'Show section'}
                    >
                      {section.visible ? '👁' : '👁‍🗨'}
                    </button>
                    <button
                      type="button"
                      className={styles.iconBtn}
                      onClick={() => startEditContent(section)}
                      disabled={busy || (editingSectionId !== null && editingSectionId !== section.id)}
                      title="Edit section content"
                    >
                      ✏️
                    </button>
                    <button
                      type="button"
                      className={styles.iconBtnDanger}
                      onClick={() => handleDelete(section)}
                      disabled={busy || isEditing}
                      title="Delete section"
                    >
                      🗑
                    </button>
                  </div>
                </div>

                <div className={`${styles.expandWrap} ${isExpanded ? styles.expandWrapOpen : ''}`}>
                  <div className={styles.expandInner}>
                    {isEditing ? (
                      <div className={styles.contentEditWrap}>
                        <textarea
                          ref={autoGrow}
                          className={styles.contentTextarea}
                          value={contentDraft}
                          onChange={(e) => {
                            setContentDraft(e.target.value);
                            autoGrow(e.target);
                          }}
                          autoFocus
                        />
                        <div className={styles.contentEditActions}>
                          <button type="button" className={styles.contentCancelBtn} onClick={cancelEditContent} disabled={busy}>
                            Cancel
                          </button>
                          <button
                            type="button"
                            className={styles.contentSaveBtn}
                            onClick={() => saveEditContent(section)}
                            disabled={busy || !contentDraft.trim()}
                          >
                            Save
                          </button>
                        </div>
                      </div>
                    ) : (
                      <>
                        {section.title !== null && (
                          editingTitleId === section.id ? (
                            <input
                              type="text"
                              autoFocus
                              className={styles.titleInput}
                              value={titleDraft}
                              onChange={(e) => setTitleDraft(e.target.value)}
                              onBlur={() => commitTitle(section)}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter') commitTitle(section);
                                if (e.key === 'Escape') setEditingTitleId(null);
                              }}
                            />
                          ) : (
                            <h3
                              className={`${styles.sectionTitle} ${!section.visible ? styles.sectionTitleStrike : ''}`}
                              onClick={() => {
                                setEditingTitleId(section.id);
                                setTitleDraft(section.title || '');
                              }}
                              title="Click to edit title"
                            >
                              {section.title}
                            </h3>
                          )
                        )}
                        <div className={styles.sectionPreview}>
                          <ReportRenderer content={section.content} accordion={false} />
                        </div>
                      </>
                    )}
                  </div>
                </div>
              </div>

              <AddRow
                afterOrder={section.order}
                isOpen={addFormAfterOrder === section.order}
                busy={busy}
                title={newTitle}
                content={newContent}
                onOpen={openAddForm}
                onTitleChange={setNewTitle}
                onContentChange={setNewContent}
                onCancel={() => setAddFormAfterOrder(null)}
                onSubmit={submitAddForm}
              />
            </div>
            );
          })}

          {sections.length === 0 && (
            <div className={styles.emptyState}>No sections yet.</div>
          )}
        </div>
      )}
    </div>
  );
}
