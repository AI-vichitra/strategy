'use client';
import styles from './Sidebar.module.css';

export default function Sidebar() {
  return (
    <aside className={styles.sidebar}>
      {/* Top Header */}
      <div className={styles.header}>
        <div className={styles.logo}>
          <div className={styles.logoIcon}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className={styles.logoText}>StratAI</span>
        </div>
      </div>

      <div className={styles.scrollArea}>
        {/* Nav Group 1 */}
        <nav className={styles.navGroup}>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('newChat')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z"/>
              <polyline points="9 22 9 12 15 12 15 22"/>
            </svg>
            Home
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openFiles')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M20 10V7l-5-5H6c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h7"/>
              <path d="M14 2v4a2 2 0 0 0 2 2h4"/>
              <path d="M16 22h6"/>
              <path d="M19 19v6"/>
            </svg>
            Files Generated
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openConnectorsView')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>
              <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/>
            </svg>
            Connector
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openAgents')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="3" width="7" height="7"/>
              <rect x="14" y="3" width="7" height="7"/>
              <rect x="14" y="14" width="7" height="7"/>
              <rect x="3" y="14" width="7" height="7"/>
            </svg>
            Agents
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openProjects')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
            Projects
          </a>
          <a href="#" className={styles.navItem} onClick={(e) => { e.preventDefault(); window.dispatchEvent(new CustomEvent('openWorkflow')); }}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/>
            </svg>
            Workflow
          </a>
        </nav>
      </div>

      {/* Bottom Area */}
      <div className={styles.bottomArea}>
        <div className={styles.creditsBox}>
          <div className={styles.creditsTop}>
            <span className={styles.creditsLabel}>Credits Remaining</span>
            <span className={styles.creditsValue}>5.0k of 5.0k</span>
          </div>
          <div className={styles.progressBar}>
            <div className={styles.progressFill} style={{ width: '100%' }}></div>
          </div>
        </div>
        
        <button className={styles.upgradeBtn}>Upgrade Plan</button>
        
        <div className={styles.userProfile}>
          <div className={styles.avatar}>AS</div>
          <span className={styles.userName}>Apoorv Srivastava</span>
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className={styles.profileDots}>
            <circle cx="12" cy="12" r="1"/>
            <circle cx="12" cy="5" r="1"/>
            <circle cx="12" cy="19" r="1"/>
          </svg>
        </div>
      </div>
    </aside>
  );
}
