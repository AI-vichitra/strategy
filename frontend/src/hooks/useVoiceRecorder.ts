import { useRef, useCallback } from 'react';

/**
 * useVoiceRecorder
 * Manages microphone access, MediaStream lifecycle, and Web Audio API
 * AnalyserNode for real-time frequency data used by WaveformVisualizer.
 */
export function useVoiceRecorder() {
  const streamRef = useRef<MediaStream | null>(null);
  const audioCtxRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);

  const startRecording = useCallback(async (): Promise<boolean> => {
    try {
      if (typeof window === 'undefined' || !navigator.mediaDevices?.getUserMedia) {
        console.warn('[useVoiceRecorder] getUserMedia is not supported');
        return false;
      }

      const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
      streamRef.current = stream;

      const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
      const audioCtx = new AudioContextClass();
      audioCtxRef.current = audioCtx;

      if (audioCtx.state === 'suspended') {
        await audioCtx.resume();
      }

      const analyser = audioCtx.createAnalyser();
      analyser.fftSize = 256; // 128 frequency bins
      analyser.smoothingTimeConstant = 0.82; // smooth out spikes
      analyserRef.current = analyser;

      const source = audioCtx.createMediaStreamSource(stream);
      sourceRef.current = source;
      source.connect(analyser);

      return true;
    } catch (err) {
      console.error('[useVoiceRecorder] mic access error:', err);
      return false;
    }
  }, []);

  const stopRecording = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect();
      sourceRef.current = null;
    }
    if (audioCtxRef.current) {
      audioCtxRef.current.close().catch(() => {});
      audioCtxRef.current = null;
    }
    analyserRef.current = null;
  }, []);

  return { startRecording, stopRecording, analyserRef };
}
