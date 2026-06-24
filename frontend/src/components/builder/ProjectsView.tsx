'use client';
import { useRouter } from 'next/navigation';
import styles from './ProjectsView.module.css';

export default function ProjectsView() {
  const router = useRouter();

  const handleCreateNewProject = () => {
    router.push('/brand-setup');
  };

  const mockProjects = [
    {
      title: 'SEO Audit Agent',
      desc: 'An AI-powered SEO auditor that crawls your website, identifies critical technical and on-page issues, and...',
      connectors: ['Firecrawl', 'Gmail', 'Google Sheets'],
      author: 'Apoorv',
      timeAgo: '4 days ago'
    }
  ];

  return (
    <div className={styles.wrapper}>
      {/* Top Header */}
      <div className={styles.header}>
        <h1 className={styles.welcomeTitle}>Welcome back, Apoorv!</h1>
        <div className={styles.actions}>
          <button type="button" className={styles.recentBtn}>Recent Updates</button>
          <button type="button" className={styles.createBtn} onClick={handleCreateNewProject}>
            Create New Project
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Most Used Section */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Most Used Agents</h2>
        <div className={styles.grid}>
          {mockProjects.map((proj, idx) => (
            <div key={idx} className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.agentAvatar}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
                </div>
                <button type="button" className={styles.optionsBtn} aria-label="Project options">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1"/>
                    <circle cx="12" cy="5" r="1"/>
                    <circle cx="12" cy="19" r="1"/>
                  </svg>
                </button>
              </div>

              <div className={styles.cardBody}>
                <h3 className={styles.cardTitle}>{proj.title}</h3>
                <p className={styles.cardDesc}>{proj.desc}</p>
              </div>

              <div className={styles.cardBottom}>
                <div className={styles.connectorsRow}>
                  <div className={styles.connectorIcon} title="Firecrawl">
                    <span style={{ fontSize: '11px' }}>🔥</span>
                  </div>
                  <div className={styles.connectorIcon} title="Gmail">
                    <span style={{ color: '#ea4335', fontWeight: 'bold', fontSize: '9px', fontFamily: 'sans-serif' }}>M</span>
                  </div>
                  <div className={styles.connectorIcon} title="Google Sheets">
                    <span style={{ color: '#0f9d58', fontWeight: 'bold', fontSize: '10px' }}>田</span>
                  </div>
                </div>
                <div className={styles.metaInfo}>
                  {proj.author} • {proj.timeAgo}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recently Chatted Section */}
      <div className={styles.section}>
        <h2 className={styles.sectionTitle}>Agents You Recently Chatted With</h2>
        <div className={styles.grid}>
          {mockProjects.map((proj, idx) => (
            <div key={idx} className={styles.card}>
              <div className={styles.cardHeader}>
                <div className={styles.agentAvatar}>
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="10" />
                    <line x1="2" y1="12" x2="22" y2="12" />
                    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                  </svg>
                </div>
                <button type="button" className={styles.optionsBtn} aria-label="Project options">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                    <circle cx="12" cy="12" r="1"/>
                    <circle cx="12" cy="5" r="1"/>
                    <circle cx="12" cy="19" r="1"/>
                  </svg>
                </button>
              </div>

              <div className={styles.cardBody}>
                <h3 className={styles.cardTitle}>{proj.title}</h3>
                <p className={styles.cardDesc}>{proj.desc}</p>
              </div>

              <div className={styles.cardBottom}>
                <div className={styles.connectorsRow}>
                  <div className={styles.connectorIcon} title="Firecrawl">
                    <span style={{ fontSize: '11px' }}>🔥</span>
                  </div>
                  <div className={styles.connectorIcon} title="Gmail">
                    <span style={{ color: '#ea4335', fontWeight: 'bold', fontSize: '9px', fontFamily: 'sans-serif' }}>M</span>
                  </div>
                  <div className={styles.connectorIcon} title="Google Sheets">
                    <span style={{ color: '#0f9d58', fontWeight: 'bold', fontSize: '10px' }}>田</span>
                  </div>
                </div>
                <div className={styles.metaInfo}>
                  {proj.author} • {proj.timeAgo}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
