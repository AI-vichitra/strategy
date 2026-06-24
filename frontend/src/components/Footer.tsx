import styles from './Footer.module.css';

const links = {
  Product: ['Features', 'How It Works', 'Pricing', 'Changelog', 'Roadmap'],
  Solutions: ['For Startups', 'For Agencies', 'For Enterprise', 'For Consultants'],
  Resources: ['Documentation', 'Blog', 'Case Studies', 'API Reference'],
  Company: ['About', 'Careers', 'Press', 'Contact', 'Privacy Policy'],
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
                <a key={s.label} href="#" className={styles.socialLink} aria-label={s.label} id={`footer-social-${s.label.toLowerCase()}`}>
                  {s.icon}
                </a>
              ))}
            </div>
          </div>

          {/* Links */}
          <div className={styles.linksGrid}>
            {Object.entries(links).map(([category, items]) => (
              <div key={category} className={styles.linkGroup}>
                <h4 className={styles.linkGroupTitle}>{category}</h4>
                <ul className={styles.linkList}>
                  {items.map((item) => (
                    <li key={item}>
                      <a
                        href="#"
                        className={styles.link}
                        id={`footer-link-${item.toLowerCase().replace(/\s+/g, '-')}`}
                      >
                        {item}
                      </a>
                    </li>
                  ))}
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
            <a href="#" className={styles.link} id="footer-terms">Terms of Service</a>
            <a href="#" className={styles.link} id="footer-privacy">Privacy Policy</a>
            <a href="#" className={styles.link} id="footer-cookies">Cookie Preferences</a>
          </div>
        </div>
      </div>
    </footer>
  );
}
