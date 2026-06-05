import * as React from 'react';
import { cn } from '../../lib/utils.js';

const toneClasses: Record<string, string> = {
  default: 'bg-foreground text-background',
  success: 'bg-emerald-600 text-white',
  warning: 'bg-amber-500 text-white',
  danger: 'bg-rose-600 text-white',
  muted: 'bg-muted text-muted-foreground',
  outline: 'border border-border bg-background text-foreground',
};

export function Badge({
  className,
  tone = 'default',
  ...props
}: React.HTMLAttributes<HTMLSpanElement> & { tone?: keyof typeof toneClasses }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-3 py-1 text-[11px] font-bold uppercase tracking-[0.18em]',
        toneClasses[tone],
        className
      )}
      {...props}
    />
  );
}
