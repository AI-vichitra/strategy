'use client';
import { useState, useEffect } from 'react';
import styles from './SettingsView.module.css';

interface UserProfile {
  id: string;
  email: string;
  full_name?: string | null;
  avatar_url?: string | null;
  created_at?: string;
  tier?: string;
}

const GOOGLE_COLORS = [
  '#1a73e8',
  '#d93025',
  '#188038',
  '#f29900',
  '#a142f4',
  '#fa7b17',
  '#007b83',
  '#e52592',
];

function getAvatarColor(nameOrEmail: string): string {
  let hash = 0;
  for (let i = 0; i < nameOrEmail.length; i++) {
    hash = nameOrEmail.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % GOOGLE_COLORS.length;
  return GOOGLE_COLORS[index];
}

function getInitials(name?: string | null, email?: string): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (email) {
    return email.slice(0, 1).toUpperCase();
  }
  return 'U';
}

interface SettingsViewProps {
  onBack?: () => void;
}

export default function SettingsView({ onBack }: SettingsViewProps) {
  const [user, setUser] = useState<UserProfile | null>(null);
  const [avatarError, setAvatarError] = useState(false);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ text: string; type: 'success' | 'error' } | null>(null);

  useEffect(() => {
    setAvatarError(false);
  }, [user?.avatar_url]);

  const fetchProfile = async () => {
    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      if (!token) return;

      const res = await fetch(`${apiBase}/api/auth/me`, {
        headers: { Authorization: `Bearer ${token}` }
      });

      if (res.ok) {
        const data = await res.json();
        setUser(data);
        setFullName(data.full_name || '');
        setEmail(data.email || '');
      }
    } catch (err) {
      console.error('Error fetching profile:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchProfile();
  }, []);

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setMessage(null);
    setSaving(true);

    try {
      const apiBase = process.env.NEXT_PUBLIC_API_URL;
      const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
      if (!token) throw new Error('Not authenticated');

      const res = await fetch(`${apiBase}/api/auth/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}`
        },
        body: JSON.stringify({
          full_name: fullName.trim() || null,
          email: email.trim() || undefined
        })
      });

      if (!res.ok) {
        const errData = await res.json();
        throw new Error(errData.detail || 'Failed to update profile');
      }

      const updated = await res.json();
      setUser(updated);
      setFullName(updated.full_name || '');
      setEmail(updated.email || '');
      setMessage({ text: 'Profile updated successfully!', type: 'success' });

      // Notify Sidebar and other components
      window.dispatchEvent(new CustomEvent('userProfileUpdated', { detail: updated }));
    } catch (err: any) {
      setMessage({ text: err.message || 'Error updating profile', type: 'error' });
    } finally {
      setSaving(false);
    }
  };

  const displayName = fullName || user?.full_name || (user?.email ? user.email.split('@')[0] : 'User');
  const initials = getInitials(fullName || user?.full_name, user?.email);

  return (
    <div className={styles.wrapper}>
      {onBack && (
        <button type="button" className={styles.backBtn} onClick={onBack}>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="19" y1="12" x2="5" y2="12" />
            <polyline points="12 19 5 12 12 5" />
          </svg>
          Back to Workspace
        </button>
      )}

      <div className={styles.header}>
        <h1 className={styles.title}>Account Settings</h1>
        <p className={styles.subtitle}>Manage your profile details and preferences</p>
      </div>

      <div className={styles.card}>
        <div className={styles.profileHero}>
          {user?.avatar_url && !avatarError ? (
            <img
              src={user.avatar_url}
              alt=""
              referrerPolicy="no-referrer"
              className={styles.avatarImgLarge}
              onError={() => setAvatarError(true)}
            />
          ) : (
            <div
              className={styles.avatarLarge}
              style={{ backgroundColor: getAvatarColor(displayName) }}
            >
              {initials}
            </div>
          )}
          <div className={styles.profileHeroDetails}>
            <div className={styles.profileHeroName}>{displayName}</div>
            <div className={styles.profileHeroEmail}>{user?.email || 'Loading...'}</div>
          </div>
        </div>

        <form onSubmit={handleSave} className={styles.form}>
          <h2 className={styles.cardTitle}>Personal Information</h2>

          {message && (
            <div className={message.type === 'success' ? styles.messageSuccess : styles.messageError}>
              {message.type === 'success' ? (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
              ) : (
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10" />
                  <line x1="12" y1="8" x2="12" y2="12" />
                  <line x1="12" y1="16" x2="12.01" y2="16" />
                </svg>
              )}
              {message.text}
            </div>
          )}

          <div className={styles.formRow}>
            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="profileName">Full Name</label>
              <input
                id="profileName"
                className={styles.input}
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                placeholder="Your full name"
                disabled={loading || saving}
              />
              <p className={styles.helpText}>Appears on your dashboard and presentations.</p>
            </div>

            <div className={styles.formGroup}>
              <label className={styles.label} htmlFor="profileEmail">Email Address</label>
              <input
                id="profileEmail"
                className={styles.input}
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                required
                disabled={loading || saving}
              />
            </div>
          </div>

          <div className={styles.buttonRow}>
            <button
              type="submit"
              className={styles.saveBtn}
              disabled={loading || saving}
            >
              {saving ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        </form>
      </div>

      <div className={`${styles.card} ${styles.overviewCard}`}>
        <h2 className={styles.cardTitle}>Account Overview</h2>
        <div className={styles.overviewGrid}>
          <div className={styles.overviewItem}>
            <span className={styles.infoLabel}>Plan</span>
            <span className={styles.infoValue} style={{ textTransform: 'capitalize' }}>{user?.tier || 'Free'}</span>
          </div>
          {user?.created_at && (
            <div className={styles.overviewItem}>
              <span className={styles.infoLabel}>Member Since</span>
              <span className={styles.infoValue}>
                {new Date(user.created_at).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric'
                })}
              </span>
            </div>
          )}
          <div className={styles.overviewItem}>
            <span className={styles.infoLabel}>Account Status</span>
            <span className={styles.activeBadge}>Active</span>
          </div>
        </div>
      </div>
    </div>
  );
}
