import { useEffect, useRef } from "react";

/**
 * Renders pre-computed waveform peaks as a canvas bar chart.
 * No audio loading required — just the stored peak array.
 */
export default function WaveformThumbnail({ peaks = [], active = false, width = 180, height = 48 }) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas || !peaks.length) return;

    const ctx = canvas.getContext("2d");
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = height * dpr;
    ctx.scale(dpr, dpr);

    ctx.clearRect(0, 0, width, height);

    const barWidth = width / peaks.length;
    const midY = height / 2;
    const color = active ? "#60a5fa" : "#6b7280";

    ctx.fillStyle = color;

    peaks.forEach((peak, i) => {
      const barHeight = Math.max(2, peak * (height - 4));
      const x = i * barWidth;
      const y = midY - barHeight / 2;
      ctx.fillRect(x, y, Math.max(1, barWidth - 1), barHeight);
    });
  }, [peaks, active, width, height]);

  return (
    <canvas
      ref={canvasRef}
      style={{ width, height, display: "block" }}
    />
  );
}
