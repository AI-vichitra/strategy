'use client';
import { useEffect, useRef, useState } from 'react';
import styles from './CompetitorForm.module.css';

export interface CompetitorSocialMedia {
  linkedin?: string;
  instagram?: string;
  facebook?: string;
  twitter?: string;
  youtube?: string;
}

export interface CompetitorDetail {
  brand_name: string;
  website_url?: string;
  social_media?: CompetitorSocialMedia;
}

interface CompetitorFormProps {
  competitors: CompetitorDetail[];
  onChange: (competitors: CompetitorDetail[]) => void;
  maxCompetitors?: number;
}

const SOCIAL_FIELDS: { key: keyof CompetitorSocialMedia; label: string; placeholder: string }[] = [
  { key: 'linkedin', label: 'LinkedIn', placeholder: 'https://linkedin.com/company/...' },
  { key: 'instagram', label: 'Instagram', placeholder: 'https://instagram.com/...' },
  { key: 'facebook', label: 'Facebook', placeholder: 'https://facebook.com/...' },
  { key: 'twitter', label: 'Twitter/X', placeholder: 'https://x.com/...' },
  { key: 'youtube', label: 'YouTube', placeholder: 'https://youtube.com/@...' },
];

function CompetitorCard({
  competitor,
  index,
  onUpdate,
  onRemove,
  autoFocus,
}: {
  competitor: CompetitorDetail;
  index: number;
  onUpdate: (next: CompetitorDetail) => void;
  onRemove: () => void;
  autoFocus: boolean;
}) {
  const [socialOpen, setSocialOpen] = useState(false);
  const nameRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (autoFocus) nameRef.current?.focus();
  }, [autoFocus]);

  const hasOtherFields =
    !!competitor.website_url ||
    Object.values(competitor.social_media || {}).some((v) => !!v);
  const nameInvalid = hasOtherFields && !competitor.brand_name.trim();

  const updateSocial = (key: keyof CompetitorSocialMedia, value: string) => {
    onUpdate({
      ...competitor,
      social_media: { ...competitor.social_media, [key]: value },
    });
  };

  return (
    <div className={styles.competitorCard}>
      <button
        type="button"
        className={styles.removeBtn}
        onClick={onRemove}
        aria-label={`Remove competitor ${index + 1}`}
      >
        &#x2715;
      </button>

      <div className={styles.fieldRow}>
        <label className={styles.fieldLabel}>Brand Name</label>
        <input
          ref={nameRef}
          type="text"
          className={`${styles.input} ${nameInvalid ? styles.inputInvalid : ''}`}
          placeholder="e.g. WPP"
          value={competitor.brand_name}
          onChange={(e) => onUpdate({ ...competitor, brand_name: e.target.value })}
        />
      </div>

      <div className={styles.fieldRow}>
        <label className={styles.fieldLabel}>Website URL</label>
        <input
          type="text"
          className={styles.input}
          placeholder="https://www.example.com"
          value={competitor.website_url || ''}
          onChange={(e) => onUpdate({ ...competitor, website_url: e.target.value })}
        />
      </div>

      <div className={styles.socialSection}>
        <button
          type="button"
          className={styles.socialToggle}
          onClick={() => setSocialOpen((v) => !v)}
          aria-expanded={socialOpen}
        >
          <span className={`${styles.socialChevron} ${socialOpen ? styles.socialChevronOpen : ''}`}>&#9656;</span>
          Social Media Links
        </button>
        <div className={`${styles.socialWrap} ${socialOpen ? styles.socialWrapOpen : ''}`}>
          <div className={styles.socialInner}>
            {SOCIAL_FIELDS.map(({ key, label, placeholder }) => (
              <div className={styles.fieldRow} key={key}>
                <label className={styles.fieldLabel}>{label}</label>
                <input
                  type="text"
                  className={styles.input}
                  placeholder={placeholder}
                  value={competitor.social_media?.[key] || ''}
                  onChange={(e) => updateSocial(key, e.target.value)}
                />
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

export default function CompetitorForm({
  competitors,
  onChange,
  maxCompetitors = 5,
}: CompetitorFormProps) {
  const [justAddedIndex, setJustAddedIndex] = useState<number | null>(null);

  const handleAdd = () => {
    if (competitors.length >= maxCompetitors) return;
    onChange([...competitors, { brand_name: '', website_url: '', social_media: {} }]);
    setJustAddedIndex(competitors.length);
  };

  const handleUpdate = (index: number, next: CompetitorDetail) => {
    const updated = [...competitors];
    updated[index] = next;
    onChange(updated);
  };

  const handleRemove = (index: number) => {
    onChange(competitors.filter((_, i) => i !== index));
    setJustAddedIndex(null);
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.header}>
        <div>
          <div className={styles.title}>Competitor Details (Optional)</div>
          <div className={styles.subtitle}>
            Add competitors you want analyzed, or skip to let AI identify them automatically
          </div>
        </div>
        <span className={styles.counter}>
          {competitors.length}/{maxCompetitors} competitors added
        </span>
      </div>

      {competitors.length > 0 && (
        <div className={styles.cardList}>
          {competitors.map((c, i) => (
            <CompetitorCard
              key={i}
              competitor={c}
              index={i}
              onUpdate={(next) => handleUpdate(i, next)}
              onRemove={() => handleRemove(i)}
              autoFocus={justAddedIndex === i}
            />
          ))}
        </div>
      )}

      {competitors.length < maxCompetitors && (
        <button type="button" className={styles.addBtn} onClick={handleAdd}>
          + Add Competitor
        </button>
      )}
    </div>
  );
}
