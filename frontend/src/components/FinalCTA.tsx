'use client';
import { useState } from 'react';
import styles from './FinalCTA.module.css';

export default function FinalCTA() {
  const [email, setEmail] = useState('');
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (email) setSubmitted(true);
  };

  return (
    <section className={`section ${styles.section}`} id="cta">
      <div className={styles.bgGlow} aria-hidden="true" />
      <div className={styles.bgGrid} aria-hidden="true" />

      <div className="container">
        <div className={styles.card}>
          <div className={styles.cardGlow} aria-hidden="true" />

          <p className="section-eyebrow badge badge" style={{ marginBottom: 20 }}>
            Get Started Today
          </p>

          <h2 className={styles.headline}>
            Build your AI<br />
            <span className="gradient-text">strategy agent</span>
          </h2>

          <p className={styles.subtext}>
            Join 2,400+ businesses using StratAI to outmaneuver the market.
            Start free — no credit card required.
          </p>

          {!submitted ? (
            <form onSubmit={handleSubmit} className={styles.form} id="cta-form">
              <div className={styles.inputRow}>
                <input
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="Enter your work email..."
                  className={styles.emailInput}
                  required
                  id="cta-email-input"
                />
                <button type="submit" className="btn btn-primary" id="cta-submit-btn">
                  Get Started Free
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M5 12h14M12 5l7 7-7 7"/>
                  </svg>
                </button>
              </div>
              <p className={styles.disclaimer}>
                Free 14-day trial · No credit card · Cancel anytime
              </p>
            </form>
          ) : (
            <div className={styles.successMsg} id="cta-success">
              <span className={styles.successIcon}>🎉</span>
              <div>
                <strong>You&apos;re on the list!</strong>
                <p>We&apos;ll send your access link to <em>{email}</em> shortly.</p>
              </div>
            </div>
          )}

          <div className={styles.trustRow}>
            <div className={styles.trustItem}>🔒 SOC 2 Certified</div>
            <div className={styles.trustItem}>🌍 GDPR Compliant</div>
            <div className={styles.trustItem}>⚡ 99.9% Uptime SLA</div>
          </div>
        </div>
      </div>
    </section>
  );
}
