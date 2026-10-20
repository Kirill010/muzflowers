import { useEffect, useRef } from 'react';

interface Petal {
  startX: number;
  startY: number;
  dirX: number; // direction vector (unit-ish)
  dirY: number;
  travel: number; // px travelled per loop
  duration: number; // loop seconds — varies per instance
  offset: number; // per-instance time offset
  rotSpeed: number; // rad per second
  baseRot: number;
  size: number;
  color: string;
  wobble: number;
  wobbleFreq: number;
}

const COLORS = [
  'rgba(217, 126, 74, 0.5)', // терракота
  'rgba(201, 110, 116, 0.45)', // пыльная роза
  'rgba(138, 154, 91, 0.4)', // олива
  'rgba(230, 199, 156, 0.55)', // песочный
  'rgba(6, 64, 19, 0.22)', // лесная зелень
];

function makePetal(w: number, h: number, randomY = false): Petal {
  const duration = 9 + Math.random() * 10;
  return {
    startX: Math.random() * w * 0.9,
    startY: randomY ? Math.random() * h : -40 - Math.random() * h * 0.3,
    dirX: 0.35 + Math.random() * 0.35, // drift down-right
    dirY: 1,
    travel: h * (0.7 + Math.random() * 0.6),
    duration,
    offset: Math.random() * duration,
    rotSpeed: (Math.PI * 2 * (0.8 + Math.random() * 1.4)) / duration, // ~20×modTime feel
    baseRot: Math.random() * Math.PI * 2,
    size: 7 + Math.random() * 10,
    color: COLORS[Math.floor(Math.random() * COLORS.length)],
    wobble: 12 + Math.random() * 22,
    wobbleFreq: 1.2 + Math.random() * 1.8,
  };
}

function drawPetal(ctx: CanvasRenderingContext2D, p: Petal, time: number) {
  const t = ((time + p.offset) % p.duration) / p.duration; // 0..1 loop progress
  const along = t * p.travel;
  const x = p.startX + p.dirX * along + Math.sin(time * p.wobbleFreq + p.offset) * p.wobble;
  const y = p.startY + p.dirY * along;
  const rot = p.baseRot + time * p.rotSpeed * 20 * 0.08; // continuous rotation
  const fadeIn = Math.min(1, t / 0.08);
  const fadeOut = Math.min(1, (1 - t) / 0.08);
  const alpha = Math.min(fadeIn, fadeOut);
  if (alpha <= 0) return;

  ctx.save();
  ctx.translate(x, y);
  ctx.rotate(rot);
  ctx.globalAlpha = alpha;
  ctx.fillStyle = p.color;
  const s = p.size;
  ctx.beginPath();
  ctx.moveTo(0, -s);
  ctx.bezierCurveTo(s * 0.9, -s * 0.7, s * 0.75, s * 0.55, 0, s);
  ctx.bezierCurveTo(-s * 0.75, s * 0.55, -s * 0.9, -s * 0.7, 0, -s);
  ctx.fill();
  // прожилка
  ctx.globalAlpha = alpha * 0.5;
  ctx.strokeStyle = 'rgba(6, 64, 19, 0.35)';
  ctx.lineWidth = 0.7;
  ctx.beginPath();
  ctx.moveTo(0, -s * 0.8);
  ctx.quadraticCurveTo(s * 0.12, 0, 0, s * 0.8);
  ctx.stroke();
  ctx.restore();
}

export default function PetalCanvas({ density = 34, className = '' }: { density?: number; className?: string }) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let petals: Petal[] = [];
    let raf = 0;
    let running = true;
    const dpr = Math.min(2, window.devicePixelRatio || 1);

    const resize = () => {
      const rect = canvas.parentElement?.getBoundingClientRect();
      if (!rect) return;
      canvas.width = rect.width * dpr;
      canvas.height = rect.height * dpr;
      canvas.style.width = rect.width + 'px';
      canvas.style.height = rect.height + 'px';
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      petals = Array.from({ length: density }, () => makePetal(rect.width, rect.height, true));
    };

    resize();
    const ro = new ResizeObserver(resize);
    if (canvas.parentElement) ro.observe(canvas.parentElement);

    const t0 = performance.now();
    const loop = (now: number) => {
      if (!running) return;
      const time = (now - t0) / 1000;
      const w = canvas.width / dpr;
      const h = canvas.height / dpr;
      ctx.clearRect(0, 0, w, h);
      for (const p of petals) drawPetal(ctx, p, time);
      raf = requestAnimationFrame(loop);
    };
    raf = requestAnimationFrame(loop);

    const onVis = () => {
      running = document.visibilityState === 'visible';
      if (running) raf = requestAnimationFrame(loop);
      else cancelAnimationFrame(raf);
    };
    document.addEventListener('visibilitychange', onVis);

    return () => {
      running = false;
      cancelAnimationFrame(raf);
      ro.disconnect();
      document.removeEventListener('visibilitychange', onVis);
    };
  }, [density]);

  return (
    <canvas
      ref={canvasRef}
      aria-hidden="true"
      className={`pointer-events-none absolute inset-0 ${className}`}
    />
  );
}
