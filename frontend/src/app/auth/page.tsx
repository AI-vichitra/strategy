'use client';
import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { GoogleOAuthProvider, GoogleLogin } from '@react-oauth/google';
import styles from './page.module.css';

export default function AuthPage() {
  const router = useRouter();
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
    
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    const payload = JSON.stringify({ email, password, full_name: 'New User' });

    try {
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
          throw new Error('Failed to register');
        }

        const regData = await regRes.json();
        
        // If register returns the token directly, use it
        if (regData.access_token) {
          localStorage.setItem('access_token', regData.access_token);
        } else {
          // Otherwise login again to get the token
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

      const token = localStorage.getItem('access_token');
      if (token) {
        await routeUserAfterAuth(token, apiBase);
      }
    } catch (err: any) {
      console.error(err);
      setError(err.message || 'Authentication failed');
    }
  };

  const routeUserAfterAuth = async (token: string, apiBase: string) => {
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
    const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    try {
      const res = await fetch(`${apiBase}/api/auth/google`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token: credentialResponse.credential }),
      });

      if (!res.ok) throw new Error('Google authentication failed');
      const data = await res.json();
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
          <h1 className={styles.title}>Welcome Back</h1>
          <p className={styles.subtitle}>Sign in to your account to continue</p>

          <form onSubmit={handleSignIn} className={styles.form}>
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
              Sign In
            </button>
          </form>

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
