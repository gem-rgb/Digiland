import React, { useEffect, useRef } from 'react';
import type { PointerEvent } from 'react';
import { Eraser } from 'lucide-react';
import { Button } from '../ui/button.js';

interface SignaturePadProps {
  label: string;
  onChange: (value: string) => void;
  placeholder?: string;
  className?: string;
}

export function SignaturePad({ label, onChange, placeholder, className }: SignaturePadProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawing = useRef(false);
  const hasInk = useRef(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const resize = () => {
      const ratio = Math.max(window.devicePixelRatio || 1, 1);
      const rect = canvas.getBoundingClientRect();
      canvas.width = Math.max(1, Math.floor(rect.width * ratio));
      canvas.height = Math.max(1, Math.floor(rect.height * ratio));
      const ctx = canvas.getContext('2d');
      if (!ctx) return;
      ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      ctx.strokeStyle = '#0f172a';
      ctx.lineWidth = 2.5;
      ctx.clearRect(0, 0, rect.width, rect.height);
    };

    resize();
    window.addEventListener('resize', resize);
    return () => window.removeEventListener('resize', resize);
  }, []);

  const getContext = () => canvasRef.current?.getContext('2d') || null;

  const getPoint = (event: PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    if (!canvas) return { x: 0, y: 0 };
    const rect = canvas.getBoundingClientRect();
    return {
      x: event.clientX - rect.left,
      y: event.clientY - rect.top,
    };
  };

  const startDrawing = (event: PointerEvent<HTMLCanvasElement>) => {
    const canvas = canvasRef.current;
    const ctx = getContext();
    if (!canvas || !ctx) return;
    canvas.setPointerCapture(event.pointerId);
    drawing.current = true;
    const point = getPoint(event);
    ctx.beginPath();
    ctx.moveTo(point.x, point.y);
  };

  const draw = (event: PointerEvent<HTMLCanvasElement>) => {
    const ctx = getContext();
    if (!drawing.current || !ctx) return;
    const point = getPoint(event);
    ctx.lineTo(point.x, point.y);
    ctx.stroke();
    hasInk.current = true;
  };

  const stopDrawing = () => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    drawing.current = false;
    if (hasInk.current) {
      onChange(canvas.toDataURL('image/png'));
    }
  };

  const clear = () => {
    const canvas = canvasRef.current;
    const ctx = getContext();
    if (!canvas || !ctx) return;
    const rect = canvas.getBoundingClientRect();
    ctx.clearRect(0, 0, rect.width, rect.height);
    hasInk.current = false;
    onChange('');
  };

  return (
    <div className={className}>
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-foreground">{label}</div>
          {placeholder ? <div className="text-xs text-muted-foreground">{placeholder}</div> : null}
        </div>
        <Button type="button" variant="outline" size="sm" onClick={clear}>
          <Eraser className="h-4 w-4" />
          Clear
        </Button>
      </div>
      <canvas
        ref={canvasRef}
        className="h-44 w-full rounded-3xl border border-border bg-white shadow-sm"
        onPointerDown={startDrawing}
        onPointerMove={draw}
        onPointerUp={stopDrawing}
        onPointerLeave={stopDrawing}
        style={{ touchAction: 'none' }}
      />
      <div className="mt-2 text-xs text-muted-foreground">Draw your signature inside the box above.</div>
    </div>
  );
}
