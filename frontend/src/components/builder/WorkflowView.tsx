'use client';
import styles from './WorkflowView.module.css';

export default function WorkflowView() {
  return (
    <div className={styles.wrapper}>
      {/* Floating background orbs */}
      <div className={styles.bgOrb1} />
      <div className={styles.bgOrb2} />
      <div className={styles.bgOrb3} />

      {/* ── Single Screen ────────────────────────── */}
      <div className={styles.heroScreen}>
        {/* ── Hero ──────────────────────────────── */}
        <div className={styles.hero}>
          <div className={styles.iconBadge}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12" />
            </svg>
          </div>
          <h1 className={styles.heroTitle}>Workflows</h1>
          <p className={styles.heroDesc}>
            Visually chain together nodes — from API calls to AI models — to automate any process, no code required.
          </p>
        </div>

        {/* ── Stats ─────────────────────────────── */}
        <div className={styles.statsRow}>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.purple}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <rect x="3" y="3" width="7" height="7" /><rect x="14" y="3" width="7" height="7" /><rect x="14" y="14" width="7" height="7" /><rect x="3" y="14" width="7" height="7" />
              </svg>
            </div>
            <span className={styles.statValue}>Multi-Agent</span>
            <span className={styles.statLabel}>Orchestrate agents together</span>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.blue}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" /><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
              </svg>
            </div>
            <span className={styles.statValue}>100+</span>
            <span className={styles.statLabel}>Integrations available</span>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.pink}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2v20M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
              </svg>
            </div>
            <span className={styles.statValue}>Zero Code</span>
            <span className={styles.statLabel}>Drag, drop & deploy</span>
          </div>
          <div className={styles.statCard}>
            <div className={`${styles.statIcon} ${styles.emerald}`}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
            </div>
            <span className={styles.statValue}>Real-Time</span>
            <span className={styles.statLabel}>Live execution & logs</span>
          </div>
        </div>

        {/* ── CTA ───────────────────────────────── */}
        <button className={styles.ctaBtn}>
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" /><line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Create Workflow
        </button>
      </div>
    </div>
  );
}
