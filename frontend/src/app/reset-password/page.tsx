'use client';

import React, { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import styles from './page.module.css';

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const token = searchParams.get('token');

  const [verifying, setVerifying] = useState(true);
  const [tokenValid, setTokenValid] = useState(false);
  const [targetEmail, setTargetEmail] = useState('');
  const [validationError, setValidationError] = useState('');

  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState('');
  const [success, setSuccess] = useState(false);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  useEffect(() => {
    if (!token) {
      setVerifying(false);
      setTokenValid(false);
      setValidationError('No reset token found in link. Please request a new password reset.');
      return;
    }

    const checkToken = async () => {
      try {
        const res = await fetch(`${apiBase}/api/auth/verify-reset-token?token=${encodeURIComponent(token)}`);
        const data = await res.json();
        if (res.ok && data.valid) {
          setTokenValid(true);
          setTargetEmail(data.email || '');
        } else {
          setTokenValid(false);
          setValidationError(data.detail || 'This reset link is invalid or has expired.');
        }
      } catch (err) {
        setTokenValid(false);
        setValidationError('Failed to connect to the authentication service. Please check your connection.');
      } finally {
        setVerifying(false);
      }
    };

    checkToken();
  }, [token, apiBase]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError('');

    if (!newPassword || !confirmPassword) {
      setFormError('Please fill in both password fields.');
      return;
    }

    if (newPassword.length < 6) {
      setFormError('Password must be at least 6 characters long.');
      return;
    }

    if (newPassword !== confirmPassword) {
      setFormError('Passwords do not match. Please verify and try again.');
      return;
    }

    setSubmitting(true);

    try {
      const res = await fetch(`${apiBase}/api/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          token,
          new_password: newPassword,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to reset password');
      }

      setSuccess(true);
      setTimeout(() => {
        router.push('/auth');
      }, 2500);
    } catch (err: any) {
      setFormError(err.message || 'An unexpected error occurred. Please try again.');
    } finally {
      setSubmitting(false);
    }
  };

  const EyeIcon = ({ visible }: { visible: boolean }) => (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      {visible ? (
        <>
          <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" />
          <circle cx="12" cy="12" r="3" />
        </>
      ) : (
        <>
          <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
          <line x1="1" y1="1" x2="23" y2="23" />
        </>
      )}
    </svg>
  );

  return (
    <main className={styles.container}>
      <div className={styles.card}>
        <div className={styles.logo}>
          <div className={styles.logoIcon}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="22" height="22">
              <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
            </svg>
          </div>
          <span className={styles.logoText}>StratAI</span>
        </div>

        {verifying ? (
          <div style={{ textAlign: 'center', padding: '30px 0' }}>
            <div className={styles.spinner} />
            <p style={{ color: '#6B6560', fontSize: '14px' }}>Verifying secure reset link...</p>
          </div>
        ) : !tokenValid ? (
          <div style={{ textAlign: 'center' }}>
            <h1 className={styles.title} style={{ color: '#DC2626' }}>Invalid Reset Link</h1>
            <p className={styles.subtitle}>{validationError}</p>
            <Link href="/auth" className={styles.backBtn}>
              ← Back to Sign In
            </Link>
          </div>
        ) : success ? (
          <div className={styles.successBox}>
            <div className={styles.successIcon}>
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="20 6 9 17 4 12" />
              </svg>
            </div>
            <h1 className={styles.title}>Password Reset!</h1>
            <p className={styles.subtitle} style={{ marginBottom: '16px' }}>
              Your password has been securely updated.
            </p>
            <p style={{ fontSize: '13px', color: '#B8912E', fontWeight: 600 }}>
              Redirecting you to sign in...
            </p>
          </div>
        ) : (
          <>
            <h1 className={styles.title}>Set New Password</h1>
            <p className={styles.subtitle}>
              {targetEmail ? (
                <>Resetting password for <strong style={{ color: '#1A1A1A' }}>{targetEmail}</strong></>
              ) : (
                'Choose a strong password with at least 6 characters.'
              )}
            </p>

            <form onSubmit={handleSubmit} className={styles.form}>
              <div className={styles.inputGroup}>
                <label htmlFor="newPassword">New Password</label>
                <div className={styles.passwordInputWrapper}>
                  <input
                    type={showPassword ? 'text' : 'password'}
                    id="newPassword"
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    placeholder="Enter new password"
                    minLength={6}
                    required
                  />
                  <button
                    type="button"
                    className={styles.eyeBtn}
                    onClick={() => setShowPassword(!showPassword)}
                    tabIndex={-1}
                    aria-label="Toggle password visibility"
                  >
                    <EyeIcon visible={showPassword} />
                  </button>
                </div>
              </div>

              <div className={styles.inputGroup}>
                <label htmlFor="confirmPassword">Confirm New Password</label>
                <div className={styles.passwordInputWrapper}>
                  <input
                    type={showConfirmPassword ? 'text' : 'password'}
                    id="confirmPassword"
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="Confirm new password"
                    minLength={6}
                    required
                  />
                  <button
                    type="button"
                    className={styles.eyeBtn}
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    tabIndex={-1}
                    aria-label="Toggle confirm password visibility"
                  >
                    <EyeIcon visible={showConfirmPassword} />
                  </button>
                </div>
              </div>

              {formError && (
                <div className={styles.errorMsg}>
                  {formError}
                </div>
              )}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={submitting}
              >
                {submitting ? 'Updating Password...' : 'Save New Password'}
              </button>
            </form>

            <div style={{ textAlign: 'center', marginTop: '20px' }}>
              <Link href="/auth" style={{ fontSize: '13px', color: '#6B6560', textDecoration: 'none' }}>
                Cancel and return to <span style={{ color: '#D4A843', fontWeight: 600 }}>Sign In</span>
              </Link>
            </div>
          </>
        )}
      </div>
    </main>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={
      <main className={styles.container}>
        <div className={styles.card} style={{ textAlign: 'center', padding: '40px' }}>
          <div className={styles.spinner} />
          <p style={{ color: '#6B6560', fontSize: '14px' }}>Loading...</p>
        </div>
      </main>
    }>
      <ResetPasswordContent />
    </Suspense>
  );
}
