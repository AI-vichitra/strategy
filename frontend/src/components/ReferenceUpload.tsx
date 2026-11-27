'use client';
import { useRef, useState } from 'react';
import styles from './ReferenceUpload.module.css';

export interface ReferenceDoc {
  ref_id: string;
  filename: string;
}

interface ReferenceUploadProps {
  value: ReferenceDoc[];
  onChange: (docs: ReferenceDoc[]) => void;
  apiBase: string;
  authToken?: string;
  maxFiles?: number;
}

type PendingStatus = 'uploading' | 'done' | 'failed';

interface PendingItem {
  key: string;
  filename: string;
  status: PendingStatus;
  charCount?: number;
  error?: string;
  refId?: string;
}

const ALLOWED_EXTENSIONS = ['.pdf', '.docx', '.txt', '.md'];
const MAX_FILE_BYTES = 10 * 1024 * 1024;

function getExtension(filename: string): string {
  const idx = filename.lastIndexOf('.');
  return idx >= 0 ? filename.slice(idx).toLowerCase() : '';
}

function FileTypeIcon({ filename }: { filename: string }) {
  const extension = getExtension(filename);
  const isPdf = extension === '.pdf';
  const isWord = extension === '.docx';
  const color = isPdf ? '#EA4335' : isWord ? '#4285F4' : '#7B8088';
  const label = isPdf ? 'PDF' : isWord ? 'W' : 'TXT';

  return (
    <svg className={styles.itemIcon} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 2.75h8l4.5 4.5v14H6a2 2 0 0 1-2-2v-14a2 2 0 0 1 2-2Z" fill={color} />
      <path d="M14 2.75v4.5h4.5" fill="none" stroke="#fff" strokeWidth="1.3" strokeLinejoin="round" />
      <text x="12" y="16" textAnchor="middle" fill="#fff" fontSize={isWord ? '8' : '5.5'} fontWeight="700" fontFamily="Arial, sans-serif">{label}</text>
    </svg>
  );
}

export default function ReferenceUpload({ value, onChange, apiBase, authToken, maxFiles = 5 }: ReferenceUploadProps) {
  const [pending, setPending] = useState<PendingItem[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const totalCount = value.length + pending.filter((p) => p.status !== 'failed').length;

  const uploadOne = async (file: File) => {
    const key = `${file.name}-${Date.now()}-${Math.random()}`;
    const ext = getExtension(file.name);

    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setPending((prev) => [...prev, { key, filename: file.name, status: 'failed', error: 'Unsupported file type. Use PDF, DOCX, TXT, or MD.' }]);
      return;
    }
    if (file.size > MAX_FILE_BYTES) {
      setPending((prev) => [...prev, { key, filename: file.name, status: 'failed', error: 'File exceeds the 10MB size limit.' }]);
      return;
    }

    setPending((prev) => [...prev, { key, filename: file.name, status: 'uploading' }]);

    try {
      const formData = new FormData();
      formData.append('file', file);
      const headers: Record<string, string> = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${apiBase ?? ''}/api/brands/upload-reference`, {
        method: 'POST',
        headers,
        body: formData,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => null);
        setPending((prev) => prev.map((p) => (p.key === key ? { ...p, status: 'failed', error: err?.detail || 'Upload failed. Please try again.' } : p)));
        return;
      }

      const data = await res.json();
      setPending((prev) => prev.map((p) => (p.key === key ? { ...p, status: 'done', charCount: data.char_count, refId: data.ref_id } : p)));
      onChange([...value, { ref_id: data.ref_id, filename: data.filename }]);
    } catch {
      setPending((prev) => prev.map((p) => (p.key === key ? { ...p, status: 'failed', error: 'Upload failed. Please try again.' } : p)));
    }
  };

  const handleFiles = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const selected = Array.from(files);
    const room = Math.max(0, maxFiles - totalCount);
    selected.slice(0, room).forEach((file) => uploadOne(file));
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    handleFiles(e.target.files);
    e.target.value = '';
  };

  const handleRemoveConfirmed = (refId: string) => {
    onChange(value.filter((d) => d.ref_id !== refId));
  };

  const handleRemovePending = (key: string) => {
    setPending((prev) => prev.filter((p) => p.key !== key));
  };

  const atLimit = totalCount >= maxFiles;

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>Brand Documents (Optional)</div>
          <div className={styles.subtitle}>
            Upload brand decks, briefs, or style guides (.pdf, .docx, .txt, .md) to ground the research in your own material
          </div>
        </div>
        <span className={styles.counter}>
          {totalCount}/{maxFiles} documents added
        </span>
      </div>

      {(value.length > 0 || pending.length > 0) && (
        <div className={styles.itemList}>
          {value.map((doc) => (
            <div key={doc.ref_id} className={styles.item}>
              <FileTypeIcon filename={doc.filename} />
              <span className={styles.itemName}>{doc.filename}</span>
              <span className={styles.itemStatusDone}>Added</span>
              <button
                type="button"
                className={styles.removeBtn}
                onClick={() => handleRemoveConfirmed(doc.ref_id)}
                aria-label={`Remove ${doc.filename}`}
              >
                &#x2715;
              </button>
            </div>
          ))}
          {pending
            .filter((p) => p.status !== 'done')
            .map((p) => (
              <div key={p.key} className={styles.item}>
                <FileTypeIcon filename={p.filename} />
                <span className={styles.itemName}>{p.filename}</span>
                {p.status === 'uploading' && <span className={styles.spinner} aria-label="Uploading" />}
                {p.status === 'failed' && <span className={styles.itemStatusFailed}>{p.error || 'Failed'}</span>}
                <button
                  type="button"
                  className={styles.removeBtn}
                  onClick={() => handleRemovePending(p.key)}
                  aria-label={`Remove ${p.filename}`}
                >
                  &#x2715;
                </button>
              </div>
            ))}
        </div>
      )}

      {!atLimit && (
        <button type="button" className={styles.addBtn} onClick={() => fileInputRef.current?.click()}>
          + Upload Reference Document
        </button>
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.docx,.txt,.md"
        multiple
        className={styles.hiddenInput}
        onChange={handleFileInputChange}
      />
    </div>
  );
}
