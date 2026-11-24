'use client';
import { useEffect, useRef, useState } from 'react';
import styles from './BrandKitForm.module.css';

export interface BrandColors {
  primary?: string;
  secondary?: string;
}

export interface BrandKit {
  logo_url?: string;
  colors?: BrandColors;
}

interface BrandKitFormProps {
  brandKit: BrandKit;
  onChange: (bk: BrandKit) => void;
  apiBase: string | undefined;
  authToken?: string;
}

const ALLOWED_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/svg+xml', 'image/webp'];
const MAX_LOGO_BYTES = 2 * 1024 * 1024;

const COLOR_FIELDS: { key: keyof BrandColors; label: string; fallback: string }[] = [
  { key: 'primary', label: 'Primary', fallback: '#D4A843' },
  { key: 'secondary', label: 'Secondary', fallback: '#6B6560' },
];
// Accent is backend-managed (extracted from the logo when vivid, otherwise
// derived from primary at export time) — not a user-settable field here.

const HEX_RE = /^#([0-9a-fA-F]{3}|[0-9a-fA-F]{6})$/;

function normalizeHex(value: string): string | null {
  if (!HEX_RE.test(value)) return null;
  let hex = value.slice(1);
  if (hex.length === 3) {
    hex = hex.split('').map((c) => c + c).join('');
  }
  return `#${hex.toUpperCase()}`;
}

export default function BrandKitForm({ brandKit, onChange, apiBase, authToken }: BrandKitFormProps) {
  const safeBrandKit = brandKit ?? {};
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const [colorDrafts, setColorDrafts] = useState<BrandColors>(safeBrandKit.colors ?? {});
  // Which color fields currently hold a logo-derived value rather than
  // something the user typed/picked themselves — lets a new upload safely
  // refresh only the still-auto-filled fields, and lets removing the logo
  // clear only those, never a manual edit.
  const [autoFilled, setAutoFilled] = useState<Partial<Record<keyof BrandColors, boolean>>>({});
  const [paletteHint, setPaletteHint] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    setColorDrafts(safeBrandKit.colors ?? {});
  }, [safeBrandKit.colors]);

  const commitColor = (key: keyof BrandColors, value: string | undefined) => {
    const nextColors: BrandColors = { ...(safeBrandKit.colors ?? {}) };
    if (value) {
      nextColors[key] = value;
    } else {
      delete nextColors[key];
    }
    const hasAny = Object.values(nextColors).some(Boolean);
    onChange({ ...safeBrandKit, colors: hasAny ? nextColors : undefined });
  };

  // A direct edit always makes the field the user's own — it stops being
  // something a future logo upload is allowed to overwrite.
  const markManual = (key: keyof BrandColors) => {
    setAutoFilled((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  };

  const handleColorTextChange = (key: keyof BrandColors, value: string) => {
    setColorDrafts((prev) => ({ ...prev, [key]: value }));
    markManual(key);
    if (value.trim() === '') {
      commitColor(key, undefined);
      return;
    }
    const normalized = normalizeHex(value.trim());
    if (normalized) commitColor(key, normalized);
  };

  const handleSwatchChange = (key: keyof BrandColors, value: string) => {
    const normalized = normalizeHex(value) || value.toUpperCase();
    setColorDrafts((prev) => ({ ...prev, [key]: normalized }));
    markManual(key);
    commitColor(key, normalized);
  };

  const uploadLogo = async (file: File) => {
    setUploadError(null);
    setPaletteHint(false);
    if (!ALLOWED_TYPES.includes(file.type)) {
      setUploadError('Unsupported file type. Use PNG, JPEG, SVG, or WebP.');
      return;
    }
    if (file.size > MAX_LOGO_BYTES) {
      setUploadError('Logo must be under 2MB.');
      return;
    }

    setUploading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const headers: Record<string, string> = {};
      if (authToken) headers['Authorization'] = `Bearer ${authToken}`;

      const res = await fetch(`${apiBase ?? ''}/api/projects/upload-logo`, {
        method: 'POST',
        headers,
        body: formData,
      });
      if (!res.ok) {
        const err = await res.json().catch(() => null);
        setUploadError(err?.detail || 'Upload failed. Please try again.');
        return;
      }
      const data = await res.json();
      const palette = data.palette ?? {};

      // Re-extract primary/secondary for THIS logo, refreshing any field that
      // isn't a manual user edit — a field previously auto-filled from a
      // different logo gets overwritten (or cleared, if this logo doesn't
      // yield that color), instead of silently keeping the old logo's value.
      // Only primary/secondary are user-settable; accent (which the backend
      // may still include in `palette`) is intentionally ignored here — it's
      // resolved server-side at export time instead.
      const nextColors: BrandColors = { ...(safeBrandKit.colors ?? {}) };
      const nextAutoFilled: Partial<Record<keyof BrandColors, boolean>> = { ...autoFilled };
      (['primary', 'secondary'] as const).forEach((key) => {
        if (!autoFilled[key] && (colorDrafts[key] ?? '').trim() !== '') return; // manual edit — leave it

        const extracted: string | undefined = palette[key];
        if (extracted) {
          nextColors[key] = extracted.startsWith('#') ? extracted : `#${extracted}`;
          nextAutoFilled[key] = true;
        } else {
          delete nextColors[key];
          delete nextAutoFilled[key];
        }
      });

      const hasAnyColor = Object.values(nextColors).some(Boolean);
      const nextBrandKit: BrandKit = {
        ...safeBrandKit,
        logo_url: data.logo_url,
        colors: hasAnyColor ? nextColors : undefined,
      };

      setColorDrafts(nextColors);
      setAutoFilled(nextAutoFilled);
      setPaletteHint(Object.keys(nextAutoFilled).length > 0);

      onChange(nextBrandKit);
    } catch {
      setUploadError('Upload failed. Please try again.');
    } finally {
      setUploading(false);
    }
  };

  const handleFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) uploadLogo(file);
    e.target.value = '';
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    const file = e.dataTransfer.files?.[0];
    if (file) uploadLogo(file);
  };

  const handleRemoveLogo = () => {
    const { logo_url, ...rest } = safeBrandKit;
    // Drop the colors that came FROM this logo so the next upload starts
    // clean; a color the user manually set (not in `autoFilled`) survives.
    const remainingColors: BrandColors = { ...(rest.colors ?? {}) };
    (['primary', 'secondary'] as const).forEach((key) => {
      if (autoFilled[key]) delete remainingColors[key];
    });
    const hasAnyColor = Object.values(remainingColors).some(Boolean);

    setColorDrafts(remainingColors);
    setAutoFilled({});
    setPaletteHint(false);
    onChange({ ...rest, colors: hasAnyColor ? remainingColors : undefined });
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>Brand Kit (Optional)</div>
          <div className={styles.subtitle}>
            Add the client&apos;s logo and brand colors to theme the exported report, or skip to use default styling
          </div>
        </div>
      </div>

      <div className={styles.body}>
        <div className={styles.logoColumn}>
          <label className={styles.fieldLabel}>Logo</label>
          {safeBrandKit.logo_url ? (
            <div className={styles.logoPreviewWrap}>
              <img
                src={`${apiBase ?? ''}${safeBrandKit.logo_url}`}
                alt="Brand logo"
                className={styles.logoPreview}
              />
              <button
                type="button"
                className={styles.removeBtn}
                onClick={handleRemoveLogo}
                aria-label="Remove logo"
              >
                &#x2715;
              </button>
            </div>
          ) : (
            <div
              className={`${styles.dropzone} ${dragOver ? styles.dropzoneActive : ''}`}
              onClick={() => fileInputRef.current?.click()}
              onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
              onDragLeave={() => setDragOver(false)}
              onDrop={handleDrop}
            >
              {uploading ? (
                <span className={styles.spinner} aria-label="Uploading" />
              ) : (
                <span className={styles.dropzoneText}>+ Upload Logo</span>
              )}
            </div>
          )}
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/svg+xml,image/webp"
            className={styles.hiddenInput}
            onChange={handleFileInputChange}
          />
          {uploadError && <div className={styles.errorText}>{uploadError}</div>}
        </div>

        <div className={styles.colorColumn}>
          <label className={styles.fieldLabel}>Brand Colors</label>
          <div className={styles.colorRow}>
            {COLOR_FIELDS.map(({ key, label, fallback }) => {
              const draft = colorDrafts[key] ?? '';
              const swatchValue = normalizeHex(draft) || fallback;
              return (
                <div className={styles.colorField} key={key}>
                  <span className={styles.colorFieldLabel}>{label}</span>
                  <div className={styles.colorInputRow}>
                    <input
                      type="color"
                      className={styles.swatch}
                      value={swatchValue}
                      onChange={(e) => handleSwatchChange(key, e.target.value)}
                    />
                    <input
                      type="text"
                      className={styles.input}
                      placeholder={fallback}
                      value={draft}
                      onChange={(e) => handleColorTextChange(key, e.target.value)}
                    />
                  </div>
                </div>
              );
            })}
          </div>
          {paletteHint && (
            <div className={styles.paletteHint}>
              <span>Colors auto-filled from your logo</span>
              <button
                type="button"
                className={styles.paletteHintDismiss}
                onClick={() => setPaletteHint(false)}
                aria-label="Dismiss"
              >
                &#x2715;
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
