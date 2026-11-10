'use client';
import Image from 'next/image';
import { useState } from 'react';
import styles from './WorkflowFeature.module.css';

const steps = [
  {
    num: '01',
    icon: '🔗',
    title: 'Connect Your Data',
    desc: 'Link your business data sources, industry feeds, and market databases in seconds.',
  },
  {
    num: '02',
    icon: '🧠',
    title: 'AI Runs Deep Analysis',
    desc: 'Our AI agents process thousands of data points across trends, competitors, and market conditions.',
  },
  {
    num: '03',
    icon: '📋',
    title: 'Receive Your Strategy',
    desc: 'Get a tailored, prioritized strategy report with clear actions, timelines, and success metrics.',
  },
  {
    num: '04',
    icon: '🔄',
    title: 'Iterate & Refine',
    desc: 'Ask follow-up questions, adjust priorities, and refine your strategy through natural conversation.',
  },
];

export default function WorkflowFeature() {
  const [activeStep, setActiveStep] = useState(0);

  return (
    <section className={`section ${styles.section}`} id="workflow">
      {/* Subtle glow */}
      <div className={styles.glow} aria-hidden="true" />

      <div className={`container ${styles.inner}`}>
        {/* Left: Steps */}
        <div className={styles.left}>
          <p className="section-eyebrow badge badge">How It Works</p>
          <h2 className="section-title">
            Let AI agents do the<br />
            <span className="gradient-text">heavy strategic lifting</span>
          </h2>
          <p className="section-subtitle" style={{ marginBottom: 40 }}>
            From raw market data to a boardroom-ready strategy — StratAI handles
            the entire research and synthesis pipeline autonomously.
          </p>

          <div className={styles.steps}>
            {steps.map((step, i) => (
              <button
                key={i}
                className={`${styles.step} ${activeStep === i ? styles.stepActive : ''}`}
                onClick={() => setActiveStep(i)}
                id={`workflow-step-${i + 1}`}
              >
                <div className={styles.stepNum}>{step.num}</div>
                <div className={styles.stepContent}>
                  <div className={styles.stepTitle}>
                    <span>{step.icon}</span> {step.title}
                  </div>
                  <div className={`${styles.stepDesc} ${activeStep === i ? styles.stepDescVisible : ''}`}>
                    {step.desc}
                  </div>
                </div>
              </button>
            ))}
          </div>

          <a href="/auth" className="btn btn-primary" id="workflow-cta" style={{ marginTop: 32 }}>
            Start Building Now →
          </a>
        </div>

        {/* Right: Preview card */}
        <div className={styles.right}>
          <div className={styles.previewCard}>
            <div className={styles.previewBar}>
              <span className={styles.dot} style={{ background: '#ff5f57' }} />
              <span className={styles.dot} style={{ background: '#febc2e' }} />
              <span className={styles.dot} style={{ background: '#28c840' }} />
              <span className={styles.previewTitle}>Strategy Pipeline</span>
            </div>
            <Image
              src="/workflow-preview.png"
              alt="StratAI workflow builder preview"
              width={520}
              height={380}
              className={styles.previewImage}
            />
            {/* Overlay pipeline steps */}
            <div className={styles.pipelineOverlay}>
              {steps.map((step, i) => (
                <div
                  key={i}
                  className={`${styles.pipelineStep} ${activeStep === i ? styles.pipelineStepActive : ''}`}
                >
                  <span className={styles.pipelineIcon}>{step.icon}</span>
                  <span className={styles.pipelineLabel}>{step.title}</span>
                  {i < steps.length - 1 && <div className={styles.pipelineConnector} />}
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
