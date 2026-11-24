'use client';

import React, { useRef, useEffect } from 'react';

interface WaveformVisualizerProps {
  analyserRef: React.RefObject<AnalyserNode | null>;
  isRecording: boolean;
  barCount?: number;
  color?: string;
  dotColor?: string;
  height?: number;
}

/**
 * WaveformVisualizer
 * Draws a real-time scrolling voice waveform where audio volume travels from right to left.
 * Silent frames enter as subtle dots, and active voice signals enter as rounded reactive bars.
 */
export default function WaveformVisualizer({
  analyserRef,
  isRecording,
  barCount = 65,
  color = '#D4A843',
  dotColor = '#D4CFC7',
  height = 32,
}: WaveformVisualizerProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const rafRef = useRef<number | null>(null);

  // History buffer of volume levels (0 to 1)
  const historyRef = useRef<Float32Array>(new Float32Array(barCount).fill(0));
  const shiftCounterRef = useRef(0);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = typeof window !== 'undefined' ? window.devicePixelRatio || 1 : 1;

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      canvas.width = rect.width * dpr;
      canvas.height = height * dpr;
      ctx.scale(dpr, dpr);
    };

    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    // Reset history to quiet dots initially
    historyRef.current = new Float32Array(barCount).fill(0);

    const draw = () => {
      rafRef.current = requestAnimationFrame(draw);

      const W = canvas.width / dpr;
      const H = canvas.height / dpr;

      ctx.clearRect(0, 0, W, H);

      const analyser = analyserRef?.current;
      const history = historyRef.current;

      // 1. Get current volume level
      let currentVolume = 0;
      if (isRecording && analyser) {
        const data = new Uint8Array(analyser.frequencyBinCount);
        analyser.getByteFrequencyData(data);

        // Sum up speech frequency range (lower-middle spectrum)
        let sum = 0;
        const voiceRange = Math.floor(data.length * 0.55);
        for (let i = 0; i < voiceRange; i++) {
          sum += data[i];
        }
        currentVolume = sum / voiceRange / 255; // 0 to 1
      }

      // 2. Smooth volume peak
      const targetVolume = currentVolume > 0.03 ? currentVolume : 0;

      // 3. Shift history to the left every 2 frames for smooth scrolling speed
      shiftCounterRef.current++;
      if (shiftCounterRef.current >= 2) {
        shiftCounterRef.current = 0;
        for (let i = 0; i < barCount - 1; i++) {
          history[i] = history[i + 1];
        }
        // Interpolate entry slightly for smooth transitions
        const prev = history[barCount - 1];
        history[barCount - 1] = prev + (targetVolume - prev) * 0.45;
      }

      // 4. Render bars & dots travelling from right to left
      const totalGap = W * 0.42; // 42% of space for gaps
      const barW = Math.max(2, (W - totalGap) / barCount);
      const gap = totalGap / (barCount - 1);

      for (let i = 0; i < barCount; i++) {
        const amp = history[i];
        const x = i * (barW + gap);

        if (amp < 0.06) {
          // Draw subtle dot for silence
          ctx.beginPath();
          ctx.arc(x + barW / 2, H / 2, 2, 0, Math.PI * 2);
          ctx.fillStyle = dotColor;
          ctx.fill();
        } else {
          // Draw reactive rounded voice bar
          const barH = Math.max(amp * (H * 0.95), 4);
          const y = (H - barH) / 2;

          ctx.fillStyle = color;
          ctx.beginPath();
          drawRoundRect(ctx, x, y, barW, barH, barW / 2);
          ctx.fill();
        }
      }
    };

    rafRef.current = requestAnimationFrame(draw);

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
      }
      ro.disconnect();
    };
  }, [isRecording, barCount, color, dotColor, height, analyserRef]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: `${height}px`,
        display: 'block',
      }}
    />
  );
}

function drawRoundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
) {
  const radius = Math.min(r, w / 2, h / 2);
  ctx.moveTo(x + radius, y);
  ctx.arcTo(x + w, y, x + w, y + h, radius);
  ctx.arcTo(x + w, y + h, x, y + h, radius);
  ctx.arcTo(x, y + h, x, y, radius);
  ctx.arcTo(x, y, x + w, y, radius);
  ctx.closePath();
}
