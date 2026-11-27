'use client';
import { useState, useEffect, Suspense } from 'react';
import { useRouter, useSearchParams } from 'next/navigation';
import Link from 'next/link';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import TeamWelcomeScreen from '../../components/TeamWelcomeScreen';
import styles from './page.module.css';

function AuthForm() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [isSignUp, setIsSignUp] = useState(false);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [error, setError] = useState('');

  // Team invitation states
  const [inviteToken, setInviteToken] = useState<string | null>(null);
  const [inviteEmailLocked, setInviteEmailLocked] = useState(false);
  const [inviteTeamName, setInviteTeamName] = useState('');
  const [inviteAdminName, setInviteAdminName] = useState('');
  const [inviteNotice, setInviteNotice] = useState('');
  const [showWelcomeScreen, setShowWelcomeScreen] = useState(false);

  // Forgot password flow states
  const [isForgotPassword, setIsForgotPassword] = useState(false);
  const [forgotEmail, setForgotEmail] = useState('');
  const [forgotLoading, setForgotLoading] = useState(false);
  const [forgotSuccess, setForgotSuccess] = useState(false);
  const [forgotError, setForgotError] = useState('');

  // Detect and resolve invitation link or token on mount
  useEffect(() => {
    const tokenFromUrl = searchParams.get('invite_token');
    const emailFromUrl = searchParams.get('email');
    const storedToken = typeof window !== 'undefined' ? localStorage.getItem('invite_token') : null;

    const token = (tokenFromUrl || storedToken || '').trim();

    // Clear previous sessions
    localStorage.removeItem('access_token');
    localStorage.removeItem('brand_config_id');
    localStorage.removeItem('pathChosen');

    if (token) {
      localStorage.setItem('invite_token', token);
      setInviteToken(token);

      if (emailFromUrl) {
        setEmail(decodeURIComponent(emailFromUrl));
      }

      const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      fetch(`${apiBase}/api/teams/invitations/resolve?token=${encodeURIComponent(token)}`)
        .then(async (res) => {
          if (res.ok) {
            const data = await res.json();
            if (data.email) {
              setEmail(data.email);
            }
            setInviteEmailLocked(true);
            setInviteTeamName(data.team_name || '');
            setInviteAdminName(data.invited_by_name || '');

            // Route to Sign In if already registered, or Sign Up if new user
            if (data.user_exists) {
              setIsSignUp(false);
              setInviteNotice(`Welcome back! Sign in with your password to join ${data.team_name || 'the team workspace'}.`);
            } else {
              setIsSignUp(true);
              setInviteNotice(`You've been invited! Create a password to join ${data.team_name || 'the team workspace'}.`);
            }
          } else {
            console.warn('Invite token could not be resolved:', res.status);
          }
        })
        .catch((err) => {
          console.warn('Error resolving invitation token:', err);
        });
    }
  }, [searchParams]);

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    setForgotError('');

    if (!forgotEmail || !forgotEmail.trim()) {
      setForgotError('Please enter your email address.');
      return;
    }

    setForgotLoading(true);
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

    try {
      const res = await fetch(`${apiBase}/api/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: forgotEmail.trim() }),
      });

      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.detail || data.message || 'Failed to send reset link.');
      }

      setForgotSuccess(true);
    } catch (err: any) {
      setForgotError(err.message || 'Unable to send reset email. Please try again.');
    } finally {
      setForgotLoading(false);
    }
  };

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const resolvedName = fullName.trim() || 'New User';
    const payload = JSON.stringify({
      email,
      password,
      full_name: resolvedName,
      invite_token: inviteToken || undefined,
    });

    try {
      if (isSignUp) {
        if (!password || !confirmPassword) {
          setError('Please fill in both password fields');
          return;
        }

        if (password.length < 6) {
          setError('Password must be at least 6 characters long');
          return;
        }

        if (password !== confirmPassword) {
          setError('Passwords do not match. Please re-enter your password.');
          return;
        }

        // Direct Registration Flow
        const regRes = await fetch(`${apiBase}/api/auth/register`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });

        if (!regRes.ok) {
          const regErr = await regRes.json();
          throw new Error(regErr.detail || 'Failed to register');
        }

        const regData = await regRes.json();
        if (regData.access_token) {
          localStorage.setItem('access_token', regData.access_token);
        } else {
          const loginRes = await fetch(`${apiBase}/api/auth/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
          });
          if (!loginRes.ok) {
            const loginErr = await loginRes.json();
            throw new Error(loginErr.detail || 'Failed to login after registration');
          }
          const loginData = await loginRes.json();
          if (loginData.access_token) {
            localStorage.setItem('access_token', loginData.access_token);
          }
        }
      } else {
        // Sign In Flow
        let res = await fetch(`${apiBase}/api/auth/login`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: payload,
        });

        if (res.status === 401 || res.status === 404 || res.status === 400 || res.status === 422) {
          // Auto-Register Fallback
          const regRes = await fetch(`${apiBase}/api/auth/register`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: payload,
          });

          if (!regRes.ok) {
            throw new Error('Failed to login or register');
          }

          const regData = await regRes.json();
          if (regData.access_token) {
            localStorage.setItem('access_token', regData.access_token);
          } else {
            res = await fetch(`${apiBase}/api/auth/login`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: payload,
            });
          }
        }

        if (!localStorage.getItem('access_token')) {
          if (!res.ok) throw new Error('Failed to login');
          const data = await res.json();
          if (data.access_token) {
            localStorage.setItem('access_token', data.access_token);
          } else {
            throw new Error('No token returned');
          }
        }
      }

      const token = localStorage.getItem('access_token');
      if (token) {
        // If user logged in or registered with an invite token, accept the invitation
        if (inviteToken) {
          try {
            await fetch(`${apiBase}/api/teams/invitations/accept`, {
              method: 'POST',
              headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${token}`,
              },
              body: JSON.stringify({ invite_token: inviteToken }),
            });
          } catch (invErr) {
            console.warn('Could not accept invitation:', invErr);
          }
          localStorage.removeItem('invite_token');
          // Show minimal welcome screen
          setShowWelcomeScreen(true);
        } else {
          await routeUserAfterAuth(token, apiBase);
        }
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Authentication failed');
    }
  };

  const routeUserAfterAuth = async (token: string, apiBase: string | undefined) => {
    try {
      const res = await fetch(`${apiBase}/api/brands/`, {
        headers: { 'Authorization': `Bearer ${token}` },
      });
      if (res.ok) {
        const brands = await res.json();
        if (brands.length > 0 && !localStorage.getItem('brand_config_id')) {
          localStorage.setItem('brand_config_id', brands[0].id);
        }
      }
    } catch (e) {
      console.error('Error checking brands on auth redirect:', e);
    }

    router.push('/build');
  };

  const handleGoogleSuccess = async (credentialResponse: any) => {
    setError('');
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiBase}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: credentialResponse.credential }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Google authentication failed');
      localStorage.setItem('access_token', data.access_token);

      // If invite token present, accept invitation
      if (inviteToken) {
        try {
          await fetch(`${apiBase}/api/teams/invitations/accept`, {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
              'Authorization': `Bearer ${data.access_token}`,
            },
            body: JSON.stringify({ invite_token: inviteToken }),
          });
        } catch (invErr) {
          console.warn('Could not accept invitation with Google auth:', invErr);
        }
        localStorage.removeItem('invite_token');
        setShowWelcomeScreen(true);
      } else {
        await routeUserAfterAuth(data.access_token, apiBase);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Google Authentication failed');
    }
  };

  const handleGoogleError = () => {
    setError('Google Sign In was unsuccessful. Try again later.');
  };

  return (
    <>
      {showWelcomeScreen && (
        <TeamWelcomeScreen
          adminName={inviteAdminName}
          teamName={inviteTeamName}
          onContinue={() => {
            setShowWelcomeScreen(false);
            const token = localStorage.getItem('access_token');
            if (token) {
              routeUserAfterAuth(token, process.env.NEXT_PUBLIC_API_URL);
            } else {
              router.push('/build');
            }
          }}
        />
      )}

      <main className={styles.container}>
        <Link href="/" prefetch={false} className={styles.backHomeBtn} title="Back to landing page">
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <path d="M19 12H5M12 19l-7-7 7-7" />
          </svg>
          <span>Back to Home</span>
        </Link>

        <div className={styles.authCard}>
          <div className={styles.logo}>
            <div className={styles.logoIcon}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" width="18" height="18">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className={styles.logoText}>StratAI</span>
          </div>

          {/* Invitation Banner if arriving from invite link */}
          {inviteEmailLocked && (
            <div className={styles.inviteBanner}>
              <div className={styles.inviteBannerIcon}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2" />
                  <circle cx="9" cy="7" r="4" />
                  <path d="M23 21v-2a4 4 0 0 0-3-3.87" />
                  <path d="M16 3.13a4 4 0 0 1 0 7.75" />
                </svg>
              </div>
              <div className={styles.inviteBannerText}>
                <span>
                  {inviteAdminName ? (
                    <><strong>{inviteAdminName}</strong> invited you to join <strong>{inviteTeamName || 'the workspace'}</strong></>
                  ) : (
                    <>You&apos;ve been invited to join <strong>{inviteTeamName || 'the workspace'}</strong></>
                  )}
                </span>
              </div>
            </div>
          )}

          {isForgotPassword ? (
            <div>
              <h1 className={styles.title}>Reset Password</h1>
              <p className={styles.subtitle}>
                {forgotSuccess
                  ? 'Password reset instructions have been dispatched.'
                  : 'Enter your account email to receive a password reset link.'}
              </p>

              {forgotSuccess ? (
                <div className={styles.successEmailCard}>
                  <div className={styles.emailIcon}>
                    <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                      <polyline points="22,6 12,13 2,6" />
                    </svg>
                  </div>
                  <h2 style={{ fontSize: '18px', fontWeight: 600, color: '#1A1A1A', marginBottom: '8px' }}>
                    Check Your Email
                  </h2>
                  <p style={{ fontSize: '14px', color: '#6B6560', lineHeight: 1.5, marginBottom: '24px' }}>
                    If an account exists for <strong style={{ color: '#1A1A1A' }}>{forgotEmail}</strong>, you will receive a secure password reset link shortly.
                  </p>

                  <button
                    type="button"
                    className={styles.submitBtn}
                    style={{ width: '100%', marginBottom: '12px' }}
                    onClick={() => {
                      setIsForgotPassword(false);
                      setForgotSuccess(false);
                      setForgotError('');
                    }}
                  >
                    Return to Sign In
                  </button>

                  <button
                    type="button"
                    style={{ background: 'none', border: 'none', color: '#B8912E', fontSize: '13px', cursor: 'pointer', fontWeight: 500 }}
                    onClick={() => setForgotSuccess(false)}
                  >
                    Didn&apos;t receive the email? Try again
                  </button>
                </div>
              ) : (
                <form onSubmit={handleForgotPassword} className={styles.form}>
                  <div className={styles.inputGroup}>
                    <label htmlFor="forgotEmail">Email address</label>
                    <input
                      type="email"
                      id="forgotEmail"
                      value={forgotEmail}
                      onChange={(e) => setForgotEmail(e.target.value)}
                      placeholder="name@company.com"
                      required
                      autoFocus
                    />
                  </div>

                  {forgotError && (
                    <div className={styles.errorMsg} style={{ color: '#ef4444', marginBottom: '8px', fontSize: '14px' }}>
                      {forgotError}
                    </div>
                  )}

                  <button
                    type="submit"
                    className={styles.submitBtn}
                    disabled={forgotLoading}
                  >
                    {forgotLoading ? 'Sending Reset Link...' : 'Send Reset Link'}
                  </button>

                  <button
                    type="button"
                    className={styles.backToSignInBtn}
                    onClick={() => {
                      setIsForgotPassword(false);
                      setForgotError('');
                    }}
                  >
                    ← Back to Sign In
                  </button>
                </form>
              )}
            </div>
          ) : (
            <>
              <div className={styles.tabContainer}>
                <button
                  type="button"
                  className={`${styles.tabBtn} ${!isSignUp ? styles.activeTabBtn : ''}`}
                  onClick={() => { setIsSignUp(false); setError(''); setConfirmPassword(''); }}
                >
                  Sign In
                </button>
                <button
                  type="button"
                  className={`${styles.tabBtn} ${isSignUp ? styles.activeTabBtn : ''}`}
                  onClick={() => { setIsSignUp(true); setError(''); setConfirmPassword(''); }}
                >
                  Sign Up
                </button>
              </div>

              <h1 className={styles.title}>{isSignUp ? 'Create Account' : 'Welcome Back'}</h1>
              <p className={styles.subtitle}>
                {isSignUp
                  ? (inviteToken ? 'Set a password to join the workspace' : 'Enter your details to get started')
                  : 'Enter your credentials to continue'}
              </p>

              <form onSubmit={handleSignIn} className={styles.form}>
                {isSignUp && (
                  <div className={styles.inputGroup}>
                    <label htmlFor="fullName">Full Name</label>
                    <input 
                      type="text" 
                      id="fullName" 
                      value={fullName}
                      onChange={(e) => setFullName(e.target.value)}
                      placeholder="John Doe" 
                      required={isSignUp}
                    />
                  </div>
                )}

                <div className={styles.inputGroup}>
                  <label htmlFor="email">
                    Email address {inviteEmailLocked && <span className={styles.lockedBadge}>Locked</span>}
                  </label>
                  {inviteEmailLocked ? (
                    <div className={styles.lockedInputWrapper}>
                      <input 
                        type="email" 
                        id="email" 
                        value={email}
                        readOnly
                        required 
                      />
                      <div className={styles.lockedInputIcon} title="Email is locked to the invitation">
                        <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                      </div>
                    </div>
                  ) : (
                    <input 
                      type="email" 
                      id="email" 
                      value={email}
                      onChange={(e) => setEmail(e.target.value)}
                      placeholder="name@company.com" 
                      required 
                    />
                  )}
                </div>

                <div className={styles.inputGroup}>
                  <label htmlFor="password">Password</label>
                  <input 
                    type="password" 
                    id="password" 
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••" 
                    required 
                  />
                </div>

                {isSignUp && (
                  <div className={styles.inputGroup}>
                    <label htmlFor="confirmPassword">Confirm Password</label>
                    <input 
                      type="password" 
                      id="confirmPassword" 
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      placeholder="••••••••" 
                      required={isSignUp}
                    />
                  </div>
                )}

                {!isSignUp && (
                  <button
                    type="button"
                    className={styles.forgotPasswordLink}
                    onClick={() => {
                      setIsForgotPassword(true);
                      setForgotEmail(email);
                      setForgotSuccess(false);
                      setForgotError('');
                      setError('');
                    }}
                  >
                    Forgot password?
                  </button>
                )}

                {error && <div className={styles.errorMsg} style={{ color: '#ef4444', marginBottom: '16px', fontSize: '14px' }}>{error}</div>}
                
                <button type="submit" className={styles.submitBtn}>
                  {isSignUp ? (inviteToken ? 'Join Workspace' : 'Create Account') : (inviteToken ? 'Sign In & Join' : 'Sign In')}
                </button>
              </form>

              <div className={styles.toggleText}>
                {isSignUp ? 'Already have an account?' : "Don't have an account?"}
                <span 
                  className={styles.toggleLink} 
                  onClick={() => { setIsSignUp(!isSignUp); setError(''); setConfirmPassword(''); }}
                >
                  {isSignUp ? 'Sign In' : 'Sign Up'}
                </span>
              </div>

              <div style={{ margin: '10px 0', textAlign: 'center', color: '#9CA3AF', fontSize: '12px', fontWeight: 500 }}>
                OR
              </div>

              <div style={{ display: 'flex', justifyContent: 'center' }}>
                <GoogleLogin
                  onSuccess={handleGoogleSuccess}
                  onError={handleGoogleError}
                />
              </div>
            </>
          )}
        </div>
      </main>
    </>
  );
}

export default function AuthPage() {
  return (
    <GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || 'dummy_client_id'}>
      <Suspense fallback={<div className={styles.container}><div className={styles.authCard}>Loading...</div></div>}>
        <AuthForm />
      </Suspense>
    </GoogleOAuthProvider>
  );
}
