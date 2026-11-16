'use client';
import { useEffect, useRef, useState } from 'react';
import styles from './ExportMenu.module.css';

export interface ExportFormatConfig {
  id: string;
  label: string;       // "PDF" / "Word" / "PowerPoint"
  extension: string;   // ".pdf" / ".docx" / ".pptx"
  chip: string;         // short glyph shown in the row, e.g. "PDF" / "DOC" / "PPT"
  onSelect: () => void;
  loading: boolean;
  error?: boolean;
}

interface ExportMenuProps {
  formats: ExportFormatConfig[];
  buttonClassName?: string;
}

export default function ExportMenu({ formats, buttonClassName }: ExportMenuProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);
  const wasLoadingRef = useRef(false);

  const anyLoading = formats.some((f) => f.loading);
  const anyError = formats.some((f) => f.error);

  // Close automatically once a download finishes without erroring.
  useEffect(() => {
    if (wasLoadingRef.current && !anyLoading && !anyError) {
      setOpen(false);
    }
    wasLoadingRef.current = anyLoading;
  }, [anyLoading, anyError]);

  useEffect(() => {
    if (!open) return;

    const handleOutsideClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setOpen(false);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        setActiveIndex((prev) => (prev + 1) % formats.length);
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        setActiveIndex((prev) => (prev - 1 + formats.length) % formats.length);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const fmt = formats[activeIndex];
        if (fmt && !fmt.loading) fmt.onSelect();
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
        <div className={styles.menu} role="menu">
          {formats.map((fmt, idx) => (
            <button
              key={fmt.id}
              type="button"
              role="menuitem"
              className={`${styles.menuRow} ${idx === activeIndex ? styles.menuRowActive : ''}`}
              onMouseEnter={() => setActiveIndex(idx)}
              onClick={() => !fmt.loading && fmt.onSelect()}
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
              ) : null}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
