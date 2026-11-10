import styles from './Footer.module.css';

const links: Record<string, { label: string; href?: string }[]> = {
  Product: [
    { label: 'Features', href: '#features' },
    { label: 'How It Works', href: '#workflow' },
    { label: 'Pricing' },
    { label: 'Changelog' },
    { label: 'Roadmap' },
  ],
  Solutions: [
    { label: 'For Startups' },
    { label: 'For Agencies' },
    { label: 'For Enterprise' },
    { label: 'For Consultants' },
  ],
  Resources: [
    { label: 'Documentation' },
    { label: 'Blog' },
    { label: 'Case Studies' },
    { label: 'API Reference' },
  ],
  Company: [
    { label: 'About' },
    { label: 'Careers' },
    { label: 'Press' },
    { label: 'Contact' },
    { label: 'Privacy Policy' },
  ],
};

export default function Footer() {
  return (
    <footer className={styles.footer} id="footer">
      <div className="container">
        <div className={styles.top}>
          {/* Brand */}
          <div className={styles.brand}>
            <div className={styles.logo}>
              <div className={styles.logoIcon}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none">
                  <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <span className={styles.logoText}>StratAI</span>
            </div>
            <p className={styles.brandDesc}>
              AI-powered market analysis and business strategy for modern teams.
              Move faster. Decide smarter.
            </p>
            <div className={styles.socials}>
              {[
                { label: 'Twitter', icon: '𝕏' },
                { label: 'LinkedIn', icon: 'in' },
                { label: 'GitHub', icon: '⌥' },
              ].map((s) => (
                <span key={s.label} className={styles.socialLink} aria-label={s.label} id={`footer-social-${s.label.toLowerCase()}`}>
                  {s.icon}
                </span>
              ))}
            </div>
          </div>

          {/* Links */}
          <div className={styles.linksGrid}>
            {Object.entries(links).map(([category, items]) => (
              <div key={category} className={styles.linkGroup}>
                <h4 className={styles.linkGroupTitle}>{category}</h4>
                <ul className={styles.linkList}>
                  {items.map((item) => {
                    const linkId = `footer-link-${item.label.toLowerCase().replace(/\s+/g, '-')}`;
                    return (
                      <li key={item.label}>
                        {item.href ? (
                          <a href={item.href} className={styles.link} id={linkId}>
                            {item.label}
                          </a>
                        ) : (
                          <span className={styles.link} id={linkId}>
                            {item.label}
                          </span>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className={styles.divider} />

        <div className={styles.bottom}>
          <p className={styles.copyright}>
            © {new Date().getFullYear()} StratAI, Inc. All rights reserved.
          </p>
          <div className={styles.bottomLinks}>
            <span className={styles.link} id="footer-terms">Terms of Service</span>
            <span className={styles.link} id="footer-privacy">Privacy Policy</span>
            <span className={styles.link} id="footer-cookies">Cookie Preferences</span>
          </div>
        </div>
      </div>
    </footer>
  );
}
