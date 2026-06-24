import styles from './FeaturesGrid.module.css';

const features = [
  {
    icon: '📊',
    title: 'Market Trend Analysis',
    desc: 'Real-time scanning of market signals, emerging trends, and industry shifts tailored to your sector.',
    color: '#6366f1',
  },
  {
    icon: '🔍',
    title: 'Competitor Intelligence',
    desc: 'Deep-dive analysis of competitor moves, positioning, and strategies so you stay one step ahead.',
    color: '#8b5cf6',
  },
  {
    icon: '🎯',
    title: 'Actionable Roadmaps',
    desc: 'Turn raw insights into prioritized strategic roadmaps with clear milestones and KPIs.',
    color: '#ec4899',
  },
  {
    icon: '⚡',
    title: 'Instant Strategy Reports',
    desc: 'Generate comprehensive strategy documents in minutes — not weeks of consultant fees.',
    color: '#06b6d4',
  },
  {
    icon: '🌍',
    title: 'Industry Benchmarking',
    desc: 'Compare your business performance against industry benchmarks to identify growth gaps.',
    color: '#10b981',
  },
  {
    icon: '🤖',
    title: 'AI Agent Workflows',
    desc: 'Automate recurring strategic reviews with AI agents that monitor and alert you to changes.',
    color: '#f59e0b',
  },
];

export default function FeaturesGrid() {
  return (
    <section className={`section ${styles.section}`} id="features">
      <div className="container">
        <div className={styles.header}>
          <p className={`section-eyebrow badge badge`}>Features</p>
          <h2 className={`section-title`}>
            Everything you need to<br />
            <span className="gradient-text">make strategy work</span>
          </h2>
          <p className={`section-subtitle ${styles.subtitle}`}>
            StratAI combines cutting-edge AI with deep business context to give
            your team a genuine competitive advantage.
          </p>
        </div>

        <div className={styles.grid}>
          {features.map((feat, i) => (
            <div key={i} className={`card ${styles.card}`} id={`feature-card-${i + 1}`}>
              <div
                className={`icon-box icon-box ${styles.iconBox}`}
                style={{ background: `${feat.color}18`, borderColor: `${feat.color}25` }}
              >
                <span style={{ fontSize: 24 }}>{feat.icon}</span>
              </div>
              <h3 className={styles.cardTitle}>{feat.title}</h3>
              <p className={styles.cardDesc}>{feat.desc}</p>
              <div className={styles.cardArrow} style={{ color: feat.color }}>
                Learn more →
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
