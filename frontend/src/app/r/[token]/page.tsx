'use client';
import { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ReportRenderer from '../../../components/ReportRenderer';
import styles from './page.module.css';

type PublicReport = {
  title: string;
  content: string;
  agent_type: string;
  brand_name: string | null;
  created_at: string;
};

export default function PublicReportPage() {
  const params = useParams();
  const rawToken = params?.token;
  const token = Array.isArray(rawToken) ? rawToken[0] : (rawToken ?? '');

  const [report, setReport] = useState<PublicReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [notFound, setNotFound] = useState(false);

  useEffect(() => {
    if (!token) {
      setLoading(false);
      setNotFound(true);
      return;
    }

    let cancelled = false;

    const fetchReport = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:8000';
        // Public endpoint — intentionally no auth header.
        const res = await fetch(`${apiBase}/api/public/reports/${token}`);
        if (!res.ok) {
          if (!cancelled) setNotFound(true);
          return;
        }
        const data = await res.json();
        if (!cancelled) setReport(data);
      } catch (err) {
        console.error('Failed to load shared report:', err);
        if (!cancelled) setNotFound(true);
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchReport();
    return () => {
      cancelled = true;
    };
  }, [token]);

  const formattedDate = report?.created_at
    ? new Date(report.created_at).toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'long',
        day: 'numeric',
      })
    : '';

  if (loading) {
    return (
      <main className={styles.page}>
        <div className={styles.stateWrapper}>
          <div className={styles.spinner} />
          <p className={styles.stateText}>Loading report...</p>
        </div>
      </main>
    );
  }

  if (notFound || !report) {
    return (
      <main className={styles.page}>
        <div className={styles.stateWrapper}>
          <div className={styles.stateIcon}>
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <h1 className={styles.stateTitle}>Report not found</h1>
          <p className={styles.stateText}>This report is no longer available or the link has been revoked.</p>
        </div>
      </main>
    );
  }

  const metaParts = [report.brand_name, report.agent_type, formattedDate].filter(Boolean);

  return (
    <main className={styles.page}>
      <div className={styles.column}>
        <header className={styles.header}>
          <div className={styles.badge}>
            <span className={styles.badgeDot} />
            <span>Shared Report</span>
          </div>
          <h1 className={styles.title}>{report.title}</h1>
          {metaParts.length > 0 && <p className={styles.meta}>{metaParts.join(' • ')}</p>}
        </header>

        <div className={styles.body}>
          <ReportRenderer content={report.content} />
        </div>

        <footer className={styles.footer}>Powered by StratAI</footer>
      </div>
    </main>
  );
}
