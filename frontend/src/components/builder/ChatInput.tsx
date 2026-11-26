'use client';
import { useState, useRef, useEffect } from 'react';
import VoiceInput from './VoiceInput';
import FileIcon from '../FileIcon';
import styles from './ChatInput.module.css';

interface ChatInputProps {
  value: string;
  onChange: (val: string) => void;
  showBanner: boolean;
  onRevert: () => void;
  onSubmit?: () => void;
  attachedFiles: File[];
  onAddFiles: (files: File[]) => void;
  onRemoveFile: (index: number) => void;
  onOpenConnectors?: () => void;
  onOpenTemplates?: () => void;
  isInstaScraped?: boolean;
  isGenerating?: boolean;
  onStop?: () => void;
  selectedModel?: string;
  onSelectModel?: (model: string) => void;
  providers?: { id: string; display_name: string; configured: boolean; model: string }[];
  advancedPin?: string | null;
  providerNote?: string;
}

const OpenAILogo = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" style={{ flexShrink: 0 }}>
    <path d="M22.2819 9.8211a5.9847 5.9847 0 0 0-.5157-4.9108 6.0462 6.0462 0 0 0-6.5098-2.9A6.0651 6.0651 0 0 0 4.9807 4.1818a5.9847 5.9847 0 0 0-3.9977 2.9 6.0462 6.0462 0 0 0 .7427 7.0966 5.98 5.98 0 0 0 .511 4.9107 6.051 6.051 0 0 0 6.5146 2.9001A5.9847 5.9847 0 0 0 13.2599 24a6.0557 6.0557 0 0 0 5.7718-4.2058 5.9894 5.9894 0 0 0 3.9977-2.9001 6.0557 6.0557 0 0 0-.7475-7.0729zm-9.022 12.6081a4.4755 4.4755 0 0 1-2.8764-1.0408l.1419-.0804 4.7783-2.7582a.7948.7948 0 0 0 .3927-.6813v-6.7369l2.02 1.1686a.071.071 0 0 1 .038.052v5.5826a4.5045 4.5045 0 0 1-4.4945 4.4944zm-9.6607-4.1254a4.4708 4.4708 0 0 1-.5346-3.0137l.142.0852 4.783 2.7582a.7712.7712 0 0 0 .7806 0l5.8428-3.3685v2.3324a.0804.0804 0 0 1-.0332.0615L9.74 19.9502a4.4992 4.4992 0 0 1-6.1408-1.6464zM2.3408 7.8956a4.485 4.485 0 0 1 2.3655-1.9728V11.6a.7664.7664 0 0 0 .3879.6765l5.8144 3.3543-2.0201 1.1685a.0757.0757 0 0 1-.071 0l-4.8303-2.7865A4.504 4.504 0 0 1 2.3408 7.872zm16.5963 3.8558L13.1038 8.364 15.1192 7.2a.0757.0757 0 0 1 .071 0l4.8303 2.7913a4.4944 4.4944 0 0 1-.6765 8.1042v-5.6772a.79.79 0 0 0-.407-.6669zm2.0107-3.0231l-.142-.0852-4.7735-2.7818a.7759.7759 0 0 0-.7854 0L9.409 9.2297V6.8974a.0662.0662 0 0 1 .0284-.0615l4.8303-2.7866a4.4992 4.4992 0 0 1 6.6802 4.66zM8.3065 12.863l-2.02-1.1638a.0804.0804 0 0 1-.038-.0567V6.0742a4.4992 4.4992 0 0 1 7.3757-3.4537l-.142.0805L8.704 5.4593a.7948.7948 0 0 0-.3927.6813zm1.1458-1.6761l3.076-1.7755 3.076 1.7755v3.551l-3.076 1.7755-3.076-1.7755z" />
  </svg>
);

const GroqLogo = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="44 48 112 112" fill="none" style={{ flexShrink: 0 }}>
    <path fill="#F54F35" d="m128 49 1.895 1.52C136.336 56.288 140.602 64.49 142 73c.097 1.823.148 3.648.161 5.474l.03 3.247.012 3.482.017 3.613c.01 2.522.016 5.044.02 7.565.01 3.84.041 7.68.072 11.521.007 2.455.012 4.91.016 7.364l.038 3.457c-.033 11.717-3.373 21.83-11.475 30.547-4.552 4.23-9.148 7.372-14.891 9.73l-2.387 1.055c-9.275 3.355-20.3 2.397-29.379-1.13-5.016-2.38-9.156-5.17-13.234-8.925 3.678-4.526 7.41-8.394 12-12l3.063 2.375c5.572 3.958 11.135 5.211 17.937 4.625 6.96-1.384 12.455-4.502 17-10 4.174-6.784 4.59-12.222 4.531-20.094l.012-3.473c.003-2.414-.005-4.827-.022-7.241-.02-3.68 0-7.36.026-11.04-.003-2.353-.008-4.705-.016-7.058l.025-3.312c-.098-7.996-1.732-13.21-6.681-19.47-6.786-5.458-13.105-8.211-21.914-7.792-7.327 1.188-13.278 4.7-17.777 10.601C75.472 72.012 73.86 78.07 75 85c2.191 7.547 5.019 13.948 12 18 5.848 3.061 10.892 3.523 17.438 3.688l2.794.103c2.256.082 4.512.147 6.768.209v16c-16.682.673-29.615.654-42.852-10.848-8.28-8.296-13.338-19.55-13.71-31.277.394-9.87 3.93-17.894 9.562-25.875l1.688-2.563C84.698 35.563 110.05 34.436 128 49Z"/>
  </svg>
);

const ClaudeLogo = ({ size = 16 }: { size?: number }) => (
  <svg width={size} height={size} viewBox="0 0 24 24" fill="none" style={{ flexShrink: 0 }}>
    <path
      fillRule="evenodd"
      clipRule="evenodd"
      d="M13.827 3.52h3.603L24 20.48h-3.603l-1.99-4.897H11.53l-1.99 4.897H5.937L12.44 3.52h1.387zm1.387 8.76l-2.484-6.11h-.082l-2.484 6.11h5.05zM0 20.48h3.603L10.113 3.52H6.51L0 20.48z"
      fill="#D97757"
    />
  </svg>
);

const ProviderLogo = ({ providerId, size = 16 }: { providerId?: string; size?: number }) => {
  const pid = (providerId || '').toLowerCase();
  if (pid === 'openai') {
    return <OpenAILogo size={size} />;
  }
  if (pid === 'groq') {
    return <GroqLogo size={size} />;
  }
  if (pid === 'anthropic' || pid === 'claude') {
    return <ClaudeLogo size={size} />;
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" style={{ flexShrink: 0 }}>
      <circle cx="12" cy="12" r="10" />
      <path d="M12 2a14.5 14.5 0 0 0 0 20 14.5 14.5 0 0 0 0-20" />
      <path d="M2 12h20" />
    </svg>
  );
};

export default function ChatInput({
  value,
  onChange,
  showBanner,
  onRevert,
  onSubmit,
  attachedFiles,
  onAddFiles,
  onRemoveFile,
  onOpenConnectors,
  onOpenTemplates,
  isInstaScraped = false,
  isGenerating = false,
  onStop,
  selectedModel = '',
  onSelectModel,
  providers,
  advancedPin,
  providerNote,
}: ChatInputProps) {
  const [showModelMenu, setShowModelMenu] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isVoiceRecording, setIsVoiceRecording] = useState(false);
  const voiceInitialTextRef = useRef('');
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Built from the backend /api/chat/providers response — never hardcoded.
  // Each option's badge is the REAL resolved model; a provider with no key is
  // shown disabled with a reason and is not selectable (never "Active/Default").
  const modelOptions = (providers ?? [])
    .filter(p => p.id !== 'mistral' && p.id !== 'qwen')
    .map(p => ({
      id: p.id,
      label: p.display_name,
      badge: p.configured ? p.model : 'No key configured',
      configured: p.configured,
    }));

  // Auto-resize textarea to fit content between min-height (80px) and max-height (240px)
  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = 'auto';
      const scrollHeight = textareaRef.current.scrollHeight;
      if (scrollHeight > 80) {
        textareaRef.current.style.height = `${Math.min(scrollHeight, 240)}px`;
      }
    }
  }, [value]);

  // Reset local isStopping when parent states update
  useEffect(() => {
    if (!isGenerating) {
      setIsStopping(false);
    }
  }, [isGenerating]);

  const handleLocalSubmit = () => {
    onSubmit?.();
    setShowModelMenu(false);
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      onAddFiles(Array.from(e.target.files));
      e.target.value = '';
    }
  };

  // Keyboard shortcut Ctrl+U / Ctrl+u to open file picker directly
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'u') {
        e.preventDefault();
        fileInputRef.current?.click();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Handle clicking outside the model popover to close it
  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (showModelMenu && !(e.target as HTMLElement).closest(`.${styles.modelContainer}`)) {
        setShowModelMenu(false);
      }
    };
    document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, [showModelMenu]);

  const currentModelLabel = modelOptions.find(m => m.id === selectedModel)?.label || 'Model';
  const pinnedLabel = advancedPin ? (modelOptions.find(m => m.id === advancedPin)?.label || advancedPin) : null;

  // ── Paste handler: images, files, large text ────────────────────────────
  const handlePaste = (e: React.ClipboardEvent<HTMLTextAreaElement>) => {
    const { clipboardData } = e;
    if (!clipboardData) return;

    // 1. Files from clipboard (images, PDFs, etc.)
    const pastedFiles: File[] = [];
    if (clipboardData.files && clipboardData.files.length > 0) {
      Array.from(clipboardData.files).forEach(file => pastedFiles.push(file));
    } else if (clipboardData.items) {
      Array.from(clipboardData.items).forEach(item => {
        if (item.kind === 'file') {
          const f = item.getAsFile();
          if (f) pastedFiles.push(f);
        }
      });
    }

    if (pastedFiles.length > 0) {
      e.preventDefault();
      // Rename image files with timestamp for uniqueness
      const renamedFiles = pastedFiles.map(f => {
        if (f.type.startsWith('image/')) {
          const ext = f.type.split('/')[1] || 'png';
          const name = `pasted-image-${Date.now()}.${ext}`;
          return new File([f], name, { type: f.type });
        }
        return f;
      });
      onAddFiles(renamedFiles);
      return;
    }

    // 2. Large pasted text → "Pasted content" document card
    const text = clipboardData.getData('text/plain');
    if (text && (text.length >= 3500 || text.split('\n').length >= 45)) {
      e.preventDefault();
      const blob = new Blob([text], { type: 'text/plain' });
      const pastedFile = new File([blob], 'Pasted content.txt', { type: 'text/plain' });
      Object.defineProperty(pastedFile, '__isPastedText', { value: true });
      onAddFiles([pastedFile]);
      return;
    }
    // 3. Normal short text — let the browser handle it (default behavior)
  };

  return (
    <div className={styles.wrapper}>

      {/* File chips row */}
      {attachedFiles.length > 0 && (
        <div className={styles.fileChipsRow}>
          {attachedFiles.map((file, idx) => {
            const isImage = file.type.startsWith('image/');
            const isPastedText = (file as any).__isPastedText === true;
            const objUrl = isImage ? URL.createObjectURL(file) : null;
            return isImage ? (
              <div key={idx} className={styles.fileChipImg} title={file.name}>
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src={objUrl!} alt={file.name} className={styles.fileChipThumb} onLoad={() => { if (objUrl) URL.revokeObjectURL(objUrl); }} />
                <button type="button" className={styles.fileChipRemoveImg} onClick={() => onRemoveFile(idx)} aria-label={`Remove ${file.name}`}>&times;</button>
              </div>
            ) : isPastedText ? (
              <div key={idx} className={styles.fileChipPasted} title={file.name}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                <span className={styles.fileChipName}>{file.name}</span>
                <button type="button" className={styles.fileChipRemove} onClick={() => onRemoveFile(idx)} aria-label={`Remove ${file.name}`}>&times;</button>
              </div>
            ) : (
              <div key={idx} className={styles.fileChip}>
                <FileIcon filename={file.name} mimeType={file.type} size={14} />
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
            );
          })}
        </div>
      )}


      <textarea
        ref={textareaRef}
        className={styles.input}
        placeholder={
          isGenerating
            ? "Streaming response..."
            : isVoiceRecording
            ? "Listening... (speak now)"
            : "Send a message to your agent"
        }
        rows={3}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onPaste={handlePaste}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && !e.shiftKey && !isGenerating && !isVoiceRecording) {
            e.preventDefault();
            handleLocalSubmit();
          }
        }}
        disabled={isGenerating}
      ></textarea>

      <div className={styles.bottomRow}>
        <div className={styles.leftActions}>
          {/* Direct File Upload Trigger */}
          <button
            type="button"
            className={styles.iconBtn}
            onClick={() => fileInputRef.current?.click()}
            aria-label="Upload file"
            title="Upload files or photos (Ctrl+U)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
            </svg>
          </button>

          <input
            type="file"
            multiple
            ref={fileInputRef}
            style={{ display: 'none' }}
            onChange={handleFileChange}
          />

          {/* Model Selector Dropdown */}
          <div className={styles.modelContainer}>
            <button
              type="button"
              className={`${styles.modelSelectBtn} ${showModelMenu ? styles.activeIconBtn : ''}`}
              onClick={() => setShowModelMenu(prev => !prev)}
              aria-label="Select AI Model"
            >
              <span className={styles.modelTriggerIcon}>
                <ProviderLogo providerId={selectedModel} size={16} />
              </span>
              <span>{currentModelLabel}</span>
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>

            {showModelMenu && (
              <div className={styles.modelMenu}>
                <div className={styles.modelMenuHeader}>MODEL PROVIDER</div>
                {providerNote && (
                  <div className={styles.modelMenuHeader} style={{ textTransform: 'none', whiteSpace: 'normal', lineHeight: 1.3 }}>
                    {providerNote}
                  </div>
                )}
                {modelOptions.length === 0 && (
                  <div className={styles.modelMenuHeader} style={{ textTransform: 'none' }}>Loading providers…</div>
                )}
                {modelOptions.map(m => {
                  const disabled = !m.configured;
                  const isPinned = advancedPin === m.id;
                  return (
                    <button
                      key={m.id}
                      type="button"
                      disabled={disabled}
                      title={disabled ? 'No API key configured for this provider' : undefined}
                      className={`${styles.modelMenuItem} ${selectedModel === m.id ? styles.selectedModelItem : ''}`}
                      style={disabled ? { opacity: 0.45, cursor: 'not-allowed' } : undefined}
                      onClick={() => {
                        if (disabled) return;
                        onSelectModel?.(m.id);
                        setShowModelMenu(false);
                      }}
                    >
                      <div className={styles.modelMenuItemContent}>
                        <div className={styles.providerLogoWrap}>
                          <ProviderLogo providerId={m.id} size={20} />
                        </div>
                        <div className={styles.modelMenuLeft}>
                          <span className={styles.modelMenuLabel}>
                            {m.label}{isPinned ? ' · pinned' : ''}
                          </span>
                          <span className={styles.modelMenuBadge}>{m.badge}</span>
                        </div>
                      </div>
                      {selectedModel === m.id && !disabled && (
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="#D4A843" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      )}
                    </button>
                  );
                })}
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
        </div>

        <div className={styles.rightActions}>
          <VoiceInput
            disabled={isGenerating}
            onRecordingChange={(recording) => {
              setIsVoiceRecording(recording);
              if (recording) {
                voiceInitialTextRef.current = value;
              }
            }}
            onLiveTranscript={(liveText) => {
              const prefix = voiceInitialTextRef.current ? voiceInitialTextRef.current.trim() + ' ' : '';
              onChange(prefix + liveText);
              if (textareaRef.current) {
                textareaRef.current.scrollTop = textareaRef.current.scrollHeight;
              }
            }}
            onTranscript={(finalText) => {
              const prefix = voiceInitialTextRef.current ? voiceInitialTextRef.current.trim() + ' ' : '';
              if (finalText) {
                onChange(prefix + finalText);
              }
              setTimeout(() => {
                textareaRef.current?.focus();
              }, 80);
            }}
            onCancel={() => {
              onChange(voiceInitialTextRef.current);
              setTimeout(() => {
                textareaRef.current?.focus();
              }, 80);
            }}
          />

          {!isVoiceRecording && (
            isGenerating ? (
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
              <button className={styles.submitBtn} onClick={handleLocalSubmit} aria-label="Send message">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="white" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 19V5M5 12l7-7 7 7" />
                </svg>
              </button>
            )
          )}
        </div>
      </div>
    </div>
  );
}
