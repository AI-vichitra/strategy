'use client';
import Image from 'next/image';
import styles from './Hero.module.css';

export default function Hero() {
  return (
    <section className={styles.hero} id="hero">
      {/* Background glow orbs */}
      <div className={styles.orbBlue} aria-hidden="true" />
      <div className={styles.orbPurple} aria-hidden="true" />
      <div className={styles.orbPink} aria-hidden="true" />

      {/* Animated grid */}
      <div className={styles.grid} aria-hidden="true" />

      <div className={`container ${styles.inner}`}>
        {/* Left: Text */}
        <div className={styles.content}>
          <div className={`badge badge ${styles.badge}`} id="hero-badge">
            <span className={styles.badgeDot} />
            AI-Powered Strategy Platform
          </div>

          <h1 className={styles.headline}>
            AI strategy built<br />
            <span className="gradient-text">for your business</span>
          </h1>

          <p className={styles.subtext}>
            StratAI analyzes market trends, competitor landscapes, and
            industry signals to deliver clear, actionable strategies —
            so your team can move faster and smarter.
          </p>

          <div className={styles.ctaRow}>
            <a href="/auth" className="btn btn-primary btn-lg" id="hero-cta-primary">
              Build Your Strategy
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14M12 5l7 7-7 7"/>
              </svg>
            </a>
            <a href="#workflow" className="btn btn-secondary btn-lg" id="hero-cta-secondary">
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/>
              </svg>
              See How It Works
            </a>
          </div>

          <div className={styles.socialProofInline}>
            <div className={styles.avatarStack}>
              {['🧑‍💼','👩‍💻','👨‍🔬','👩‍🎯','🧑‍🚀'].map((emoji, i) => (
                <div key={i} className={styles.avatar} style={{ zIndex: 5 - i }}>
                  {emoji}
                </div>
              ))}
            </div>
            <p className={styles.socialText}>
              <strong>2,400+</strong> businesses already scaling with StratAI
            </p>
          </div>
        </div>

        {/* Right: Visual */}
        <div className={styles.visual}>
          <div className={styles.graphicWrapper}>
            <Image
              src="/hero-graphic.png"
              alt="StratAI workflow visualization"
              width={600}
              height={520}
              className={`${styles.heroImage} animate-float`}
              priority
            />
            {/* Floating stat cards */}
            <div className={`${styles.floatCard} ${styles.floatCard1}`} id="hero-stat-card-1">
              <div className={styles.floatCardIcon}>📈</div>
              <div>
                <div className={styles.floatCardValue}>+340%</div>
                <div className={styles.floatCardLabel}>Strategy Accuracy</div>
              </div>
            </div>
            <div className={`${styles.floatCard} ${styles.floatCard2}`} id="hero-stat-card-2">
              <div className={styles.floatCardIcon}>⚡</div>
              <div>
                <div className={styles.floatCardValue}>10x</div>
                <div className={styles.floatCardLabel}>Faster Insights</div>
              </div>
            </div>
            <div className={`${styles.floatCard} ${styles.floatCard3}`} id="hero-stat-card-3">
              <div className={styles.floatCardIcon}>🎯</div>
              <div>
                <div className={styles.floatCardValue}>97%</div>
                <div className={styles.floatCardLabel}>Decision Confidence</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Bottom fade */}
      <div className={styles.bottomFade} aria-hidden="true" />
    </section>
  );
}
