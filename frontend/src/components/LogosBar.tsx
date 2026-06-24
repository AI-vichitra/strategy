import styles from './LogosBar.module.css';

const logos = [
  { name: 'Sequoia', symbol: '◆' },
  { name: 'Andreessen', symbol: 'a16z' },
  { name: 'Y Combinator', symbol: 'YC' },
  { name: 'Stripe', symbol: '▪' },
  { name: 'Notion', symbol: 'N' },
  { name: 'Figma', symbol: 'F' },
];

export default function LogosBar() {
  return (
    <section className={`section ${styles.section}`} id="logos">
      <div className="container">
        <p className={styles.label}>Trusted by teams at the world&apos;s most innovative companies</p>
        <div className={styles.logosTrack}>
          <div className={styles.logosInner}>
            {[...logos, ...logos].map((logo, i) => (
              <div key={i} className={styles.logoItem} aria-label={logo.name}>
                <span className={styles.logoSymbol}>{logo.symbol}</span>
                <span className={styles.logoName}>{logo.name}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
