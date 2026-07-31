import * as React from 'react';
import { cn } from '../../lib/utils.js';

const toneClasses: Record<string, string> = {
  default: 'bg-emerald-500/15 text-emerald-300 border border-emerald-500/30',
  success: 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/40',
  warning: 'bg-amber-500/20 text-amber-300 border border-amber-500/40',
  danger: 'bg-rose-500/20 text-rose-300 border border-rose-500/40',
  muted: 'bg-slate-800 text-slate-300 border border-slate-700',
  outline: 'border border-emerald-400/30 bg-emerald-500/10 text-emerald-300',
};

export function Badge({
  className,
  tone = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof toneClasses }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-3 py-1 text-[11px] font-extrabold uppercase tracking-[0.18em]',
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
