import styles from './Testimonials.module.css';

const testimonials = [
  {
    quote: "StratAI completely changed how we approach quarterly planning. What used to take 3 weeks of research now takes 20 minutes. The insights are genuinely actionable.",
    name: "Sarah Chen",
    role: "VP of Strategy, NovaTech",
    avatar: "👩‍💼",
    rating: 5,
    tag: "Enterprise",
  },
  {
    quote: "As a boutique consulting agency, StratAI lets us punch way above our weight class. Our clients get Fortune 500-level market intelligence without the price tag.",
    name: "Marcus Reid",
    role: "Founder, Pinnacle Advisory",
    avatar: "🧑‍💼",
    rating: 5,
    tag: "Agency",
  },
  {
    quote: "I was skeptical AI could handle the nuance of strategic analysis. StratAI proved me completely wrong. The competitor intelligence alone is worth 10x the price.",
    name: "Priya Nair",
    role: "CEO, GrowthLoop",
    avatar: "👩‍🚀",
    rating: 5,
    tag: "Startup",
  },
];

export default function Testimonials() {
  return (
    <section className={`section ${styles.section}`} id="testimonials">
      <div className="container">
        <div className={styles.header}>
          <p className="section-eyebrow badge badge">Testimonials</p>
          <h2 className="section-title">
            Trusted by <span className="gradient-text">world-class teams</span>
          </h2>
          <p className="section-subtitle" style={{ margin: '0 auto', textAlign: 'center' }}>
            From startups to enterprise — StratAI delivers results across every industry.
          </p>
        </div>

        <div className={styles.grid}>
          {testimonials.map((t, i) => (
            <div key={i} className={`card ${styles.card}`} id={`testimonial-card-${i + 1}`}>
              <div className={styles.cardTop}>
                <div className={styles.stars}>
                  {Array.from({ length: t.rating }).map((_, j) => (
                    <span key={j} className={styles.star}>★</span>
                  ))}
                </div>
                <span className={styles.tag}>{t.tag}</span>
              </div>

              <blockquote className={styles.quote}>
                &ldquo;{t.quote}&rdquo;
              </blockquote>

              <div className={styles.author}>
                <div className={styles.authorAvatar}>{t.avatar}</div>
                <div>
                  <div className={styles.authorName}>{t.name}</div>
                  <div className={styles.authorRole}>{t.role}</div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
