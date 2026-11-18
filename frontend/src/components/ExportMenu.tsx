'use client';
import { useEffect, useRef, useState } from 'react';
import styles from './ExportMenu.module.css';

export interface ExportTemplateOption {
  id: string;
  name: string;
  description: string;
}

export interface ExportFormatConfig {
  id: string;
  label: string;       // "PDF" / "Word" / "PowerPoint"
  extension: string;   // ".pdf" / ".docx" / ".pptx"
  chip: string;         // short glyph shown in the row, e.g. "PDF" / "DOC" / "PPT"
  onSelect: () => void;
  loading: boolean;
  error?: boolean;
  // When provided (non-empty) alongside onSelectTemplate, the row expands
  // into a submenu listing these templates instead of calling onSelect
  // directly — the registry's own first entry is already "Default".
  templates?: ExportTemplateOption[];
  onSelectTemplate?: (templateId: string) => void;
}

interface ExportMenuProps {
  formats: ExportFormatConfig[];
  buttonClassName?: string;
}

export default function ExportMenu({ formats, buttonClassName }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [flyoutSide, setFlyoutSide] = useState<'right' | 'left'>('right');
  const containerRef = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);
  const wasLoadingRef = useRef(false);

  // Viewport guard: a right-opening flyout would run past the edge of the
  // screen, so open it to the left instead when there isn't room.
  const ESTIMATED_FLYOUT_WIDTH = 200;
  const pickFlyoutSide = (): 'right' | 'left' => {
    const rect = menuRef.current?.getBoundingClientRect();
    if (!rect) return 'right';
    const gap = 6;
    return rect.right + gap + ESTIMATED_FLYOUT_WIDTH > window.innerWidth ? 'left' : 'right';
  };

  const anyLoading = formats.some((f) => f.loading);
  const anyError = formats.some((f) => f.error);

  // Closing the menu (for any reason) always collapses the template
  // submenu too, so reopening never shows a stale expanded row.
  const closeMenu = () => {
    setOpen(false);
    setExpandedId(null);
  };

  // Close automatically once a download finishes without erroring.
  useEffect(() => {
    if (wasLoadingRef.current && !anyLoading && !anyError) {
      closeMenu();
    }
    wasLoadingRef.current = anyLoading;
  }, [anyLoading, anyError]);

  useEffect(() => {
    if (!open) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        closeMenu();
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        closeMenu();
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1) % formats.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => (prev - 1 + formats.length) % formats.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const fmt = formats[activeIndex];
        if (!fmt || fmt.loading) return;
        if (fmt.templates?.length && fmt.onSelectTemplate) {
          setFlyoutSide(pickFlyoutSide());
          setExpandedId((prev) => (prev === fmt.id ? null : fmt.id));
        } else {
          fmt.onSelect();
        }
      }
    };

    document.addEventListener('mousedown', handleOutsideClick);
    document.addEventListener('keydown', handleKeyDown);
    return () => {
      document.removeEventListener('mousedown', handleOutsideClick);
      document.removeEventListener('keydown', handleKeyDown);
    };
  }, [open, formats, activeIndex]);

  const toggle = () => {
    setOpen((prev) => !prev);
    setActiveIndex(0);
    setExpandedId(null);
  };

  const handleRowClick = (fmt: ExportFormatConfig) => {
    if (fmt.loading) return;
    if (fmt.templates?.length && fmt.onSelectTemplate) {
      setFlyoutSide(pickFlyoutSide());
      setExpandedId((prev) => (prev === fmt.id ? null : fmt.id));
    } else {
      fmt.onSelect();
    }
  };

  const handleTemplateSelect = (fmt: ExportFormatConfig, templateId: string) => {
    setExpandedId(null);
    fmt.onSelectTemplate?.(templateId);
  };

  return (
    <div className={styles.container} ref={containerRef}>
      <button
        type="button"
        className={buttonClassName}
        onClick={toggle}
        aria-haspopup="menu"
        aria-expanded={open}
        title="Export report"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
          <polyline points="7 10 12 15 17 10" />
          <line x1="12" y1="15" x2="12" y2="3" />
        </svg>
        <span>Export</span>
        <svg
          width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
          strokeLinecap="round" strokeLinejoin="round"
          className={`${styles.chevron} ${open ? styles.chevronOpen : ''}`}
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>

      {open && (
        <div className={styles.menu} role="menu" ref={menuRef}>
          {formats.map((fmt, idx) => {
            const hasTemplates = !!(fmt.templates?.length && fmt.onSelectTemplate);
            const isExpanded = hasTemplates && expandedId === fmt.id;
            return (
              <div key={fmt.id} className={styles.menuItemWrap}>
                <button
                  type="button"
                  role="menuitem"
                  aria-haspopup={hasTemplates ? 'menu' : undefined}
                  aria-expanded={hasTemplates ? isExpanded : undefined}
                  className={`${styles.menuRow} ${idx === activeIndex ? styles.menuRowActive : ''}`}
                  onMouseEnter={() => setActiveIndex(idx)}
                  onClick={() => handleRowClick(fmt)}
                  disabled={fmt.loading}
                >
                  <span className={styles.formatChip}>{fmt.chip}</span>
                  <span className={styles.formatInfo}>
                    <span className={styles.formatLabel}>{fmt.label}</span>
                    <span className={styles.formatExt}>{fmt.extension}</span>
                  </span>
                  {fmt.loading ? (
                    <span className={styles.rowSpinner} aria-label="Exporting" />
                  ) : fmt.error ? (
                    <span className={styles.rowError}>Failed</span>
                  ) : hasTemplates ? (
                    <svg
                      width="9" height="9" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3"
                      strokeLinecap="round" strokeLinejoin="round" className={styles.templateCaret}
                    >
                      <polyline points="9 6 15 12 9 18" />
                    </svg>
                  ) : null}
                </button>

                {isExpanded && (
                  <div
                    className={`${styles.templateFlyout} ${flyoutSide === 'left' ? styles.templateFlyoutLeft : ''}`}
                    role="menu"
                  >
                    {fmt.templates!.map((tpl) => (
                      <button
                        key={tpl.id}
                        type="button"
                        role="menuitem"
                        className={styles.templateRow}
                        onClick={() => handleTemplateSelect(fmt, tpl.id)}
                        title={tpl.description || tpl.name}
                      >
                        {tpl.name}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
