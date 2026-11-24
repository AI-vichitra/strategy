import { useRef, useCallback, useState } from 'react';

/**
 * useSpeechToText
 * Wraps Web Speech API (SpeechRecognition / webkitSpeechRecognition)
 * for real-time speech-to-text with interim previews and continuous recording.
 */
export function useSpeechToText() {
  const recognitionRef = useRef<any>(null);
  const isListeningRef = useRef(false);
  const accumulatedBeforeSessionRef = useRef('');
  const finalBufRef = useRef('');
  const interimBufRef = useRef('');
  const [interimTranscript, setInterimTranscript] = useState('');
  const [finalTranscript, setFinalTranscript] = useState('');
  const [error, setError] = useState<string | null>(null);

  const isSupported =
    typeof window !== 'undefined' &&
    !!((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

  const startListening = useCallback(() => {
    if (!isSupported) {
      setError('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
      return;
    }

    if (recognitionRef.current) {
      try {
        recognitionRef.current.abort();
      } catch (_) {}
    }

    isListeningRef.current = true;
    accumulatedBeforeSessionRef.current = '';
    finalBufRef.current = '';
    interimBufRef.current = '';
    setFinalTranscript('');
    setInterimTranscript('');
    setError(null);

    const SpeechRecognitionClass =
      (window as any).SpeechRecognition || (window as any).webkitSpeechRecognition;
    const recognition = new SpeechRecognitionClass();

    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.maxAlternatives = 1;
    recognition.lang = typeof navigator !== 'undefined' ? navigator.language || 'en-US' : 'en-US';

    recognition.onresult = (event: any) => {
      let sessionFinal = '';
      let sessionInterim = '';

      for (let i = 0; i < event.results.length; i++) {
        const item = event.results[i];
        const text = item[0]?.transcript || '';
        if (item.isFinal) {
          sessionFinal += (sessionFinal ? ' ' : '') + text.trim();
        } else {
          sessionInterim += text;
        }
      }

      const totalFinal = (
        (accumulatedBeforeSessionRef.current ? accumulatedBeforeSessionRef.current + ' ' : '') +
        sessionFinal
      ).trim();

      finalBufRef.current = totalFinal;
      interimBufRef.current = sessionInterim.trim();

      setFinalTranscript(totalFinal);
      setInterimTranscript(sessionInterim.trim());
    };

    recognition.onerror = (event: any) => {
      if (event.error === 'no-speech' || event.error === 'aborted') return;

      const messages: Record<string, string> = {
        'audio-capture': 'No microphone found.',
        'not-allowed': 'Microphone permission denied. Please allow access in browser settings.',
        'network': 'Network error during speech recognition.',
        'service-not-allowed': 'Speech service is not allowed.',
      };
      setError(messages[event.error] || `Speech error: ${event.error}`);
    };

    recognition.onend = () => {
      // If recognition stopped unexpectedly and we haven't manually stopped it, restart cleanly
      if (isListeningRef.current && recognitionRef.current === recognition) {
        accumulatedBeforeSessionRef.current = finalBufRef.current;
        try {
          recognition.start();
        } catch (_) {}
      }
    };

    try {
      recognition.start();
      recognitionRef.current = recognition;
    } catch (e: any) {
      console.error('[useSpeechToText] start error:', e);
      setError('Could not start speech recognition.');
    }
  }, [isSupported]);

  const stopListening = useCallback((): string => {
    isListeningRef.current = false;
    if (!recognitionRef.current) return finalBufRef.current;

    const rec = recognitionRef.current;
    recognitionRef.current = null;

    try {
      rec.stop();
    } catch (_) {}

    const accumulated = (finalBufRef.current + ' ' + interimBufRef.current).trim();
    setInterimTranscript('');
    interimBufRef.current = '';
    return accumulated;
  }, []);

  const resetTranscript = useCallback(() => {
    isListeningRef.current = false;
    accumulatedBeforeSessionRef.current = '';
    finalBufRef.current = '';
    interimBufRef.current = '';
    setFinalTranscript('');
    setInterimTranscript('');
    setError(null);
  }, []);

  return {
    startListening,
    stopListening,
    resetTranscript,
    interimTranscript,
    finalTranscript,
    isSupported,
    error,
  };
}
