'use client';

import React, { useState, useEffect, useRef } from 'react';

interface ShareChatModalProps {
  isOpen: boolean;
  onClose: () => void;
  projectId: string;
  projectTitle?: string;
  currentUser?: {
    full_name?: string | null;
    email?: string | null;
    avatar_url?: string | null;
  } | null;
  onShowToast?: (msg: string) => void;
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

interface ShareData {
  share_id: string;
  share_url: string;
  title: string;
  access_type: 'anyone' | 'invited';
  invited_emails: string[];
  owner_name?: string;
  owner_email?: string;
  message_count?: number;
  is_expired?: boolean;
}

export default function ShareChatModal({
  isOpen,
  onClose,
  projectId,
  projectTitle,
  currentUser,
  onShowToast
}: ShareChatModalProps) {
  const [view, setView] = useState<'main' | 'settings'>('main');
  const [loading, setLoading] = useState(false);
  const [shareData, setShareData] = useState<ShareData | null>(null);
  const [accessType, setAccessType] = useState<'anyone' | 'invited'>('anyone');
  const [invitedEmails, setInvitedEmails] = useState<string[]>([]);
  const [draftPills, setDraftPills] = useState<string[]>([]);
  const [inputVal, setInputVal] = useState('');
  const [copied, setCopied] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);
  const [avatarError, setAvatarError] = useState(false);
  const [localToast, setLocalToast] = useState<string | null>(null);
  const [settingsDropdownOpen, setSettingsDropdownOpen] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const settingsDropdownRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleOutsideClick = (e: MouseEvent) => {
      if (settingsDropdownRef.current && !settingsDropdownRef.current.contains(e.target as Node)) {
        setSettingsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleOutsideClick);
    return () => document.removeEventListener('mousedown', handleOutsideClick);
  }, []);

  useEffect(() => {
    setAvatarError(false);
  }, [currentUser?.avatar_url]);

  const apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

  const notify = (msg: string) => {
    if (onShowToast) {
      onShowToast(msg);
    } else {
      setLocalToast(msg);
      setTimeout(() => setLocalToast(null), 3000);
    }
  };

  const getAuthHeaders = (): Record<string, string> => {
    const token = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;
    const headers: Record<string, string> = { 'Content-Type': 'application/json' };
    if (token) headers['Authorization'] = `Bearer ${token}`;
    return headers;
  };

  useEffect(() => {
    if (!isOpen || !projectId) return;
    setView('main');
    setCopied(false);
    setDraftPills([]);
    setInputVal('');
    loadShareStatus();
  }, [isOpen, projectId]);

  const loadShareStatus = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${apiBase}/api/chat/share/settings/${projectId}?auto_create=true`, {
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        if (data.shared || data.share_id) {
          setShareData(data);
          setAccessType(data.access_type || 'anyone');
          setInvitedEmails(data.invited_emails || []);
          return;
        }
      }

      // Fallback create if not initialized
      const createRes = await fetch(`${apiBase}/api/chat/share`, {
        method: 'POST',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          project_id: projectId,
          access_type: 'anyone',
          invited_emails: []
        })
      });
      if (createRes.ok) {
        const initial = await createRes.json();
        setShareData(initial);
        setAccessType(initial.access_type || 'anyone');
        setInvitedEmails(initial.invited_emails || []);
      }
    } catch (err) {
      console.error('Error loading share settings:', err);
      notify('Failed to initialize share link');
    } finally {
      setLoading(false);
    }
  };

  const getShareFullUrl = () => {
    if (!shareData?.share_id) return '';
    if (typeof window !== 'undefined') {
      const origin = window.location.origin;
      return `${origin}/share/${shareData.share_id}`;
    }
    return `/share/${shareData.share_id}`;
  };

  const handleCopyLink = () => {
    if (loading || !shareData?.share_id) return;
    const url = getShareFullUrl();
    if (!url) return;
    navigator.clipboard.writeText(url);
    setCopied(true);
    notify('Link copied to clipboard!');
    setTimeout(() => setCopied(false), 2500);
  };

  const addPill = (text: string) => {
    const clean = text.trim().toLowerCase();
    if (!clean || !clean.includes('@')) return;
    if (!draftPills.includes(clean) && !invitedEmails.includes(clean)) {
      setDraftPills(prev => [...prev, clean]);
    }
    setInputVal('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',' || e.key === ' ') {
      e.preventDefault();
      if (inputVal.trim()) {
        addPill(inputVal);
      }
    } else if (e.key === 'Backspace' && !inputVal && draftPills.length > 0) {
      setDraftPills(prev => prev.slice(0, -1));
    }
  };

  const removePill = (pillToRemove: string) => {
    setDraftPills(prev => prev.filter(p => p !== pillToRemove));
  };

  const handleInvite = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();

    let pending = [...draftPills];
    if (inputVal.trim() && inputVal.includes('@')) {
      const clean = inputVal.trim().toLowerCase();
      if (!pending.includes(clean) && !invitedEmails.includes(clean)) {
        pending.push(clean);
      }
      setInputVal('');
    }

    if (pending.length === 0) return;

    const newInvited = Array.from(new Set([...invitedEmails, ...pending]));
    setInvitedEmails(newInvited);
    setDraftPills([]);

    if (shareData?.share_id) {
      try {
        // Send email invitations via backend SMTP service
        await fetch(`${apiBase}/api/chat/share/${shareData.share_id}/invite`, {
          method: 'POST',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            emails: pending,
            share_url: getShareFullUrl()
          })
        });

        const nextAccess = accessType === 'anyone' ? 'invited' : accessType;
        const res = await fetch(`${apiBase}/api/chat/share/${shareData.share_id}`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({
            invited_emails: newInvited,
            access_type: nextAccess
          })
        });
        if (res.ok) {
          const updated = await res.json();
          setShareData(prev => ({
            ...prev!,
            invited_emails: newInvited,
            access_type: nextAccess
          }));
          setAccessType(nextAccess);
          notify(`Invitation email sent to ${pending.length} member(s)!`);
        }
      } catch (err) {
        console.error('Failed to send invitation emails:', err);
        notify('Failed to send invitations.');
      }
    }
  };

  const handleRemoveEmail = async (emailToRemove: string) => {
    const updated = invitedEmails.filter(e => e !== emailToRemove);
    setInvitedEmails(updated);

    if (shareData?.share_id) {
      try {
        const res = await fetch(`${apiBase}/api/chat/share/${shareData.share_id}`, {
          method: 'PUT',
          headers: getAuthHeaders(),
          body: JSON.stringify({ invited_emails: updated })
        });
        if (res.ok) {
          setShareData(prev => ({ ...prev!, invited_emails: updated }));
          notify(`Removed ${emailToRemove}`);
        }
      } catch (err) {
        console.error('Failed to remove email:', err);
      }
    }
  };

  const handleSaveSettings = async (newAccessType: 'anyone' | 'invited') => {
    if (!shareData?.share_id) return;
    setIsUpdating(true);
    try {
      const res = await fetch(`${apiBase}/api/chat/share/${shareData.share_id}`, {
        method: 'PUT',
        headers: getAuthHeaders(),
        body: JSON.stringify({
          access_type: newAccessType,
          invited_emails: invitedEmails
        })
      });
      if (res.ok) {
        const updated = await res.json();
        setShareData(updated);
        setAccessType(updated.access_type);
        setView('main');
        notify('Share settings updated successfully');
      } else {
        notify('Failed to update settings');
      }
    } catch (err) {
      notify('Failed to update settings');
    } finally {
      setIsUpdating(false);
    }
  };

  const handleStopSharing = async () => {
    if (!shareData?.share_id) return;
    setIsUpdating(true);
    try {
      const res = await fetch(`${apiBase}/api/chat/share/${shareData.share_id}`, {
        method: 'DELETE',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        setShareData(null);
        notify('Chat sharing stopped');
        onClose();
      } else {
        notify('Failed to stop sharing');
      }
    } catch (err) {
      notify('Failed to stop sharing');
    } finally {
      setIsUpdating(false);
    }
  };

  if (!isOpen) return null;

  if (!projectId) {
    return (
      <div
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 99999,
          background: 'rgba(15, 23, 42, 0.45)',
          backdropFilter: 'blur(4px)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center'
        }}
        onClick={onClose}
      >
        <div
          style={{
            maxWidth: '380px',
            width: '90%',
            background: '#ffffff',
            borderRadius: '16px',
            padding: '24px',
            textAlign: 'center',
            boxShadow: '0 20px 25px -5px rgba(0,0,0,0.1)'
          }}
          onClick={(e) => e.stopPropagation()}
        >
          <h3 style={{ fontSize: '16px', fontWeight: 600, color: '#111827', margin: '0 0 8px 0' }}>No Active Chat</h3>
          <p style={{ fontSize: '13.5px', color: '#6b7280', margin: '0 0 20px 0' }}>
            Please select or start a project conversation before sharing.
          </p>
          <button
            onClick={onClose}
            style={{
              background: '#000000',
              color: '#ffffff',
              border: 'none',
              borderRadius: '8px',
              padding: '8px 20px',
              fontSize: '13px',
              fontWeight: 500,
              cursor: 'pointer'
            }}
          >
            Close
          </button>
        </div>
      </div>
    );
  }

  const ownerName = currentUser?.full_name || (currentUser?.email ? currentUser.email.split('@')[0] : 'You');
  const ownerEmail = currentUser?.email || 'user@example.com';
  const ownerInitials = getInitials(currentUser?.full_name, currentUser?.email);
  const ownerDisplayName = currentUser?.full_name || currentUser?.email || 'User';

  const hasPendingToInvite = draftPills.length > 0 || (inputVal.trim() && inputVal.includes('@'));

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 99999,
        background: 'rgba(15, 23, 42, 0.45)',
        backdropFilter: 'blur(4px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        animation: 'fadeIn 0.2s ease-out'
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        style={{
          width: '100%',
          maxWidth: '460px',
          background: '#ffffff',
          color: '#111827',
          borderRadius: '16px',
          border: '1px solid #e5e7eb',
          boxShadow: '0 20px 25px -5px rgba(0, 0, 0, 0.1), 0 10px 10px -5px rgba(0, 0, 0, 0.04)',
          overflow: 'hidden',
          maxHeight: 'calc(100vh - 40px)',
          overflowY: 'auto',
          fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
        }}
        onClick={(e) => e.stopPropagation()}
      >
        {localToast && (
          <div
            style={{
              position: 'absolute',
              top: '12px',
              left: '50%',
              transform: 'translateX(-50%)',
              background: '#111827',
              color: '#ffffff',
              padding: '6px 14px',
              borderRadius: '20px',
              fontSize: '12px',
              fontWeight: 500,
              zIndex: 100000,
              boxShadow: '0 4px 12px rgba(0,0,0,0.15)'
            }}
          >
            {localToast}
          </div>
        )}

        {view === 'main' ? (
          /* ================= MAIN SHARE VIEW ================= */
          <div style={{ padding: '22px 24px' }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
              <h2 style={{ margin: 0, fontSize: '18px', fontWeight: 600, color: '#111827' }}>
                Share chat
              </h2>
              <button
                onClick={onClose}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#6b7280',
                  fontSize: '18px',
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: '6px',
                  lineHeight: 1,
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f3f4f6';
                  e.currentTarget.style.color = '#111827';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#6b7280';
                }}
              >
                ✕
              </button>
            </div>
            <div style={{ fontSize: '13px', color: '#6b7280', marginBottom: '18px' }}>
              Only messages up until now will be shared
            </div>

            {/* Email Invite Box with Tag/Pill support */}
            <div style={{ display: 'flex', gap: '8px', marginBottom: '22px' }}>
              <div
                onClick={() => inputRef.current?.focus()}
                style={{
                  flex: 1,
                  background: '#ffffff',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  padding: '6px 10px',
                  display: 'flex',
                  flexWrap: 'wrap',
                  alignItems: 'center',
                  gap: '6px',
                  minHeight: '42px',
                  boxSizing: 'border-box',
                  cursor: 'text',
                  transition: 'border-color 0.2s ease, box-shadow 0.2s ease'
                }}
              >
                {draftPills.map(pill => (
                  <span
                    key={pill}
                    style={{
                      display: 'inline-flex',
                      alignItems: 'center',
                      gap: '5px',
                      background: '#f3f4f6',
                      border: '1px solid #e5e7eb',
                      borderRadius: '6px',
                      padding: '2px 8px',
                      fontSize: '13px',
                      color: '#1f2937',
                      lineHeight: 1.4
                    }}
                  >
                    <span>{pill}</span>
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        removePill(pill);
                      }}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#6b7280',
                        cursor: 'pointer',
                        padding: 0,
                        fontSize: '12px',
                        lineHeight: 1,
                        display: 'flex',
                        alignItems: 'center'
                      }}
                      onMouseEnter={(e) => (e.currentTarget.style.color = '#ef4444')}
                      onMouseLeave={(e) => (e.currentTarget.style.color = '#6b7280')}
                    >
                      ✕
                    </button>
                  </span>
                ))}

                <input
                  ref={inputRef}
                  type="email"
                  placeholder={draftPills.length === 0 ? "Add people by email" : ""}
                  value={inputVal}
                  onChange={(e) => setInputVal(e.target.value)}
                  onKeyDown={handleKeyDown}
                  onBlur={() => {
                    if (inputVal.trim() && inputVal.includes('@')) {
                      addPill(inputVal);
                    }
                  }}
                  style={{
                    flex: 1,
                    minWidth: '130px',
                    border: 'none',
                    outline: 'none',
                    background: 'transparent',
                    color: '#111827',
                    fontSize: '13.5px',
                    padding: '3px 2px'
                  }}
                />
              </div>

              <button
                type="button"
                onClick={handleInvite}
                disabled={!hasPendingToInvite}
                style={{
                  background: hasPendingToInvite ? '#111827' : '#f3f4f6',
                  color: hasPendingToInvite ? '#ffffff' : '#9ca3af',
                  border: hasPendingToInvite ? '1px solid #111827' : '1px solid #e5e7eb',
                  borderRadius: '8px',
                  padding: '0 16px',
                  fontSize: '13.5px',
                  fontWeight: 500,
                  cursor: hasPendingToInvite ? 'pointer' : 'default',
                  transition: 'all 0.15s ease',
                  flexShrink: 0
                }}
              >
                Invite
              </button>
            </div>

            {/* Who has access label */}
            <div style={{ fontSize: '12px', fontWeight: 600, color: '#6b7280', textTransform: 'uppercase', letterSpacing: '0.5px', marginBottom: '10px' }}>
              Who has access
            </div>

            {/* Access Permission Selector Row */}
            <div
              onClick={() => setView('settings')}
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                padding: '10px 12px',
                borderRadius: '8px',
                background: '#f9fafb',
                cursor: 'pointer',
                marginBottom: '14px',
                border: '1px solid #e5e7eb',
                transition: 'background 0.15s ease, border-color 0.15s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f3f4f6';
                e.currentTarget.style.borderColor = '#d1d5db';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#f9fafb';
                e.currentTarget.style.borderColor = '#e5e7eb';
              }}
            >
              <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                <div
                  style={{
                    width: '32px',
                    height: '32px',
                    borderRadius: '8px',
                    background: '#e5e7eb',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    color: '#374151'
                  }}
                >
                  {accessType === 'anyone' ? (
                    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <circle cx="12" cy="12" r="10" />
                      <line x1="2" y1="12" x2="22" y2="12" />
                      <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                    </svg>
                  ) : (
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                      <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                    </svg>
                  )}
                </div>
                <div>
                  <div style={{ fontSize: '14px', fontWeight: 500, color: '#111827' }}>
                    {accessType === 'anyone' ? 'Anyone with the link' : 'Only people invited'}
                  </div>
                  <div style={{ fontSize: '12px', color: '#6b7280' }}>
                    {accessType === 'anyone' ? 'No sign-in required to view' : 'Only invited email accounts can access'}
                  </div>
                </div>
              </div>
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#9ca3af" strokeWidth="2">
                <polyline points="9 18 15 12 9 6" />
              </svg>
            </div>

            {/* Members List Container */}
            <div style={{ maxHeight: '200px', overflowY: 'auto', marginBottom: '8px', paddingRight: '2px' }}>
              {/* Owner Row */}
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '8px 10px', borderRadius: '8px', marginBottom: '4px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  {currentUser?.avatar_url && !avatarError ? (
                    <img
                      src={currentUser.avatar_url}
                      alt=""
                      referrerPolicy="no-referrer"
                      onError={() => setAvatarError(true)}
                      style={{
                        width: '34px',
                        height: '34px',
                        borderRadius: '50%',
                        objectFit: 'cover',
                        flexShrink: 0,
                        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)'
                      }}
                    />
                  ) : (
                    <div
                      style={{
                        width: '34px',
                        height: '34px',
                        borderRadius: '50%',
                        backgroundColor: getAvatarColor(ownerDisplayName),
                        color: '#ffffff',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        fontSize: '12px',
                        fontWeight: 600,
                        flexShrink: 0,
                        textTransform: 'uppercase',
                        letterSpacing: '0.5px',
                        boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)'
                      }}
                    >
                      {ownerInitials}
                    </div>
                  )}
                  <div>
                    <div style={{ fontSize: '13.5px', fontWeight: 500, color: '#111827' }}>
                      {ownerName} <span style={{ color: '#6b7280', fontWeight: 400 }}>(you)</span>
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280' }}>
                      {ownerEmail}
                    </div>
                  </div>
                </div>
                <span style={{ fontSize: '12.5px', color: '#6b7280' }}>Owner</span>
              </div>

              {/* Invited Members List */}
              {invitedEmails.map((email) => {
                const initial = email[0]?.toUpperCase() || 'U';
                return (
                  <div
                    key={email}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '8px 10px',
                      borderRadius: '8px',
                      background: 'transparent',
                      transition: 'background 0.15s ease',
                      marginBottom: '4px'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f9fafb')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = 'transparent')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '12px', minWidth: 0 }}>
                      <div
                        style={{
                          width: '34px',
                          height: '34px',
                          borderRadius: '50%',
                          backgroundColor: getAvatarColor(email),
                          color: '#ffffff',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          fontSize: '12px',
                          fontWeight: 600,
                          flexShrink: 0,
                          textTransform: 'uppercase',
                          letterSpacing: '0.5px',
                          boxShadow: '0 1px 3px rgba(0, 0, 0, 0.12)'
                        }}
                      >
                        {getInitials(null, email)}
                      </div>
                      <div style={{ minWidth: 0 }}>
                        <div style={{ fontSize: '13.5px', color: '#111827', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {email} <span style={{ color: '#6b7280', fontSize: '12px' }}>(Invited)</span>
                        </div>
                      </div>
                    </div>

                    <button
                      onClick={() => handleRemoveEmail(email)}
                      style={{
                        background: 'transparent',
                        border: 'none',
                        color: '#9ca3af',
                        cursor: 'pointer',
                        padding: '6px',
                        borderRadius: '6px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        transition: 'all 0.15s ease'
                      }}
                      onMouseEnter={(e) => {
                        e.currentTarget.style.color = '#ef4444';
                        e.currentTarget.style.background = '#fee2e2';
                      }}
                      onMouseLeave={(e) => {
                        e.currentTarget.style.color = '#9ca3af';
                        e.currentTarget.style.background = 'transparent';
                      }}
                      title="Remove access"
                    >
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                        <line x1="10" y1="11" x2="10" y2="17" />
                        <line x1="14" y1="11" x2="14" y2="17" />
                      </svg>
                    </button>
                  </div>
                );
              })}
            </div>

            <div style={{ height: '1px', background: '#e5e7eb', margin: '14px 0' }} />

            {/* Bottom Actions Bar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <button
                onClick={() => setView('settings')}
                style={{
                  background: '#ffffff',
                  border: '1px solid #d1d5db',
                  borderRadius: '8px',
                  padding: '8px 10px',
                  color: '#374151',
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'center',
                  transition: 'all 0.15s ease'
                }}
                title="Share Settings"
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f3f4f6';
                  e.currentTarget.style.borderColor = '#9ca3af';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = '#ffffff';
                  e.currentTarget.style.borderColor = '#d1d5db';
                }}
              >
                <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="3" />
                  <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 1 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 1 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83-2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 1 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
                </svg>
              </button>

              <button
                onClick={handleCopyLink}
                disabled={loading || !shareData?.share_id}
                style={{
                  background: copied ? '#10b981' : '#000000',
                  color: '#ffffff',
                  border: 'none',
                  borderRadius: '8px',
                  padding: '9px 18px',
                  fontSize: '13.5px',
                  fontWeight: 600,
                  cursor: (loading || !shareData?.share_id) ? 'not-allowed' : 'pointer',
                  opacity: (loading || !shareData?.share_id) ? 0.75 : 1,
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => {
                  if (!copied && !loading && shareData?.share_id) e.currentTarget.style.background = '#1f2937';
                }}
                onMouseLeave={(e) => {
                  if (!copied && !loading && shareData?.share_id) e.currentTarget.style.background = '#000000';
                }}
              >
                {loading || !shareData?.share_id ? (
                  <>
                    <span
                      style={{
                        width: '14px',
                        height: '14px',
                        border: '2px solid rgba(255, 255, 255, 0.3)',
                        borderTopColor: '#ffffff',
                        borderRadius: '50%',
                        animation: 'spin 0.8s linear infinite',
                        display: 'inline-block',
                        flexShrink: 0
                      }}
                    />
                    <span>Generating link...</span>
                  </>
                ) : copied ? (
                  <>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                    <span>Copied!</span>
                  </>
                ) : (
                  <>
                    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                      <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
                      <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
                    </svg>
                    <span>Copy link</span>
                  </>
                )}
              </button>
            </div>
          </div>
        ) : (
          /* ================= SETTINGS VIEW ================= */
          <div style={{ padding: '22px 24px' }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '20px' }}>
              <button
                onClick={() => setView('main')}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#111827',
                  fontSize: '16px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: 0
                }}
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="15 18 9 12 15 6" />
                </svg>
                <span>Share chat settings</span>
              </button>
              <button
                onClick={onClose}
                style={{
                  background: 'transparent',
                  border: 'none',
                  color: '#6b7280',
                  fontSize: '18px',
                  cursor: 'pointer',
                  padding: '4px 8px',
                  borderRadius: '6px'
                }}
                onMouseEnter={(e) => {
                  e.currentTarget.style.background = '#f3f4f6';
                  e.currentTarget.style.color = '#111827';
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.background = 'transparent';
                  e.currentTarget.style.color = '#6b7280';
                }}
              >
                ✕
              </button>
            </div>

            {/* Who has access label */}
            <div style={{ fontSize: '12.5px', fontWeight: 600, color: '#4b5563', textTransform: 'uppercase', letterSpacing: '0.4px', marginBottom: '8px' }}>
              Who has access
            </div>

            {/* Custom Styled Dropdown */}
            <div ref={settingsDropdownRef} style={{ marginBottom: '16px' }}>
              <div
                onClick={() => setSettingsDropdownOpen(prev => !prev)}
                style={{
                  width: '100%',
                  background: '#ffffff',
                  border: settingsDropdownOpen ? '1.5px solid #111827' : '1.5px solid #e5e7eb',
                  borderRadius: '12px',
                  padding: '12px 14px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  cursor: 'pointer',
                  boxShadow: settingsDropdownOpen ? '0 0 0 3px rgba(15, 23, 42, 0.08)' : '0 1px 3px rgba(0, 0, 0, 0.04)',
                  boxSizing: 'border-box',
                  transition: 'all 0.15s ease'
                }}
              >
                <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                  <div
                    style={{
                      width: '32px',
                      height: '32px',
                      borderRadius: '8px',
                      background: accessType === 'anyone' ? '#f0fdf4' : '#eff6ff',
                      color: accessType === 'anyone' ? '#16a34a' : '#2563eb',
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'center',
                      flexShrink: 0
                    }}
                  >
                    {accessType === 'anyone' ? (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <circle cx="12" cy="12" r="10" />
                        <line x1="2" y1="12" x2="22" y2="12" />
                        <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                      </svg>
                    ) : (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                        <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                      </svg>
                    )}
                  </div>
                  <div style={{ textAlign: 'left' }}>
                    <div style={{ fontSize: '14px', fontWeight: 600, color: '#111827', lineHeight: 1.2 }}>
                      {accessType === 'anyone' ? 'Anyone with the link' : 'Only people invited'}
                    </div>
                    <div style={{ fontSize: '12px', color: '#6b7280', marginTop: '2px' }}>
                      {accessType === 'anyone' ? 'Public snapshot — anyone with link can view' : 'Restricted access — only approved emails can view'}
                    </div>
                  </div>
                </div>

                <div style={{ color: '#6b7280', display: 'flex', alignItems: 'center', transform: settingsDropdownOpen ? 'rotate(180deg)' : 'none', transition: 'transform 0.2s ease' }}>
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="6 9 12 15 18 9" />
                  </svg>
                </div>
              </div>

              {settingsDropdownOpen && (
                <div
                  style={{
                    marginTop: '8px',
                    background: '#ffffff',
                    border: '1px solid #e5e7eb',
                    borderRadius: '12px',
                    boxShadow: '0 4px 16px rgba(0, 0, 0, 0.06)',
                    padding: '6px',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '4px',
                    animation: 'slideDown 0.15s ease-out'
                  }}
                >
                  {/* Option 1: Anyone with the link */}
                  <div
                    onClick={() => {
                      setAccessType('anyone');
                      setSettingsDropdownOpen(false);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: accessType === 'anyone' ? '#f9fafb' : 'transparent',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = accessType === 'anyone' ? '#f9fafb' : 'transparent')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div
                        style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '6px',
                          background: '#f0fdf4',
                          color: '#16a34a',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <circle cx="12" cy="12" r="10" />
                          <line x1="2" y1="12" x2="22" y2="12" />
                          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
                        </svg>
                      </div>
                      <div style={{ textAlign: 'left' }}>
                        <div style={{ fontSize: '13.5px', fontWeight: 600, color: '#111827' }}>Anyone with the link</div>
                        <div style={{ fontSize: '11.5px', color: '#6b7280' }}>Anyone with the link can view this snapshot</div>
                      </div>
                    </div>
                    {accessType === 'anyone' && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#16a34a" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>

                  {/* Option 2: Only people invited */}
                  <div
                    onClick={() => {
                      setAccessType('invited');
                      setSettingsDropdownOpen(false);
                    }}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      padding: '10px 12px',
                      borderRadius: '8px',
                      background: accessType === 'invited' ? '#f9fafb' : 'transparent',
                      cursor: 'pointer',
                      transition: 'background 0.15s ease'
                    }}
                    onMouseEnter={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                    onMouseLeave={(e) => (e.currentTarget.style.background = accessType === 'invited' ? '#f9fafb' : 'transparent')}
                  >
                    <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                      <div
                        style={{
                          width: '28px',
                          height: '28px',
                          borderRadius: '6px',
                          background: '#eff6ff',
                          color: '#2563eb',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center'
                        }}
                      >
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                          <path d="M7 11V7a5 5 0 0 1 10 0v4" />
                        </svg>
                      </div>
                      <div style={{ textAlign: 'left' }}>
                        <div style={{ fontSize: '13.5px', fontWeight: 600, color: '#111827' }}>Only people invited</div>
                        <div style={{ fontSize: '11.5px', color: '#6b7280' }}>Only approved email addresses can access</div>
                      </div>
                    </div>
                    {accessType === 'invited' && (
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#2563eb" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="20 6 9 17 4 12" />
                      </svg>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Divider */}
            <div style={{ height: '1px', background: '#e5e7eb', margin: '20px 0 16px 0' }} />

            {/* Bottom Actions Bar */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <button
                onClick={handleStopSharing}
                disabled={isUpdating}
                style={{
                  background: '#fee2e2',
                  color: '#b91c1c',
                  border: '1px solid #fecaca',
                  borderRadius: '8px',
                  padding: '9px 16px',
                  fontSize: '13.5px',
                  fontWeight: 600,
                  cursor: 'pointer',
                  transition: 'all 0.15s ease'
                }}
                onMouseEnter={(e) => (e.currentTarget.style.background = '#fca5a5')}
                onMouseLeave={(e) => (e.currentTarget.style.background = '#fee2e2')}
              >
                Stop sharing
              </button>

              <div style={{ display: 'flex', gap: '8px' }}>
                <button
                  onClick={() => setView('main')}
                  style={{
                    background: '#f3f4f6',
                    color: '#374151',
                    border: '1px solid #e5e7eb',
                    borderRadius: '8px',
                    padding: '9px 16px',
                    fontSize: '13.5px',
                    fontWeight: 500,
                    cursor: 'pointer',
                    transition: 'background 0.15s ease'
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#e5e7eb')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#f3f4f6')}
                >
                  Back
                </button>
                <button
                  onClick={() => handleSaveSettings(accessType)}
                  disabled={isUpdating}
                  style={{
                    background: '#000000',
                    color: '#ffffff',
                    border: 'none',
                    borderRadius: '8px',
                    padding: '9px 18px',
                    fontSize: '13.5px',
                    fontWeight: 600,
                    cursor: 'pointer',
                    transition: 'background 0.15s ease'
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.background = '#1f2937')}
                  onMouseLeave={(e) => (e.currentTarget.style.background = '#000000')}
                >
                  {isUpdating ? 'Saving...' : 'Save'}
                </button>
              </div>
            </div>
          </div>
        )}
        <style>{`
          @keyframes spin {
            to { transform: rotate(360deg); }
          }
          @keyframes fadeIn {
            from { opacity: 0; transform: scale(0.97); }
            to { opacity: 1; transform: scale(1); }
          }
          @keyframes slideDown {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
          }
        `}</style>
      </div>
    </div>
  );
}
