'use client';

import React, { useEffect, useState } from 'react';
import { useParams } from 'next/navigation';
import ReportRenderer from '../../../components/ReportRenderer';
import AlertModal from '../../../components/AlertModal';

interface SnapshotMessage {
  id?: string;
  role: 'user' | 'assistant' | 'thinking' | 'error';
  content: string;
  created_at?: string;
  message_metadata?: string;
}

interface SharedChatResponse {
  share_id: string;
  title: string;
  owner_name?: string;
  owner_email?: string;
  created_at?: string;
  expires_at?: string;
  messages: SnapshotMessage[];
  access_type: 'anyone' | 'invited';
}

interface ErrorDetail {
  error: string;
  message: string;
  title?: string;
  owner_name?: string;
  owner_email?: string;
  user_email?: string;
}

const GOOGLE_COLORS = [
  '#1a73e8', // blue
  '#d93025', // red
  '#188038', // green
  '#f29900', // yellow-orange
  '#a142f4', // purple
  '#fa7b17', // orange
  '#007b83', // teal
  '#e52592', // pink
];

function getAvatarColor(nameOrEmail: string): string {
  let hash = 0;
  for (let i = 0; i < nameOrEmail.length; i++) {
    hash = nameOrEmail.charCodeAt(i) + ((hash << 5) - hash);
  }
  const index = Math.abs(hash) % GOOGLE_COLORS.length;
  return GOOGLE_COLORS[index];
}

function getInitials(name?: string | null, email?: string | null): string {
  if (name && name.trim()) {
    const parts = name.trim().split(/\s+/);
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase();
    }
    return parts[0].slice(0, 2).toUpperCase();
  }
  if (email) {
    return email.slice(0, 1).toUpperCase();
  }
  return 'U';
}

export default function SharedChatPage() {
  const params = useParams();
  const rawId = params?.id;
  const shareId = Array.isArray(rawId) ? rawId[0] : (rawId ?? '');

  const [loading, setLoading] = useState(true);
  const [chatData, setChatData] = useState<SharedChatResponse | null>(null);
  const [errorData, setErrorData] = useState<ErrorDetail | null>(null);
  const [requestEmail, setRequestEmail] = useState('');
  const [requestMessage, setRequestMessage] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [requestSuccess, setRequestSuccess] = useState(false);
  const [copiedLink, setCopiedLink] = useState(false);
  const [copiedMsgIdx, setCopiedMsgIdx] = useState<number | null>(null);
  const [alertModal, setAlertModal] = useState<{ isOpen: boolean; title: string; message: string; variant?: 'error' | 'info' | 'success' }>({
    isOpen: false, title: '', message: '', variant: 'info'
  });

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const getAuthHeaders = (): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const headers: Record<string, string> = {};
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  };

  const loadChat = async () => {
    if (!shareId) {
      setLoading(false);
      setErrorData({ error: 'NOT_FOUND', message: 'No share link provided.' });
      return;
    }

    setLoading(true);
    setErrorData(null);

    try {
      const res = await fetch(`${apiBase}/api/chat/shared/${shareId}`, {
        headers: getAuthHeaders()
      });

      if (!res.ok) {
        let errJson: any = null;
        try {
          errJson = await res.json();
        } catch {
          errJson = null;
        }

        const detail: ErrorDetail = errJson?.detail || {
          error: res.status === 410 ? 'LINK_EXPIRED' : res.status === 403 ? 'ACCESS_RESTRICTED' : 'NOT_FOUND',
          message: typeof errJson?.detail === 'string' ? errJson.detail : 'Unable to view this shared chat.'
        };
        setErrorData(detail);
        return;
      }

      const data: SharedChatResponse = await res.json();
      setChatData(data);
    } catch (err: any) {
      setErrorData({
        error: 'NETWORK_ERROR',
        message: err?.message || 'Failed to connect to the server.'
      });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadChat();
  }, [shareId]);

  const handleCopyShareLink = () => {
    if (typeof window !== 'undefined') {
      navigator.clipboard.writeText(window.location.href);
      setCopiedLink(true);
      setTimeout(() => setCopiedLink(false), 2500);
    }
  };

  const handleCopyMessage = async (idx: number, content: string) => {
    try {
      await navigator.clipboard.writeText(content);
      setCopiedMsgIdx(idx);
      setTimeout(() => setCopiedMsgIdx(null), 2000);
    } catch (e) {
      console.error('Failed to copy message:', e);
    }
  };

  const handleRequestAccess = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!shareId) return;

    setIsSubmitting(true);
    try {
      const res = await fetch(`${apiBase}/api/chat/shared/${shareId}/request-access`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...getAuthHeaders()
        },
        body: JSON.stringify({
          email: requestEmail.trim(),
          message: requestMessage.trim()
        })
      });

      if (res.ok) {
        setRequestSuccess(true);
      } else {
        const err = await res.json();
        setAlertModal({ isOpen: true, title: 'Request Failed', message: err?.detail || 'Failed to submit request', variant: 'error' });
      }
    } catch {
      setAlertModal({ isOpen: true, title: 'Request Failed', message: 'Failed to submit access request', variant: 'error' });
    } finally {
      setIsSubmitting(false);
    }
  };

  // ── Loading Screen ──
  if (loading) {
    return (
      <div
        style={{
          minHeight: '100vh',
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          justifyContent: 'center',
          backgroundColor: '#FAF8F5',
          backgroundImage:
            'radial-gradient(ellipse at 8% 8%, rgba(212, 168, 67, 0.08) 0%, transparent 55%), radial-gradient(ellipse at 92% 88%, rgba(45, 42, 38, 0.04) 0%, transparent 55%)',
          color: '#1A1A1A',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}
      >
        <div
          style={{
            width: '40px',
            height: '40px',
            border: '3px solid #E8E4DC',
            borderTopColor: '#D4A843',
            borderRadius: '50%',
            animation: 'spin 0.8s linear infinite',
            marginBottom: '16px'
          }}
        />
        <style>{`@keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }`}</style>
        <div style={{ fontSize: '15px', color: '#6B6560', fontWeight: 500 }}>
          Loading shared chat snapshot...
        </div>
      </div>
    );
  }

  // ── Link Expired Screen ──
  if (errorData?.error === 'LINK_EXPIRED') {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FAF8F5',
          backgroundImage:
            'radial-gradient(ellipse at 8% 8%, rgba(212, 168, 67, 0.08) 0%, transparent 55%), radial-gradient(ellipse at 92% 88%, rgba(45, 42, 38, 0.04) 0%, transparent 55%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}
      >
        <div
          style={{
            maxWidth: '460px',
            width: '100%',
            background: '#ffffff',
            border: '1px solid #E8E4DC',
            borderRadius: '16px',
            padding: '36px 32px',
            textAlign: 'center',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.04)'
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#FEF3C7',
              color: '#D97706',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 18px auto'
            }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <polyline points="12 6 12 12 16 14" />
            </svg>
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A1A', margin: '0 0 8px 0' }}>Link Expired</h2>
          <p style={{ fontSize: '14px', color: '#6B6560', lineHeight: 1.5, margin: '0 0 24px 0' }}>
            {errorData.message || 'This shared chat link has expired. Shared snapshots are kept active for 3 days.'}
          </p>
          <a
            href="/"
            style={{
              display: 'inline-block',
              background: '#1A1A1A',
              color: '#ffffff',
              padding: '10px 22px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 600,
              textDecoration: 'none'
            }}
          >
            Go to Strat AI
          </a>
        </div>
      </div>
    );
  }

  // ── Restricted Access Screen ──
  if (errorData?.error === 'ACCESS_RESTRICTED' || errorData?.error === 'AUTH_REQUIRED') {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FAF8F5',
          backgroundImage:
            'radial-gradient(ellipse at 8% 8%, rgba(212, 168, 67, 0.08) 0%, transparent 55%), radial-gradient(ellipse at 92% 88%, rgba(45, 42, 38, 0.04) 0%, transparent 55%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}
      >
        <div
          style={{
            maxWidth: '480px',
            width: '100%',
            background: '#ffffff',
            border: '1px solid #E8E4DC',
            borderRadius: '16px',
            padding: '36px 32px',
            textAlign: 'center',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.04)'
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#FAF5EC',
              color: '#D4A843',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 18px auto'
            }}
          >
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
              <path d="M7 11V7a5 5 0 0 1 10 0v4" />
            </svg>
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A1A', margin: '0 0 8px 0' }}>Access Restricted</h2>
          <p style={{ fontSize: '14px', color: '#6B6560', lineHeight: 1.5, margin: '0 0 24px 0' }}>
            {errorData.message || 'This conversation snapshot is restricted to invited members.'}
          </p>

          {requestSuccess ? (
            <div
              style={{
                background: '#ECFDF5',
                color: '#065F46',
                border: '1px solid #A7F3D0',
                borderRadius: '8px',
                padding: '12px 16px',
                fontSize: '13.5px',
                fontWeight: 500
              }}
            >
              ✓ Access request submitted. The chat owner will be able to grant you access.
            </div>
          ) : (
            <form onSubmit={handleRequestAccess} style={{ display: 'flex', flexDirection: 'column', gap: '14px', textAlign: 'left' }}>
              <div>
                <label style={{ display: 'block', fontSize: '12.5px', fontWeight: 600, color: '#4A4540', marginBottom: '5px' }}>
                  Your Email
                </label>
                <input
                  type="email"
                  required
                  placeholder="name@company.com"
                  value={requestEmail}
                  onChange={(e) => setRequestEmail(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid #D1D5DB',
                    fontSize: '13.5px',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              <div>
                <label style={{ display: 'block', fontSize: '12.5px', fontWeight: 600, color: '#4A4540', marginBottom: '5px' }}>
                  Note for Owner (optional)
                </label>
                <input
                  type="text"
                  placeholder="Hi, please grant me access..."
                  value={requestMessage}
                  onChange={(e) => setRequestMessage(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    border: '1px solid #D1D5DB',
                    fontSize: '13.5px',
                    boxSizing: 'border-box',
                    outline: 'none'
                  }}
                />
              </div>

              <button
                type="submit"
                disabled={isSubmitting}
                style={{
                  background: '#1A1A1A',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '11px',
                  fontSize: '13.5px',
                  fontWeight: 600,
                  cursor: isSubmitting ? 'not-allowed' : 'pointer',
                  marginTop: '6px'
                }}
              >
                {isSubmitting ? 'Submitting...' : 'Request Access'}
              </button>

              <div style={{ textAlign: 'center', marginTop: '10px' }}>
                <a
                  href="/auth"
                  style={{ fontSize: '13px', color: '#B45309', textDecoration: 'none', fontWeight: 500 }}
                >
                  Already have an account? Sign In
                </a>
              </div>
            </form>
          )}
        </div>
        <AlertModal
          isOpen={alertModal.isOpen}
          title={alertModal.title}
          message={alertModal.message}
          variant={alertModal.variant || 'info'}
          onClose={() => setAlertModal(a => ({ ...a, isOpen: false }))}
        />
      </div>
    );
  }

  // ── General Error / Not Found ──
  if (errorData || !chatData) {
    return (
      <div
        style={{
          minHeight: '100vh',
          backgroundColor: '#FAF8F5',
          backgroundImage:
            'radial-gradient(ellipse at 8% 8%, rgba(212, 168, 67, 0.08) 0%, transparent 55%), radial-gradient(ellipse at 92% 88%, rgba(45, 42, 38, 0.04) 0%, transparent 55%)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          padding: '24px',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}
      >
        <div
          style={{
            maxWidth: '460px',
            width: '100%',
            background: '#ffffff',
            border: '1px solid #E8E4DC',
            borderRadius: '16px',
            padding: '36px 32px',
            textAlign: 'center',
            boxShadow: '0 10px 30px rgba(0, 0, 0, 0.04)'
          }}
        >
          <div
            style={{
              width: '56px',
              height: '56px',
              borderRadius: '50%',
              background: '#FEE2E2',
              color: '#DC2626',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              margin: '0 auto 18px auto'
            }}
          >
            <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="15" y1="9" x2="9" y2="15" />
              <line x1="9" y1="9" x2="15" y2="15" />
            </svg>
          </div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: '#1A1A1A', margin: '0 0 8px 0' }}>Chat Unavailable</h2>
          <p style={{ fontSize: '14px', color: '#6B6560', lineHeight: 1.5, margin: '0 0 24px 0' }}>
            {errorData?.message || 'This shared chat snapshot could not be loaded.'}
          </p>
          <a
            href="/"
            style={{
              display: 'inline-block',
              background: '#1A1A1A',
              color: '#ffffff',
              padding: '10px 22px',
              borderRadius: '8px',
              fontSize: '13.5px',
              fontWeight: 600,
              textDecoration: 'none'
            }}
          >
            Go to Strat AI
          </a>
        </div>
      </div>
    );
  }

  // ── Render Shared Chat Snapshot ──
  const ownerDisplayName = chatData.owner_name || chatData.owner_email || 'Strat AI User';
  const ownerInitials = getInitials(chatData.owner_name, chatData.owner_email);
  const ownerAvatarBg = getAvatarColor(ownerDisplayName);

  const formattedDate = chatData.created_at
    ? new Date(chatData.created_at).toLocaleDateString('en-US', {
        month: 'short',
        day: 'numeric',
        year: 'numeric'
      })
    : '';

  return (
    <div
      style={{
        minHeight: '100vh',
        backgroundColor: '#FAF8F5',
        backgroundImage:
          'radial-gradient(ellipse at 8% 8%, rgba(212, 168, 67, 0.08) 0%, transparent 55%), radial-gradient(ellipse at 92% 88%, rgba(45, 42, 38, 0.04) 0%, transparent 55%)',
        color: '#1A1A1A',
        display: 'flex',
        flexDirection: 'column',
        fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
      }}
    >
      <style>{`
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @keyframes pulse { 0%, 100% { opacity: 1; transform: scale(1); } 50% { opacity: 0.5; transform: scale(0.9); } }
      `}</style>

      {/* Top Header Bar */}
      <header
        style={{
          borderBottom: '1px solid rgba(232, 228, 220, 0.8)',
          padding: '0 28px',
          height: '60px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          position: 'sticky',
          top: 0,
          background: 'rgba(250, 248, 245, 0.92)',
          backdropFilter: 'blur(12px)',
          WebkitBackdropFilter: 'blur(12px)',
          zIndex: 50
        }}
      >
        <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
          <a
            href="/"
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '8px',
              fontSize: '17px',
              fontWeight: 700,
              color: '#1A1A1A',
              textDecoration: 'none',
              letterSpacing: '-0.3px'
            }}
          >
            <span
              style={{
                width: '26px',
                height: '26px',
                borderRadius: '6px',
                background: 'linear-gradient(135deg, #a78bfa 0%, #d4a843 100%)',
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#ffffff',
                boxShadow: '0 2px 6px rgba(212, 168, 67, 0.3)'
              }}
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
              </svg>
            </span>
            <span>Strat AI</span>
          </a>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '14px' }}>
          <a
            href="/auth"
            style={{
              background: '#1A1A1A',
              color: '#ffffff',
              padding: '7px 16px',
              borderRadius: '8px',
              fontSize: '13px',
              fontWeight: 600,
              textDecoration: 'none',
              boxShadow: '0 1px 3px rgba(0, 0, 0, 0.1)',
              transition: 'background 0.15s ease'
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = '#2D2A26')}
            onMouseLeave={(e) => (e.currentTarget.style.background = '#1A1A1A')}
          >
            Try Strat AI Free
          </a>
        </div>
      </header>

      {/* Main Conversation Container */}
      <main
        style={{
          flex: 1,
          maxWidth: '860px',
          width: '100%',
          margin: '0 auto',
          padding: '28px 20px 80px 20px',
          display: 'flex',
          flexDirection: 'column',
          gap: '24px',
          boxSizing: 'border-box'
        }}
      >
        {/* Claude-style Shared Notice Card */}
        <div
          style={{
            background: '#ffffff',
            border: '1px solid #E8E4DC',
            borderRadius: '12px',
            padding: '16px 20px',
            boxShadow: '0 2px 10px rgba(0, 0, 0, 0.02)',
            display: 'flex',
            flexDirection: 'column',
            gap: '12px'
          }}
        >
          <div style={{ display: 'flex', alignItems: 'flex-start', gap: '10px' }}>
            <svg
              width="17"
              height="17"
              viewBox="0 0 24 24"
              fill="none"
              stroke="#6B6560"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              style={{ flexShrink: 0, marginTop: '2px' }}
            >
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
            <p style={{ margin: 0, fontSize: '13px', color: '#4A4540', lineHeight: 1.55 }}>
              Shared by <strong>{ownerDisplayName}</strong>. This is a copy of a chat between Strat AI and{' '}
              <strong>{ownerDisplayName}</strong>. Content may include unverified or unsafe content that does not
              represent the views of Strat AI. Shared snapshot may contain attachments and data not displayed here.
            </p>
          </div>

          <div>
            <button
              type="button"
              onClick={() => setAlertModal({ isOpen: true, title: 'Report Submitted', message: 'Thank you. This shared conversation has been flagged for review.', variant: 'success' })}
              style={{
                background: '#FAF8F5',
                border: '1px solid #E8E4DC',
                borderRadius: '6px',
                padding: '4px 12px',
                fontSize: '12px',
                fontWeight: 500,
                color: '#4A4540',
                cursor: 'pointer',
                transition: 'all 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.borderColor = '#D4A843';
                e.currentTarget.style.background = '#FAF5EC';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.borderColor = '#E8E4DC';
                e.currentTarget.style.background = '#FAF8F5';
              }}
            >
              Report
            </button>
          </div>
        </div>

        {/* Conversation Messages */}
        {chatData.messages.length === 0 ? (
          <div
            style={{
              textAlign: 'center',
              color: '#8C827A',
              padding: '60px 0',
              background: '#ffffff',
              borderRadius: '16px',
              border: '1px solid #E8E4DC'
            }}
          >
            No messages recorded in this chat snapshot.
          </div>
        ) : (
          chatData.messages.map((msg, idx) => {
            const isUser = msg.role === 'user';

            if (isUser) {
              return (
                <div
                  key={msg.id || idx}
                  style={{
                    display: 'flex',
                    justifyContent: 'flex-end',
                    width: '100%'
                  }}
                >
                  <div
                    style={{
                      maxWidth: '74%',
                      background: 'linear-gradient(135deg, #F5F1EB, #EFE9E0)',
                      border: '1px solid rgba(232, 228, 220, 0.7)',
                      borderRadius: '18px 18px 4px 18px',
                      padding: '14px 20px',
                      boxShadow: '0 2px 12px rgba(0, 0, 0, 0.04)',
                      fontSize: '14.5px',
                      lineHeight: 1.6,
                      color: '#1A1A1A',
                      whiteSpace: 'pre-wrap',
                      wordBreak: 'break-word'
                    }}
                  >
                    {msg.content}
                  </div>
                </div>
              );
            }

            // Assistant Response Card — Styled identical to Strat AI builder
            return (
              <div
                key={msg.id || idx}
                style={{
                  display: 'flex',
                  alignItems: 'flex-start',
                  gap: '12px',
                  width: '100%'
                }}
              >
                {/* Strat AI Purple/Gold Icon */}
                <div
                  style={{
                    width: '34px',
                    height: '34px',
                    borderRadius: '10px',
                    background: '#FAF5EC',
                    border: '1px solid rgba(212, 168, 67, 0.3)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    flexShrink: 0,
                    boxShadow: '0 1px 3px rgba(0, 0, 0, 0.05)'
                  }}
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="url(#tg)" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <defs>
                      <linearGradient id="tg" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" stopColor="#a78bfa" />
                        <stop offset="100%" stopColor="#d4a843" />
                      </linearGradient>
                    </defs>
                    <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                  </svg>
                </div>

                {/* Assistant Bubble */}
                <div
                  style={{
                    flex: 1,
                    minWidth: 0,
                    maxWidth: 'calc(100% - 46px)',
                    background: 'rgba(255, 255, 255, 0.95)',
                    border: '1px solid #E8E4DC',
                    borderRadius: '18px 18px 18px 4px',
                    padding: '16px 20px',
                    boxShadow: '0 2px 16px rgba(0, 0, 0, 0.03)',
                    backdropFilter: 'blur(8px)',
                    boxSizing: 'border-box',
                    overflowX: 'hidden'
                  }}
                >
                  {/* Top Report Action Bar */}
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      marginBottom: '14px',
                      paddingBottom: '10px',
                      borderBottom: '1px solid rgba(232, 228, 220, 0.6)'
                    }}
                  >
                    <div
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '6px',
                        background: '#FAF5EC',
                        border: '1px solid rgba(212, 168, 67, 0.3)',
                        borderRadius: '20px',
                        padding: '3px 10px',
                        fontSize: '11px',
                        fontWeight: 600,
                        color: '#B45309'
                      }}
                    >
                      <span
                        style={{
                          width: '6px',
                          height: '6px',
                          borderRadius: '50%',
                          background: '#D4A843',
                          animation: 'pulse 2s infinite'
                        }}
                      />
                      <span>StratAI Report</span>
                    </div>

                    <button
                      type="button"
                      onClick={() => handleCopyMessage(idx, msg.content)}
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '5px',
                        background: '#FAF8F5',
                        border: '1px solid #E8E4DC',
                        borderRadius: '6px',
                        padding: '4px 10px',
                        fontSize: '12px',
                        fontWeight: 500,
                        color: '#4A4540',
                        cursor: 'pointer',
                        transition: 'all 0.15s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.borderColor = '#D4A843';
                        e.currentTarget.style.background = '#FAF5EC';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.borderColor = '#E8E4DC';
                        e.currentTarget.style.background = '#FAF8F5';
                      }}
                    >
                      {copiedMsgIdx === idx ? (
                        <>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5">
                            <polyline points="20 6 9 17 4 12" />
                          </svg>
                          <span style={{ color: '#16a34a' }}>Copied!</span>
                        </>
                      ) : (
                        <>
                          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                            <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                          </svg>
                          <span>Copy</span>
                        </>
                      )}
                    </button>
                  </div>

                  {/* Render Report Markdown & Elements */}
                  <div
                    style={{
                      fontFamily: "'Inter', sans-serif",
                      fontSize: '14.5px',
                      lineHeight: 1.7,
                      color: '#1A1A1A'
                    }}
                  >
                    <ReportRenderer content={msg.content} />
                  </div>
                </div>
              </div>
            );
          })
        )}
      </main>

      {/* Static Footer Notice */}
      <footer
        style={{
          borderTop: '1px solid rgba(232, 228, 220, 0.8)',
          padding: '16px 20px',
          textAlign: 'center',
          fontSize: '12.5px',
          color: '#8C827A',
          backgroundColor: '#FAF8F5'
        }}
      >
        <span>This is a static snapshot of a shared conversation captured on Strat AI. Subsequent messages are not included.</span>
      </footer>
      <AlertModal
        isOpen={alertModal.isOpen}
        title={alertModal.title}
        message={alertModal.message}
        variant={alertModal.variant || 'info'}
        onClose={() => setAlertModal(a => ({ ...a, isOpen: false }))}
      />
    </div>
  );
}
