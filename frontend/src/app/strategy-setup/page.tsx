'use client';
import { useRouter } from 'next/navigation';
import styles from './page.module.css';

export default function TierSelection() {
  const router = useRouter();

  const handleSelectIndividual = () => {
    router.push('/build');
  };

  const handleSelectEnterprise = () => {
    alert('Enterprise Tier: Please contact our sales team at sales@stratai.com to set up your enterprise workspace.');
  };

  return (
    <main className={styles.container}>
      <div className={styles.header}>
        <h1 className={styles.title}>Choose Your Path</h1>
        <p className={styles.subtitle}>Select the tier that fits your strategic needs</p>
      </div>

      <div className={styles.cardsRow}>
        {/* Individual Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.iconWrapper}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
                <circle cx="12" cy="7" r="4" />
              </svg>
            </div>
            <div>
              <h2 className={styles.cardTitle}>FOR INDIVIDUAL</h2>
              <p className={styles.cardSubtitle}>For professionals and creators</p>
            </div>
          </div>

          <div className={styles.cardBody}>
            <ul className={styles.featuresList}>
              <li>Access to all 40+ strategic agent templates</li>
              <li>Live interactive prompt uploader with user context</li>
              <li>Visual file dashboard to track and download generated assets</li>
              <li>Incognito toggle mode for private research sessions</li>
              <li>Standard workspace connectors and profiles</li>
            </ul>
          </div>

          <div className={styles.cardFooter}>
            <button type="button" className={styles.continueBtn} onClick={handleSelectIndividual}>
              Get Started
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
              </svg>
            </button>
          </div>
        </div>

        {/* Enterprise Card */}
        <div className={styles.card}>
          <div className={styles.cardHeader}>
            <div className={styles.iconWrapper} style={{ background: 'linear-gradient(135deg, #111827, #374151)' }}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z" />
                <polyline points="3.27 6.96 12 12.01 20.73 6.96" />
                <line x1="12" y1="22.08" x2="12" y2="12" />
              </svg>
            </div>
            <div>
              <h2 className={styles.cardTitle}>FOR ENTERPRISE</h2>
              <p className={styles.cardSubtitle}>For teams and organizations</p>
            </div>
          </div>

          <div className={styles.cardBody}>
            <ul className={styles.featuresList}>
              <li>Unlimited custom agents built for your business datasets</li>
              <li>Advanced security, single sign-on (SSO), and access controls</li>
              <li>Direct enterprise data warehouse integrations (BigQuery, PostgreSQL)</li>
              <li>Collaborative shared workspaces for team audits</li>
              <li>Dedicated customer success strategist support</li>
            </ul>
          </div>

          <div className={styles.cardFooter}>
            <button type="button" className={styles.enterpriseBtn} onClick={handleSelectEnterprise}>
              Contact Sales
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
            </button>
          </div>
        </div>
      </div>
    </main>
  );
}
