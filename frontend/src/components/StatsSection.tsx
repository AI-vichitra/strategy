'use client';
import { useEffect, useRef } from 'react';
import styles from './StatsSection.module.css';

const stats = [
  { value: '948', suffix: 'K+', label: 'Strategies Generated' },
  { value: '296', suffix: 'M+', label: 'Data Points Analyzed' },
  { value: '714', suffix: '+', label: 'Enterprise Clients' },
  { value: '99.2', suffix: '%', label: 'Customer Satisfaction' },
];

export default function StatsSection() {
  const sectionRef = useRef<HTMLElement>(null);

  useEffect(() => {
    const items = sectionRef.current?.querySelectorAll('[data-stat-item]');
    if (!items) return;

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            (entry.target as HTMLElement).style.opacity = '1';
            (entry.target as HTMLElement).style.transform = 'translateY(0)';
          }
        });
      },
      { threshold: 0.2 }
    );

    items.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <section className={`section ${styles.section}`} ref={sectionRef} id="stats">
      <div className={styles.gradientBg} aria-hidden="true" />
      <div className="container">
        <div className={styles.inner}>
          <div className={styles.textSide}>
            <p className="section-eyebrow badge badge">By the Numbers</p>
            <h2 className="section-title">
              The numbers that<br />
              <span className="gradient-text">speak for themselves</span>
            </h2>
            <p className="section-subtitle">
              StratAI processes millions of data points daily to keep your
              strategy ahead of the market — at a scale no human team can match.
            </p>
            <a href="#" className="btn btn-primary" id="stats-cta" style={{ marginTop: 32 }}>
              See Full Case Studies →
            </a>
          </div>

          <div className={styles.statsGrid}>
            {stats.map((stat, i) => (
              <div
                key={i}
                className={styles.statItem}
                data-stat-item="true"
                id={`stat-item-${i + 1}`}
                style={{
                  animationDelay: `${i * 0.15}s`,
                  opacity: 0,
                  transform: 'translateY(20px)',
                  transition: `opacity 0.6s ease ${i * 0.12}s, transform 0.6s ease ${i * 0.12}s, box-shadow 0.3s ease, border-color 0.3s ease`,
                }}
              >
                <div className={styles.statValue}>
                  {stat.value}
                  <span className={styles.statSuffix}>{stat.suffix}</span>
                </div>
                <div className={styles.statLabel}>{stat.label}</div>
                <div className={styles.statBar}>
                  <div
                    className={styles.statBarFill}
                    style={{ width: `${70 + i * 8}%` }}
                  />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
