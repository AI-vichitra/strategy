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
  onOpenAgents?: () => void;
  isInstaScraped?: boolean;
  isGenerating?: boolean;
  onStop?: () => void;
  selectedModel?: string;
  onSelectModel?: (model: string) => void;
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
  onOpenAgents,
  isInstaScraped = false,
  isGenerating = false,
  onStop,
  selectedModel = 'mistral',
  onSelectModel,
}: ChatInputProps) {
  const [showUploadMenu, setShowUploadMenu] = useState(false);
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const modelOptions = [
    { id: 'mistral', label: 'Mistral', badge: 'Active / Default' },
    { id: 'qwen', label: 'Qwen', badge: 'Fast' },
    { id: 'openai', label: 'OpenAI', badge: 'GPT-4o' },
    { id: 'anthropic', label: 'Claude', badge: 'Sonnet 4.5' },
  ];

  // Reset local isStopping when parent states update
  useEffect(() => {
    if (!isGenerating) {
      setIsStopping(false);
    }
  }, [isGenerating]);

  const handleLocalSubmit = () => {
    onSubmit?.();
    setShowUploadMenu(false);
    setShowModelMenu(false);
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
      if (showModelMenu && !(e.target as HTMLElement).closest(`.${styles.modelContainer}`)) {
        setShowModelMenu(false);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, [showUploadMenu, showModelMenu]);

  const currentModelLabel = modelOptions.find(m => m.id === selectedModel)?.label || 'Qwen';

  return (
    <div className={styles.wrapper}>

      {/* User Context Text Area (Always Open) */}
      <div className={styles.contextBox}>
        <div className={styles.contextBoxHeader}>
          <span className={styles.contextBoxTitle}>USER CONTEXT</span>
        </div>
        <textarea
          className={styles.contextInput}
          placeholder="Give additional context to enhance the prompt..."
          value={userContext}
          onChange={(e) => onChangeUserContext(e.target.value)}
          rows={1}
        />
      </div>

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
        placeholder={isGenerating ? "Streaming response..." : "Send a message to your agent"}
        rows={1}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !isGenerating) {
            e.preventDefault();
            handleLocalSubmit();
          }
        }}
        disabled={isGenerating}
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

          {/* Model Selector Dropdown */}
          <div className={styles.modelContainer}>
            <button
              type="button"
              className={`${styles.modelSelectBtn} ${showModelMenu ? styles.activeIconBtn : ''}`}
              onClick={() => setShowModelMenu(prev => !prev)}
              aria-label="Select AI Model"
            >
              <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
                <path d="M2 12h20" />
              </svg>
              <span>{currentModelLabel}</span>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {showModelMenu && (
              <div className={styles.modelMenu}>
                <div className={styles.modelMenuHeader}>MODEL PROVIDER</div>
                {modelOptions.map(m => (
                  <button
                    key={m.id}
                    type="button"
                    className={`${styles.modelMenuItem} ${selectedModel === m.id ? styles.selectedModelItem : ''}`}
                    onClick={() => {
                      onSelectModel?.(m.id);
                      setShowModelMenu(false);
                    }}
                  >
                    <div className={styles.modelMenuLeft}>
                      <span className={styles.modelMenuLabel}>{m.label}</span>
                      <span className={styles.modelMenuBadge}>{m.badge}</span>
                    </div>
                    {selectedModel === m.id && (
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D4A843" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </button>
                ))}
              </div>
            )}
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

          {/* AGENTS Trigger */}
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => onOpenAgents?.()}
            aria-label="Open agents"
            style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', minWidth: '40px', padding: '0 8px' }}
          >
            <span style={{ fontSize: '10px', fontWeight: 700, letterSpacing: '0.05em' }}>AGENTS</span>
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

          {isGenerating ? (
            <button 
              type="button"
              className={styles.stopBtn} 
              onClick={() => {
                setIsStopping(true);
                onStop?.();
              }}
              disabled={isStopping}
              aria-label="Stop generation"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="white">
                <rect x="4" y="4" width="16" height="16" rx="2" />
              </svg>
            </button>
          ) : (
            <button className={styles.submitBtn} onClick={handleLocalSubmit}>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 19V5M5 12l7-7 7 7" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
