'use client';

import React, { useState, useEffect, useCallback } from 'react';
import WaveformVisualizer from './WaveformVisualizer';
import { useVoiceRecorder } from '../../hooks/useVoiceRecorder';
import { useSpeechToText } from '../../hooks/useSpeechToText';
import styles from './VoiceInput.module.css';

interface VoiceInputProps {
  onTranscript: (finalText: string) => void;
  onLiveTranscript?: (liveText: string) => void;
  onCancel?: () => void;
  disabled?: boolean;
  onRecordingChange?: (isRecording: boolean) => void;
}

export default function VoiceInput({
  onTranscript,
  onLiveTranscript,
  onCancel,
  disabled = false,
  onRecordingChange,
}: VoiceInputProps) {
  const [isRecording, setIsRecording] = useState(false);

  const { startRecording, stopRecording, analyserRef } = useVoiceRecorder();
  const {
    startListening,
    stopListening,
    resetTranscript,
    interimTranscript,
    finalTranscript,
    isSupported,
    error,
  } = useSpeechToText();

  // Notify parent component of recording state changes
  useEffect(() => {
    onRecordingChange?.(isRecording);
  }, [isRecording, onRecordingChange]);

  // Stream incoming speech live to parent (just like Claude)
  useEffect(() => {
    if (!isRecording) return;
    const liveText = (finalTranscript + (interimTranscript ? ' ' + interimTranscript : '')).trim();
    if (liveText && onLiveTranscript) {
      onLiveTranscript(liveText);
    }
  }, [finalTranscript, interimTranscript, isRecording, onLiveTranscript]);

  /* ── Start Recording ── */
  const handleStart = useCallback(async () => {
    if (disabled) return;

    startListening();

    const ok = await startRecording();
    if (!ok) {
      stopListening();
      return;
    }

    setIsRecording(true);
  }, [disabled, startListening, startRecording, stopListening]);

  /* ── Confirm (✓): commit speech transcript ── */
  const handleConfirm = useCallback(() => {
    const transcript = stopListening();
    stopRecording();
    setIsRecording(false);
    resetTranscript();

    const text = (transcript || '').trim();
    onTranscript(text);
  }, [stopListening, stopRecording, resetTranscript, onTranscript]);

  /* ── Cancel (✕): abort and revert text ── */
  const handleCancel = useCallback(() => {
    stopListening();
    stopRecording();
    setIsRecording(false);
    resetTranscript();
    onCancel?.();
  }, [stopListening, stopRecording, resetTranscript, onCancel]);

  /* ── Keyboard Shortcuts (Esc to cancel, Enter to confirm) ── */
  useEffect(() => {
    if (!isRecording) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        handleCancel();
      } else if (e.key === 'Enter') {
        e.preventDefault();
        handleConfirm();
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isRecording, handleCancel, handleConfirm]);

  /* ── Cleanup on unmount ── */
  useEffect(() => {
    return () => {
      stopListening();
      stopRecording();
    };
  }, [stopListening, stopRecording]);

  return (
    <>
      {/* ── When Recording: Small waveform on the right + Cancel/Confirm (Claude style) ── */}
      {isRecording ? (
        <div className={styles.recordingGroup}>
          {/* Compact scrolling waveform */}
          <div className={styles.compactWaveform}>
            <WaveformVisualizer
              analyserRef={analyserRef}
              isRecording={isRecording}
              barCount={26}
              color="#D4A843"
              dotColor="#D4CFC7"
              height={20}
            />
          </div>

          {/* Cancel button (✕) */}
          <button
            type="button"
            className={styles.cancelBtn}
            onClick={handleCancel}
            title="Cancel (Esc)"
            aria-label="Cancel recording"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>

          {/* Confirm button (✓) */}
          <button
            type="button"
            className={styles.confirmBtn}
            onClick={handleConfirm}
            title="Done (Enter)"
            aria-label="Confirm voice input"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12" />
            </svg>
          </button>
        </div>
      ) : (
        /* ── When Not Recording: Normal mic button ── */
        <button
          type="button"
          className={styles.micBtn}
          onClick={handleStart}
          disabled={disabled || !isSupported}
          title={isSupported ? 'Voice input (Click to speak)' : 'Voice input not supported in this browser'}
          aria-label="Start voice input"
        >
          <svg
            width="15"
            height="15"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z" />
            <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
            <line x1="12" y1="19" x2="12" y2="22" />
          </svg>
        </button>
      )}

      {/* ── Error Toast ── */}
      {error && !isRecording && (
        <div className={styles.errorToast}>
          {error}
        </div>
      )}
    </>
  );
}
