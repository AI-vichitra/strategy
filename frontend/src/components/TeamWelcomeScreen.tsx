'use client';
import React, { useEffect, useState } from 'react';

interface TeamWelcomeScreenProps {
  adminName?: string;
  teamName?: string;
  onContinue: () => void;
  autoRedirectSeconds?: number;
}

export default function TeamWelcomeScreen({
  adminName,
  teamName,
  onContinue,
  autoRedirectSeconds = 2.2,
}: TeamWelcomeScreenProps) {
  const [isVisible, setIsVisible] = useState(true);

  useEffect(() => {
    // Auto-continue after specified seconds (~2s as requested)
    const timer = setTimeout(() => {
      handleContinue();
    }, autoRedirectSeconds * 1000);

    return () => clearTimeout(timer);
  }, [autoRedirectSeconds]);

  const handleContinue = () => {
    setIsVisible(false);
    setTimeout(onContinue, 300);
  };

  if (!isVisible) return null;

  const displayOwner = adminName?.trim()
    ? `${adminName.trim()}'s Team`
    : teamName?.trim()
    ? `${teamName.trim()} Workspace`
    : 'the Team Workspace';

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(250, 248, 245, 0.85)',
        backdropFilter: 'blur(6px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        zIndex: 10000,
        padding: '20px',
        animation: isVisible ? 'fadeIn 0.25s ease-in' : 'fadeOut 0.25s ease-out',
      }}
    >
      <div
        style={{
          textAlign: 'center',
          maxWidth: '420px',
          width: '100%',
          background: '#ffffff',
          border: '1px solid #E8E4DC',
          borderRadius: '16px',
          padding: '32px 28px',
          boxShadow: '0 20px 48px rgba(0, 0, 0, 0.06)',
          boxSizing: 'border-box',
        }}
      >
        {/* Sleek Success Icon */}
        <div
          style={{
            width: '48px',
            height: '48px',
            borderRadius: '12px',
            background: 'linear-gradient(135deg, #2D2A26 0%, #D4A843 100%)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            margin: '0 auto 16px',
            boxShadow: '0 4px 12px rgba(45, 42, 38, 0.12)',
          }}
        >
          <svg
            width="22"
            height="22"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#ffffff"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="20 6 9 17 4 12" />
          </svg>
        </div>

        {/* Minimal Welcome Heading */}
        <h1
          style={{
            fontSize: '20px',
            fontWeight: 600,
            color: '#1A1A1A',
            marginBottom: '6px',
            letterSpacing: '-0.015em',
            lineHeight: 1.3,
          }}
        >
          Welcome to {teamName?.trim() || 'the Workspace'}
        </h1>

        <p
          style={{
            fontSize: '13px',
            color: '#6B6560',
            lineHeight: 1.5,
            marginBottom: '22px',
          }}
        >
          {adminName?.trim() ? `Invited by ${adminName.trim()}. ` : ''}Your workspace access is ready.
        </p>

        {/* Continue Button */}
        <div>
          <button
            onClick={handleContinue}
            style={{
              width: '100%',
              padding: '10px 20px',
              background: '#1A1A1A',
              border: 'none',
              borderRadius: '8px',
              color: '#ffffff',
              fontSize: '13px',
              fontWeight: 600,
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              boxShadow: '0 2px 6px rgba(0, 0, 0, 0.08)',
              fontFamily: 'inherit',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.background = '#2D2A26';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = '#1A1A1A';
            }}
          >
            Continue to Workspace →
          </button>
        </div>

        <p
          style={{
            fontSize: '12px',
            color: '#9CA3AF',
            marginTop: '14px',
            marginBottom: 0,
          }}
        >
          Redirecting automatically...
        </p>
      </div>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; }
          to { opacity: 1; }
        }
        @keyframes fadeOut {
          from { opacity: 1; }
          to { opacity: 0; }
        }
        @keyframes scaleIn {
          0% {
            transform: scale(0);
            opacity: 0;
          }
          70% {
            transform: scale(1.12);
            opacity: 1;
          }
          100% {
            transform: scale(1);
            opacity: 1;
          }
        }
        @keyframes drawCheck {
          0% {
            stroke-dashoffset: 50;
          }
          100% {
            stroke-dashoffset: 0;
          }
        }
      `}</style>
    </div>
  );
}
