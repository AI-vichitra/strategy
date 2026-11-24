'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import styles from './page.module.css';

export default function AuthPage() {
  const router = useRouter();
  const [isSignUp, setIsSignUp] = useState(false);
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  // Clear active session immediately upon landing on the auth page
  useEffect(() => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('brand_config_id');
    localStorage.removeItem('pathChosen');
  }, []);

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    const resolvedName = fullName.trim() || 'New User';
    const payload = JSON.stringify({ email, password, full_name: resolvedName });

    try {
      if (isSignUp) {
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
        await routeUserAfterAuth(token, apiBase);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Authentication failed');
    }
  };

  const routeUserAfterAuth = async (token: string, apiBase: string | undefined) => {
    try {
      const res = await fetch(`${apiBase}/api/brands/`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      if (res.ok) {
        const brands = await res.json();
        if (brands.length > 0) {
          router.push('/build');
          return;
        }
      }
    } catch (e) {
      console.error('Error checking brands on auth redirect:', e);
    }

    if (localStorage.getItem('pathChosen')) {
      router.push('/brand-setup');
    } else {
      router.push('/strategy-setup');
    }
  };

  const handleGoogleSuccess = async (credentialResponse: any) => {
    setError('');
    const apiBase = process.env.NEXT_PUBLIC_API_URL;
    try {
      const res = await fetch(`${apiBase}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: credentialResponse.credential }),
      });

      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || 'Google authentication failed');
      localStorage.setItem('access_token', data.access_token);

      await routeUserAfterAuth(data.access_token, apiBase);
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Google Authentication failed');
    }
  };

  const handleGoogleError = () => {
    setError('Google Sign In was unsuccessful. Try again later.');
  };

  return (
    <GoogleOAuthProvider clientId={process.env.NEXT_PUBLIC_GOOGLE_CLIENT_ID || 'dummy_client_id'}>
      <main className={styles.container}>
        <div className={styles.authCard}>
          <div className={styles.logo}>
            <div className={styles.logoIcon}>
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5" />
              </svg>
            </div>
            <span className={styles.logoText}>StratAI</span>
          </div>
          <div className={styles.tabContainer}>
            <button
              type="button"
              className={`${styles.tabBtn} ${!isSignUp ? styles.activeTabBtn : ''}`}
              onClick={() => { setIsSignUp(false); setError(''); }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`${styles.tabBtn} ${isSignUp ? styles.activeTabBtn : ''}`}
              onClick={() => { setIsSignUp(true); setError(''); }}
            >
              Sign Up
            </button>
          </div>

          <h1 className={styles.title}>{isSignUp ? 'Create Account' : 'Welcome Back'}</h1>
          <p className={styles.subtitle}>
            {isSignUp ? 'Sign up with your details to get started' : 'Sign in to your account to continue'}
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
              <label htmlFor="email">Email address</label>
              <input 
                type="email" 
                id="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@company.com" 
                required 
              />
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
            {error && <div className={styles.errorMsg} style={{ color: '#ef4444', marginBottom: '16px', fontSize: '14px' }}>{error}</div>}
            <button type="submit" className={styles.submitBtn}>
              {isSignUp ? 'Sign Up' : 'Sign In'}
            </button>
          </form>

          <div className={styles.toggleText}>
            {isSignUp ? 'Already have an account?' : "Don't have an account?"}
            <span 
              className={styles.toggleLink} 
              onClick={() => { setIsSignUp(!isSignUp); setError(''); }}
            >
              {isSignUp ? 'Sign In' : 'Sign Up'}
            </span>
          </div>

          <div style={{ margin: '20px 0', textAlign: 'center', color: '#888', fontSize: '14px' }}>
            OR
          </div>

          <div style={{ display: 'flex', justifyContent: 'center' }}>
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
            />
          </div>
        </div>
      </main>
    </GoogleOAuthProvider>
  );
}
