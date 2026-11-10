'use client';
import { useState, useEffect } from 'react';
import styles from './Navbar.module.css';

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header className={`${styles.header} ${scrolled ? styles.scrolled : ''}`}>
      <div className={`container ${styles.inner}`}>
        {/* Logo */}
        <a href="/" className={styles.logo} id="nav-logo">
          <div className={styles.logoIcon}>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className={styles.logoText}>StratAI</span>
        </a>

        {/* Nav Links */}
        <nav className={`${styles.nav} ${menuOpen ? styles.navOpen : ''}`} aria-label="Main navigation">
          <a href="#features" className={styles.navLink} id="nav-features">Features</a>
          <a href="#workflow" className={styles.navLink} id="nav-workflow">How it Works</a>
        </nav>

        {/* CTA */}
        <div className={styles.actions}>
          <a href="/auth" className={styles.loginLink} id="nav-login">Sign in</a>
          <a href="/auth" className="btn btn-primary" id="nav-cta" style={{padding: '10px 20px', fontSize: '14px'}}>
            Get Started Free
          </a>
          <button
            className={styles.hamburger}
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label="Toggle menu"
            id="nav-hamburger"
          >
            <span className={menuOpen ? styles.barOpen : ''} />
            <span className={menuOpen ? styles.barOpen : ''} />
            <span className={menuOpen ? styles.barOpen : ''} />
          </button>
        </div>
      </div>
    </header>
  );
}
