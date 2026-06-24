'use client';
import { useState, useRef, useEffect } from 'react';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  value: string;
  onChange: (val: string) => void;
  showBanner: boolean;
  onRevert: () => void;
  onSubmit?: () => void;
  userContext: string;
  onChangeUserContext: (val: string) => void;
  attachedFiles: File[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
  defaultUserContextOpen?: boolean;
  onOpenConnectors?: () => void;
}

export default function ChatInput({
  value,
  onChange,
  showBanner,
  onRevert,
  onSubmit,
  userContext,
  onChangeUserContext,
  attachedFiles,
  onAddFiles,
  onRemoveFile,
  defaultUserContextOpen = false,
  onOpenConnectors,
}: ChatInputProps) {
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showUserContextBox, setShowUserContextBox] = useState(defaultUserContextOpen);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Sync when parent tells us to open user context
  useEffect(() => {
    if (defaultUserContextOpen) setShowUserContextBox(true);
  }, [defaultUserContextOpen]);

  const handleLocalSubmit = () => {
    onSubmit?.();
    setShowUserContextBox(false);
    setShowUploadMenu(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files));
      e.target.value = '';
    }
    setShowUploadMenu(false);
  };

  // Keyboard shortcut Ctrl+U / Ctrl+u
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
        e.preventDefault();
        setShowUploadMenu(true);
        // Delay slightly so layout updates, then open file explorer
        setTimeout(() => {
          fileInputRef.current?.click();
        }, 50);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handle clicking outside the upload popover to close it
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (showUploadMenu && !(e.target as HTMLElement).closest(`.${styles.uploadContainer}`)) {
        setShowUploadMenu(false);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, [showUploadMenu]);

  return (
    <div className={styles.wrapper}>
      {showBanner && (
        <div className={styles.banner}>
          Send a message to save & continue with your changes OR <button className={styles.revertLink} onClick={onRevert}>revert to original</button>
        </div>
      )}

      {/* User Context Text Area */}
      {showUserContextBox && (
        <div className={styles.contextBox}>
          <div className={styles.contextBoxHeader}>
            <span className={styles.contextBoxTitle}>USER CONTEXT</span>
            <button
              type="button"
              className={styles.contextBoxClose}
              onClick={() => setShowUserContextBox(false)}
              aria-label="Close user context"
            >
              &times;
            </button>
          </div>
          <textarea
            className={styles.contextInput}
            placeholder="Give additional context to enhance the prompt..."
            value={userContext}
            onChange={(e) => onChangeUserContext(e.target.value)}
            rows={3}
          />
        </div>
      )}

      {/* File chips row */}
      {attachedFiles.length > 0 && (
        <div className={styles.fileChipsRow}>
          {attachedFiles.map((file, idx) => (
            <div key={idx} className={styles.fileChip}>
              <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                <polyline points="14 2 14 8 20 8" />
              </svg>
              <span className={styles.fileChipName}>{file.name}</span>
              <button
                type="button"
                className={styles.fileChipRemove}
                onClick={() => onRemoveFile(idx)}
                aria-label={`Remove ${file.name}`}
              >
                &times;
              </button>
            </div>
          ))}
        </div>
      )}

      <textarea
        className={styles.input}
        placeholder="Send a message to your agent"
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            handleLocalSubmit();
          }
        }}
      ></textarea>

      <div className={styles.bottomRow}>
        <div className={styles.leftActions}>
          {/* Upload attachment wrapper */}
          <div className={styles.uploadContainer}>
            <button
              type="button"
              className={`${styles.iconBtn} ${showUploadMenu ? styles.activeIconBtn : ''}`}
              onClick={() => setShowUploadMenu(prev => !prev)}
              aria-label="Upload file"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
              </svg>
            </button>

            {showUploadMenu && (
              <div className={styles.uploadMenu}>
                <button
                  type="button"
                  className={styles.uploadMenuItem}
                  onClick={() => {
                    fileInputRef.current?.click();
                    setShowUploadMenu(false);
                  }}
                >
                  <span className={styles.uploadMenuText}>Add files or photos</span>
                  <span className={styles.uploadMenuShortcut}>Ctrl+U</span>
                </button>
              </div>
            )}

            <input
              type="file"
              multiple
              ref={fileInputRef}
              style={{ display: 'none' }}
              onChange={handleFileChange}
            />
          </div>

          {/* @ Connectors Trigger */}
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => onOpenConnectors?.()}
            aria-label="Open connectors"
          >
            <span style={{ fontSize: '16px', fontWeight: 700, lineHeight: 1 }}>@</span>
          </button>

          {/* User Context Trigger button */}
          <button
            type="button"
            className={`${styles.contextBtn} ${showUserContextBox ? styles.contextBtnActive : ''}`}
            onClick={() => setShowUserContextBox(prev => !prev)}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            User Context
          </button>
        </div>

        <div className={styles.rightActions}>
          <button className={styles.iconBtn}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
              <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
              <line x1="12" y1="19" x2="12" y2="22" />
            </svg>
          </button>

          <button className={styles.submitBtn} onClick={handleLocalSubmit}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M12 19V5M5 12l7-7 7 7" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
}
